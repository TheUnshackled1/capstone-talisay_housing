from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.cache import cache
from functools import wraps
import json
import re
from urllib.parse import urlencode

from intake.models import Applicant
from units.models import LotAward, HousingUnit
from .models import Case, CaseAction, CaseEvidence, FieldSettledIncidentLog
from . import workflow as wf
from accounts.models import FIELD_INSPECTOR_POSITIONS

# Monitor desk case recording + field settled log: no illegal occupant or occupancy dispute.
CASE_TYPE_EXCLUDED_FROM_MONITOR_INTAKE_FORMS = frozenset({
    'illegal_occupant',
    'occupancy_dispute',
})
# Field case recording only: occupancy dispute hidden; illegal occupant stays available.
CASE_TYPE_EXCLUDED_FROM_FIELD_CASE_RECORDING = frozenset({'occupancy_dispute'})


def case_type_choices_for_monitor_intake_forms():
    return [
        c for c in Case.CASE_TYPE_CHOICES
        if c[0] not in CASE_TYPE_EXCLUDED_FROM_MONITOR_INTAKE_FORMS
    ]


def case_type_choices_for_field_case_recording():
    return [
        c for c in Case.CASE_TYPE_CHOICES
        if c[0] not in CASE_TYPE_EXCLUDED_FROM_FIELD_CASE_RECORDING
    ]


def case_type_choices_for_intake_forms():
    """Alias — monitor desk + field settled log."""
    return case_type_choices_for_monitor_intake_forms()


def _valid_case_types_for_create(position, *, settled_log=False):
    if settled_log or position in wf.CASE_MONITOR_DESK_POSITIONS:
        return [code for code, _ in case_type_choices_for_monitor_intake_forms()]
    if position in FIELD_INSPECTOR_POSITIONS:
        return [code for code, _ in case_type_choices_for_field_case_recording()]
    return [code for code, _ in Case.CASE_TYPE_CHOICES]


def cases_page_url(position, **query):
    """Canonical Module 5 page URL for a staff position (accounts routes or legacy /cases/)."""
    if position in FIELD_INSPECTOR_POSITIONS:
        base = reverse('accounts:field_cases')
    elif position == 'second_member':
        base = reverse('accounts:second_member_cases')
    elif position == 'fourth_member':
        base = reverse('accounts:fourth_member_cases')
    else:
        base = reverse('cases:case_dashboard', kwargs={'position': position})
    params = {k: v for k, v in query.items() if v}
    return f'{base}?{urlencode(params)}' if params else base


def module5_cases_for_unit(unit, applicant=None, limit=20):
    """Cases tied to this lot: related_unit and/or beneficiary as complainant or respondent."""
    q = models.Q(related_unit=unit)
    if applicant:
        q |= models.Q(complainant_applicant=applicant) | models.Q(subject_applicant=applicant)
    return (
        Case.objects.filter(q)
        .distinct()
        .order_by('-received_at')[:limit]
    )


def module5_case_rows_for_unit(unit, applicant=None, position='second_member'):
    """Serialize linked cases for Unit Monitoring drawer JSON."""
    rows = []
    for case in module5_cases_for_unit(unit, applicant):
        rows.append({
            'id': str(case.id),
            'case_number': case.case_number,
            'case_type_display': case.get_case_type_display(),
            'status': case.status,
            'status_display': case.get_status_display(),
            'complainant_name': case.complainant_name or '',
            'initial_description': case.initial_description or '',
            'received_at': case.received_at.isoformat() if case.received_at else '',
            'view_url': cases_page_url(position, case_id=str(case.id)),
        })
    return rows


def verify_position(view_func):
    """
    Decorator to verify that URL position parameter matches logged-in user's position.
    Security feature: prevents URL manipulation to access other roles' views.
    """
    @wraps(view_func)
    def wrapper(request, position, *args, **kwargs):
        # Check if position in URL matches user's actual position
        if request.user.position != position:
            from django.contrib import messages
            messages.error(request, f'Access denied. You are logged in as {request.user.get_position_display()}, not {position.replace("_", " ")}.')
            return redirect('accounts:dashboard')
        return view_func(request, position, *args, **kwargs)
    return wrapper


# ===================================================================
# CASE MANAGEMENT - Module 5
# ===================================================================

# List pages never need full investigation/resolution text — keep list payloads lean.
_CASE_LIST_DEFER = (
    'investigation_notes',
    'referral_notes',
    'resolution_notes',
)
# Matches client pageSize 5 × ~5 pages; avoids shipping 100 fat rows twice.
_DESK_ACTIVE_ROW_LIMIT = 25
_SETTLED_INCIDENT_ROW_LIMIT = 50
_DRAWER_CASE_LIST_LIMIT = 50

_CASE_DESK_DATA_VERSION_KEY = 'case_desk_data_version_v1'
_CASE_DESK_DATA_VERSION_TTL = 86400  # 24h; bumped on Case / settled-log writes


def _get_case_desk_data_version():
    """Cheap mutable stamp — desk-feed polls compare this without loading list_ctx."""
    v = cache.get(_CASE_DESK_DATA_VERSION_KEY)
    if v is None:
        v = 1
        cache.set(_CASE_DESK_DATA_VERSION_KEY, v, _CASE_DESK_DATA_VERSION_TTL)
    return str(v)


def _bump_case_desk_data_version():
    """Invalidate poll short-circuit + list_ctx keys that embed this stamp."""
    try:
        new_v = cache.incr(_CASE_DESK_DATA_VERSION_KEY)
        # Refresh TTL after incr (DatabaseCache incr does not extend expiry).
        cache.set(_CASE_DESK_DATA_VERSION_KEY, new_v, _CASE_DESK_DATA_VERSION_TTL)
    except ValueError:
        cache.set(_CASE_DESK_DATA_VERSION_KEY, 1, _CASE_DESK_DATA_VERSION_TTL)


def _case_desk_poll_version(request):
    """Stamp + filter signature so filter changes still miss the unchanged short-circuit."""
    q = (request.GET.get('q') or '').strip()[:40]
    filter_type = request.GET.get('type', 'all') or 'all'
    filter_status = request.GET.get('status', 'all') or 'all'
    return f"{_get_case_desk_data_version()}:{q}:{filter_type}:{filter_status}"


def _prefer_mobile_case_desk(request):
    """Render mobile cards XOR table — not both — based on Client Hints / UA."""
    from accounts.request_ua import prefer_mobile_client
    return prefer_mobile_client(request)


def _case_management_list_context(request, position, include_drawer_rows=False):
    """Shared list/KPI context for case desk page and live desk-feed API.

    Cached for 30 seconds per (data_version, position, q, status, type, drawers).
    Drawer row lists are omitted by default (lazy-loaded via desk-feed ?part=).
    """
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', 'all')
    filter_type = request.GET.get('type', 'all')
    data_version = _get_case_desk_data_version()
    drawers_flag = '1' if include_drawer_rows else '0'

    _cache_key = (
        f"case_list_ctx_v4_{data_version}_{position}"
        f"_{''.join(c if c.isalnum() else '_' for c in search_query[:40])}"
        f"_{filter_status}_{filter_type}_d{drawers_flag}"
    )
    cached = cache.get(_cache_key)
    if cached is not None:
        return cached

    # Aggregate counts — bare Case.objects (no select_related JOIN overhead).
    status_counts = Case.objects.aggregate(
        pending_review=models.Count('pk', filter=models.Q(status=wf.STATUS_PENDING_REVIEW)),
        under_review=models.Count('pk', filter=models.Q(status=wf.STATUS_UNDER_REVIEW)),
        mediation_monitoring=models.Count('pk', filter=models.Q(status=wf.STATUS_MEDIATION)),
        awaiting_response=models.Count('pk', filter=models.Q(status=wf.STATUS_AWAITING_RESPONSE)),
        referred_engineering=models.Count('pk', filter=models.Q(status=wf.STATUS_REFERRED_ENGINEERING)),
        resolved=models.Count('pk', filter=models.Q(status=wf.STATUS_RESOLVED)),
        closed=models.Count('pk', filter=models.Q(status=wf.STATUS_CLOSED)),
    )

    cases = (
        Case.objects
        .select_related(
            'received_by',
            'complainant_applicant', 'subject_applicant', 'related_unit',
        )
        .defer(*_CASE_LIST_DEFER)
        .order_by('received_at')
    )

    if search_query:
        cases = cases.filter(
            models.Q(complainant_name__icontains=search_query) |
            models.Q(case_number__icontains=search_query) |
            models.Q(initial_description__icontains=search_query) |
            models.Q(subject_name__icontains=search_query)
        )

    if filter_status != 'all':
        cases = cases.filter(status=filter_status)

    if filter_type != 'all':
        cases = cases.filter(case_type=filter_type)

    is_field_inspector = position in FIELD_INSPECTOR_POSITIONS
    use_split_case_desk = (
        position in FIELD_INSPECTOR_POSITIONS
        or position in wf.CASE_MONITOR_DESK_POSITIONS
    )
    # Field UI has no pending drawer — skip that query entirely.
    load_pending_drawer = (
        include_drawer_rows
        and not is_field_inspector
        and position in wf.CASE_MONITOR_DESK_POSITIONS
    )
    settled_incident_rows = []
    settled_on_site_count = 0
    resolved_cases = []
    pending_cases = []

    if use_split_case_desk:
        desk_cases = (
            cases.exclude(status=wf.STATUS_RESOLVED)
            .order_by('-received_at', '-pk')[:_DESK_ACTIVE_ROW_LIMIT]
        )
        desk_rows = _build_case_desk_rows(
            desk_cases,
            include_incident_logs=False,
            search_query=search_query,
            filter_type=filter_type,
            enrich=False,
        )
        # Field UI has no Settled KPI chip — skip count on cold page load.
        # Count (and rows) still load when drawers are requested via ?part=.
        if include_drawer_rows or not is_field_inspector:
            settled_base = FieldSettledIncidentLog.objects.select_related(
                'related_unit', 'logged_by', 'subject_applicant', 'complainant_applicant',
            )
            settled_filtered = _filter_settled_incident_logs_queryset(
                settled_base, search_query, filter_type,
            )
            settled_on_site_count = settled_filtered.count()
            if include_drawer_rows:
                settled_incident_rows = _settled_incident_desk_rows(
                    settled_filtered,
                    limit=_SETTLED_INCIDENT_ROW_LIMIT,
                    enrich=False,
                )
                resolved_cases = list(
                    _apply_case_list_filters(
                        Case.objects
                        .filter(status=wf.STATUS_RESOLVED)
                        .select_related(
                            'received_by', 'complainant_applicant', 'subject_applicant', 'related_unit',
                        )
                        .defer(*_CASE_LIST_DEFER),
                        search_query,
                        filter_type,
                    ).order_by('-resolved_at', '-received_at')[:_DRAWER_CASE_LIST_LIMIT]
                )
                if load_pending_drawer:
                    pending_cases = list(
                        _apply_case_list_filters(
                            Case.objects
                            .filter(status=wf.STATUS_PENDING_REVIEW)
                            .select_related(
                                'received_by', 'complainant_applicant', 'subject_applicant', 'related_unit',
                            )
                            .defer(*_CASE_LIST_DEFER),
                            search_query,
                            filter_type,
                        ).order_by('-received_at')[:_DRAWER_CASE_LIST_LIMIT]
                    )
        enrich_apps = _collect_applicants_from_cases(
            [row['case'] for row in desk_rows if row.get('case')]
        )
        enrich_apps += [
            row['incident_log'].complainant_applicant
            for row in settled_incident_rows
            if row.get('incident_log')
        ]
        enrich_apps += [
            row['incident_log'].subject_applicant
            for row in settled_incident_rows
            if row.get('incident_log')
        ]
        enrich_apps += _collect_applicants_from_cases(resolved_cases)
        enrich_apps += _collect_applicants_from_cases(pending_cases)
        _enrich_desk_applicants(enrich_apps)
        for row in settled_incident_rows:
            log = row['incident_log']
            row['incident_unit_label'] = _settled_incident_complainant_unit_label(log)
            row['incident_complainant_unit_label'] = _settled_incident_complainant_unit_label(log)
            row['incident_respondent_unit_label'] = _settled_incident_respondent_unit_label(log)
        cases_list = []
    else:
        include_incident_logs = filter_status == 'all'
        desk_cases = cases.order_by('-received_at', '-pk')[:_DESK_ACTIVE_ROW_LIMIT]
        desk_rows = _build_case_desk_rows(
            desk_cases,
            include_incident_logs=include_incident_logs,
            search_query=search_query,
            filter_type=filter_type,
            incident_limit=_SETTLED_INCIDENT_ROW_LIMIT if include_incident_logs else None,
            enrich=False,
        )
        if include_drawer_rows:
            _resolved_base = (
                Case.objects
                .filter(status=wf.STATUS_RESOLVED)
                .select_related(
                    'received_by', 'complainant_applicant', 'subject_applicant', 'related_unit',
                )
                .defer(*_CASE_LIST_DEFER)
            )
            if search_query or filter_type != 'all':
                _resolved_base = _apply_case_list_filters(_resolved_base, search_query, filter_type)
            resolved_cases = list(
                _resolved_base.order_by('-resolved_at', '-received_at')[:_DRAWER_CASE_LIST_LIMIT]
            )
            if load_pending_drawer:
                _pending_base = (
                    Case.objects
                    .filter(status=wf.STATUS_PENDING_REVIEW)
                    .select_related(
                        'received_by', 'complainant_applicant', 'subject_applicant', 'related_unit',
                    )
                    .defer(*_CASE_LIST_DEFER)
                )
                if search_query or filter_type != 'all':
                    _pending_base = _apply_case_list_filters(
                        _pending_base, search_query, filter_type,
                    )
                pending_cases = list(
                    _pending_base.order_by('-received_at')[:_DRAWER_CASE_LIST_LIMIT]
                )
        enrich_apps = _collect_applicants_from_cases(
            [row['case'] for row in desk_rows if row.get('case')]
        )
        enrich_apps += [
            row['incident_log'].complainant_applicant
            for row in desk_rows
            if row.get('incident_log')
        ]
        enrich_apps += [
            row['incident_log'].subject_applicant
            for row in desk_rows
            if row.get('incident_log')
        ]
        enrich_apps += _collect_applicants_from_cases(resolved_cases)
        enrich_apps += _collect_applicants_from_cases(pending_cases)
        _enrich_desk_applicants(enrich_apps)
        for row in desk_rows:
            if row.get('kind') == 'incident_log' and row.get('incident_log'):
                log = row['incident_log']
                row['incident_unit_label'] = _settled_incident_complainant_unit_label(log)
                row['incident_complainant_unit_label'] = _settled_incident_complainant_unit_label(log)
                row['incident_respondent_unit_label'] = _settled_incident_respondent_unit_label(log)
        cases_list = []

    ctx = {
        'cases': cases_list,
        'resolved_cases': list(resolved_cases),
        'pending_cases': list(pending_cases),
        'status_counts': status_counts,
        'search_query': search_query,
        'filter_status': filter_status,
        'filter_type': filter_type,
        'desk_rows': desk_rows,
        'can_delete_incident_logs': position in wf.FIELD_INSPECTOR_POSITIONS,
        'is_field_inspector': is_field_inspector,
        'use_split_case_desk': use_split_case_desk,
        'settled_incident_rows': settled_incident_rows,
        'settled_on_site_count': settled_on_site_count,
    }
    cache.set(_cache_key, ctx, 30)
    return ctx


@login_required
@require_http_methods(["GET"])
@verify_position
def case_management_dashboard(request, position):
    """
    Case Management Dashboard
    Displays all cases with search, filtering, and status tracking

    URL Route: /cases/<position>/

    Actors: All staff
    Purpose: Track complaints, disputes, and case resolutions
    """
    if request.GET.get('tab') == 'incident-log':
        params = request.GET.copy()
        params.pop('tab', None)
        if params.get('status', 'all') != 'all':
            params['status'] = 'all'
        query = params.urlencode()
        url = request.path + (f'?{query}' if query else '')
        return redirect(url)

    # Drawers lazy-loaded via desk-feed ?part= — keep initial HTML lean.
    list_ctx = _case_management_list_context(request, position, include_drawer_rows=False)
    prefer_mobile = _prefer_mobile_case_desk(request)

    prefill_beneficiary = None
    prefill_applicant_id = request.GET.get('applicant_id', '').strip()
    prefill_unit_id = request.GET.get('unit_id', '').strip()
    if prefill_applicant_id:
        try:
            applicant = Applicant.objects.get(id=prefill_applicant_id)
            prefill_beneficiary = _beneficiary_search_payload(applicant)
            if prefill_unit_id:
                prefill_beneficiary['unit_id'] = prefill_unit_id
        except Applicant.DoesNotExist:
            pass

    case_templates = {
        'ronda': 'field/case_management.html',
        'field': 'field/case_management.html',
        'second_member': 'staff/case_management.html',
        'fourth_member': 'staff/case_management.html',
    }
    template_name = case_templates.get(position, 'staff/case_management.html')

    context = {
        **list_ctx,
        'case_type_choices': Case.CASE_TYPE_CHOICES,
        'case_type_choices_intake_form': case_type_choices_for_monitor_intake_forms(),
        'case_type_choices_field_recording_form': case_type_choices_for_field_case_recording(),
        'open_new_case': request.GET.get('new_case', '').strip() in ('1', 'true', 'yes'),
        'open_case_id': request.GET.get('case_id', '').strip(),
        'prefill_beneficiary': prefill_beneficiary,
        'case_position': position,
        'case_desk_mode': wf.case_desk_mode_for_position(position),
        'field_intake_positions': tuple(wf.FIELD_INSPECTOR_POSITIONS),
        'monitor_intake_positions': tuple(wf.CASE_MONITOR_DESK_POSITIONS),
        'desk_feed_version': _case_desk_poll_version(request),
        'desk_render_mobile': prefer_mobile,
        'desk_render_table': not prefer_mobile,
        'drawers_lazy': True,
    }

    return render(request, template_name, context)

@login_required
@require_http_methods(["GET"])
@verify_position
def case_desk_feed(request, position):
    """JSON + HTML fragments for live desk list sync (field ⇔ monitor desks).

    Optimised for high-frequency polling:
    1. Cheap data-version stamp checked first — unchanged polls skip list_ctx entirely.
    2. ?part=resolved|settled|pending lazy-loads one drawer without full feed render.
    3. Full list payload cached 30s keyed by poll version.
    """
    current_version = _case_desk_poll_version(request)
    client_version = request.GET.get('v', '')
    part = (request.GET.get('part') or '').strip().lower()

    # Drawer fragment — always loads drawer rows; no unchanged short-circuit.
    if part in ('resolved', 'settled', 'pending'):
        if part == 'pending' and position in FIELD_INSPECTOR_POSITIONS:
            return JsonResponse({
                'success': True,
                'version': current_version,
                'part': part,
                'html': {'pending_drawer': ''},
            })
        list_ctx = _case_management_list_context(
            request, position, include_drawer_rows=True,
        )
        fragment_ctx = {
            **list_ctx,
            'show_time_ago': False,
            'can_delete_incident_logs': position in wf.FIELD_INSPECTOR_POSITIONS,
        }
        template_by_part = {
            'resolved': 'field/case_desk_resolved_drawer_inner.html',
            'settled': 'field/case_desk_settled_drawer_inner.html',
            'pending': 'field/case_desk_pending_drawer_inner.html',
        }
        html_key = f'{part}_drawer'
        return JsonResponse({
            'success': True,
            'version': current_version,
            'part': part,
            'html': {
                html_key: render_to_string(
                    template_by_part[part], fragment_ctx, request=request,
                ),
            },
            'status_counts': list_ctx['status_counts'],
            'settled_on_site_count': list_ctx.get('settled_on_site_count', 0),
        })

    # 1. Client version short-circuit — no list_ctx / no templates.
    if client_version and client_version == current_version:
        return JsonResponse({
            'success': True,
            'version': current_version,
            'unchanged': True,
        })

    # 2. Full payload cache — keyed by poll version (includes filters).
    prefer_mobile = _prefer_mobile_case_desk(request)
    _feed_cache_key = (
        f'case_desk_feed_v4_{position}_{current_version}'
        f'_{"m" if prefer_mobile else "d"}'
    )
    cached_payload = cache.get(_feed_cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    # 3. Cold path — list rows only (drawers lazy via ?part=).
    list_ctx = _case_management_list_context(
        request, position, include_drawer_rows=False,
    )
    fragment_ctx = {
        **list_ctx,
        'show_time_ago': False,
        'can_delete_incident_logs': position in wf.FIELD_INSPECTOR_POSITIONS,
    }
    html = {}
    if prefer_mobile and position in FIELD_INSPECTOR_POSITIONS:
        html['mobile_cards'] = render_to_string(
            'field/case_desk_mobile_cards.html',
            fragment_ctx,
            request=request,
        )
    else:
        html['table_body'] = render_to_string(
            'field/case_desk_unified_tbody.html',
            fragment_ctx,
            request=request,
        )
    payload = {
        'success': True,
        'version': current_version,
        'desk_row_count': len(list_ctx['desk_rows']),
        'status_counts': list_ctx['status_counts'],
        'settled_on_site_count': list_ctx.get('settled_on_site_count', 0),
        'html': html,
        'drawers_stale': True,
    }
    cache.set(_feed_cache_key, payload, 30)
    return JsonResponse(payload)


@login_required
@verify_position
def case_dashboard_redirect(request, position):
    """
    Legacy /cases/<position>/ entry — routes field desk and second member to accounts URLs.
    """
    accounts_routes = {
        'ronda': 'accounts:field_cases',
        'field': 'accounts:field_cases',
        'second_member': 'accounts:second_member_cases',
    }
    route = accounts_routes.get(position)
    if route:
        url = reverse(route)
        if request.GET:
            url = f'{url}?{request.GET.urlencode()}'
        return redirect(url)
    return case_management_dashboard(request, position)


def _prior_case_detail_payload(case):
    """Serialize a case row for prior-history lists in the view modal."""
    return {
        'id': str(case.id),
        'case_number': case.case_number,
        'status': wf.normalize_status(case.status),
        'status_display': case.get_status_display(),
        'case_type_display': case.get_case_type_display(),
        'initial_description': case.initial_description or '',
        'received_at': case.received_at.isoformat() if case.received_at else '',
    }


def _prior_cases_for_complainant(case, complainant_applicant, unit, limit=8):
    qs = Case.objects.exclude(id=case.id)
    if complainant_applicant:
        qs = qs.filter(complainant_applicant_id=complainant_applicant.id)
    elif unit:
        qs = qs.filter(related_unit=unit)
    else:
        return []
    return list(
        qs.only(
            'id', 'case_number', 'status', 'case_type', 'initial_description', 'received_at'
        ).order_by('-received_at')[:limit]
    )


def _prior_cases_for_respondent(case, subject_applicant, limit=8):
    """Other cases involving the respondent (as subject or as complainant)."""
    qs = Case.objects.exclude(id=case.id)
    if subject_applicant:
        qs = qs.filter(
            models.Q(subject_applicant_id=subject_applicant.id)
            | models.Q(complainant_applicant_id=subject_applicant.id)
        )
    elif (case.subject_name or '').strip():
        qs = qs.filter(subject_name__iexact=(case.subject_name or '').strip())
    else:
        return []
    return list(
        qs.only(
            'id', 'case_number', 'status', 'case_type', 'initial_description', 'received_at'
        ).order_by('-received_at')[:limit]
    )


def _subject_housing_unit(subject_applicant):
    if not subject_applicant:
        return None
    la = (
        LotAward.objects.filter(
            application__applicant=subject_applicant,
            status='active',
        )
        .select_related('unit')
        .order_by('-awarded_at')
        .first()
    )
    return la.unit if la else None


def _housing_unit_label(unit):
    if unit and unit.block_number and unit.lot_number:
        return f'Block {unit.block_number}, Lot {unit.lot_number}'
    return str(unit) if unit else ''


def _settled_incident_unit_label(log):
    """Complainant lot (stored on log.related_unit). Kept for backward compatibility."""
    return _settled_incident_complainant_unit_label(log)


def _settled_incident_complainant_unit_label(log):
    # Prefer select_related related_unit — avoids active_unit_label N+1.
    label = _housing_unit_label(log.related_unit)
    if label:
        return label
    if log.complainant_applicant_id and log.complainant_applicant:
        return (getattr(log.complainant_applicant, 'desk_unit_label', None) or '').strip()
    return ''


def _settled_incident_respondent_unit_label(log):
    if not _settled_incident_respondent_name(log):
        return ''
    if log.subject_applicant_id and log.subject_applicant:
        return (getattr(log.subject_applicant, 'desk_unit_label', None) or '').strip()
    return ''


def _parties_are_same_person(
    complainant_applicant_id,
    subject_applicant_id,
    complainant_name='',
    subject_name='',
):
    if complainant_applicant_id and subject_applicant_id:
        if str(complainant_applicant_id) == str(subject_applicant_id):
            return True
    cname = (complainant_name or '').strip().casefold()
    sname = (subject_name or '').strip().casefold()
    return bool(cname and sname and cname == sname)


def _settled_log_has_complainant_fields(log):
    return bool(log.complainant_applicant_id or (log.complainant_name or '').strip())


def _settled_incident_parties_same(log, complainant_name='', respondent_name=''):
    return _parties_are_same_person(
        log.complainant_applicant_id,
        log.subject_applicant_id,
        complainant_name,
        respondent_name,
    )


def _settled_incident_complainant_name(log):
    if _settled_log_has_complainant_fields(log):
        if log.complainant_applicant_id and log.complainant_applicant:
            return log.complainant_applicant.full_name or log.complainant_name or ''
        return (log.complainant_name or '').strip()
    if log.subject_applicant_id and log.subject_applicant:
        return log.subject_applicant.full_name or log.subject_name or ''
    return (log.subject_name or '').strip()


def _settled_incident_respondent_name(log):
    if not _settled_log_has_complainant_fields(log):
        return ''
    if log.subject_applicant_id and log.subject_applicant:
        respondent = log.subject_applicant.full_name or log.subject_name or ''
    else:
        respondent = (log.subject_name or '').strip()
    if not respondent:
        return ''
    complainant = _settled_incident_complainant_name(log)
    if _settled_incident_parties_same(log, complainant, respondent):
        return ''
    return respondent


def _filter_settled_incident_logs_queryset(qs, search_query, filter_type):
    if search_query:
        qs = qs.filter(
            models.Q(description__icontains=search_query)
            | models.Q(subject_name__icontains=search_query)
            | models.Q(related_unit__block_number__icontains=search_query)
            | models.Q(related_unit__lot_number__icontains=search_query)
            |             models.Q(subject_applicant__full_name__icontains=search_query)
            | models.Q(subject_applicant__reference_number__icontains=search_query)
            | models.Q(complainant_name__icontains=search_query)
            | models.Q(complainant_applicant__full_name__icontains=search_query)
            | models.Q(complainant_applicant__reference_number__icontains=search_query)
        )
    if filter_type != 'all':
        qs = qs.filter(case_type=filter_type)
    return qs


def _attach_desk_complaint_counts(applicants):
    """
    Batch-load complaint filed/received totals onto Applicant instances so list
    templates avoid per-row .count() N+1 queries.
    Sets: desk_complaints_filed, desk_complaints_received
    """
    apps = [a for a in applicants if a is not None and getattr(a, 'pk', None)]
    if not apps:
        return
    ids = list({a.pk for a in apps})

    filed = {
        row['complainant_applicant_id']: row['c']
        for row in Case.objects.filter(complainant_applicant_id__in=ids)
        .values('complainant_applicant_id')
        .annotate(c=models.Count('pk'))
    }
    against = {
        row['subject_applicant_id']: row['c']
        for row in Case.objects.filter(subject_applicant_id__in=ids)
        .values('subject_applicant_id')
        .annotate(c=models.Count('pk'))
    }
    settled_as_complainant = {
        row['complainant_applicant_id']: row['c']
        for row in FieldSettledIncidentLog.objects.filter(complainant_applicant_id__in=ids)
        .values('complainant_applicant_id')
        .annotate(c=models.Count('pk'))
    }
    settled_as_subject = {
        row['subject_applicant_id']: row['c']
        for row in FieldSettledIncidentLog.objects.filter(subject_applicant_id__in=ids)
        .values('subject_applicant_id')
        .annotate(c=models.Count('pk'))
    }

    for a in apps:
        pk = a.pk
        a.desk_complaints_filed = filed.get(pk, 0) + settled_as_complainant.get(pk, 0)
        a.desk_complaints_received = against.get(pk, 0) + settled_as_subject.get(pk, 0)


def _attach_desk_unit_labels(applicants):
    """
    Batch-load active housing-unit labels onto Applicant instances.
    Sets: desk_unit_label ('' when none). Avoids per-row active_unit_label N+1.
    """
    apps = [a for a in applicants if a is not None and getattr(a, 'pk', None)]
    if not apps:
        return
    ids = list({a.pk for a in apps})
    unit_by_applicant = {}
    for award in (
        LotAward.objects.filter(application__applicant_id__in=ids, status='active')
        .select_related('unit', 'application')
        .order_by('-awarded_at')
    ):
        aid = award.application.applicant_id
        if aid not in unit_by_applicant:
            unit_by_applicant[aid] = award.unit
    for a in apps:
        a.desk_unit_label = _housing_unit_label(unit_by_applicant.get(a.pk))


def _collect_applicants_from_cases(cases):
    apps = []
    for case in cases:
        if case.complainant_applicant_id and case.complainant_applicant:
            apps.append(case.complainant_applicant)
        if case.subject_applicant_id and case.subject_applicant:
            apps.append(case.subject_applicant)
    return apps


def _enrich_desk_applicants(applicants):
    """Batch complaint counts + unit labels for desk list templates."""
    apps = [a for a in applicants if a is not None]
    _attach_desk_complaint_counts(apps)
    _attach_desk_unit_labels(apps)


def _settled_incident_desk_rows(incident_qs, limit=None, enrich=True):
    """Build display rows for on-site settled incident logs (newest first)."""
    qs = incident_qs.order_by('-logged_at', '-pk')
    if limit is not None:
        qs = qs[:limit]
    logs = list(qs)
    if enrich:
        _enrich_desk_applicants(
            [log.complainant_applicant for log in logs] + [log.subject_applicant for log in logs]
        )
    rows = []
    for log in logs:
        rows.append({
            'kind': 'incident_log',
            'sort_at': log.logged_at,
            'case': None,
            'incident_log': log,
            'incident_unit_label': (
                _settled_incident_complainant_unit_label(log) if enrich else ''
            ),
            'incident_complainant_unit_label': (
                _settled_incident_complainant_unit_label(log) if enrich else ''
            ),
            'incident_respondent_unit_label': (
                _settled_incident_respondent_unit_label(log) if enrich else ''
            ),
            'incident_complainant_name': _settled_incident_complainant_name(log),
            'incident_respondent_name': _settled_incident_respondent_name(log),
        })
    return rows


def _apply_case_list_filters(qs, search_query, filter_type):
    if search_query:
        qs = qs.filter(
            models.Q(complainant_name__icontains=search_query)
            | models.Q(case_number__icontains=search_query)
            | models.Q(initial_description__icontains=search_query)
            | models.Q(subject_name__icontains=search_query)
            | models.Q(subject_applicant__full_name__icontains=search_query)
            | models.Q(complainant_applicant__full_name__icontains=search_query)
        )
    if filter_type != 'all':
        qs = qs.filter(case_type=filter_type)
    return qs


def _build_case_desk_rows(
    cases_qs,
    include_incident_logs,
    search_query,
    filter_type,
    incident_limit=None,
    enrich=True,
):
    """
    Merge formal cases and on-site settled incident logs for one desk list.
    Incident logs appear only when include_incident_logs is True (status filter = all).
    """
    case_list = list(cases_qs)
    if enrich:
        _enrich_desk_applicants(_collect_applicants_from_cases(case_list))
    rows = []
    for case in case_list:
        rows.append({
            'kind': 'case',
            'sort_at': case.received_at,
            'case': case,
            'incident_log': None,
        })
    if include_incident_logs:
        incident_qs = FieldSettledIncidentLog.objects.select_related(
            'related_unit', 'logged_by', 'subject_applicant', 'complainant_applicant',
        )
        incident_qs = _filter_settled_incident_logs_queryset(incident_qs, search_query, filter_type)
        rows.extend(
            _settled_incident_desk_rows(incident_qs, limit=incident_limit, enrich=enrich)
        )
    rows.sort(key=lambda row: row['sort_at'] or timezone.now())
    return rows


def _settled_incident_log_payload(log):
    complainant_unit_label = _settled_incident_complainant_unit_label(log)
    respondent_unit_label = _settled_incident_respondent_unit_label(log)
    return {
        'id': str(log.id),
        'case_type': log.case_type,
        'case_type_display': log.get_case_type_display(),
        'description': log.description,
        'subject_name': log.subject_name or '',
        'complainant_name': _settled_incident_complainant_name(log),
        'respondent_name': _settled_incident_respondent_name(log),
        'occupant_name': _settled_incident_complainant_name(log),
        'unit_label': respondent_unit_label or complainant_unit_label,
        'complainant_unit_label': complainant_unit_label,
        'respondent_unit_label': respondent_unit_label,
        'logged_at': log.logged_at.isoformat(),
        'logged_by': log.logged_by.get_full_name() if log.logged_by else 'Field',
    }


def _settled_incident_logs_for_subject(subject_applicant, unit=None, limit=10):
    q = models.Q()
    if subject_applicant:
        q |= models.Q(subject_applicant_id=subject_applicant.id)
    if unit:
        q |= models.Q(related_unit_id=unit.id)
    if not q:
        return []
    return list(
        FieldSettledIncidentLog.objects.filter(q)
        .select_related(
            'related_unit', 'logged_by', 'subject_applicant', 'complainant_applicant',
        )
        .order_by('-logged_at')[:limit]
    )


def _parse_block_lot_query(q):
    """Match housing map labels used on Unit Monitoring (e.g. 1-1, Block 1 Lot 1)."""
    text = (q or '').strip()
    m = re.match(r'^(\d+)\s*[-/]\s*(\d+)$', text)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r'(?i)^block\s*(\d+)\s*lot\s*(\d+)$', text)
    if m:
        return m.group(1), m.group(2)
    return None


def _beneficiary_search_payload_from_award(award):
    """Build JSON row from active lot award (same source as Housing Unit Monitoring)."""
    applicant = award.application.applicant
    unit = award.unit
    block = (unit.block_number or '').strip()
    lot = (unit.lot_number or '').strip()
    site_name = unit.site.name if unit.site_id else ''
    name = (applicant.full_name or unit.occupant_name or '').strip()
    ref = (applicant.reference_number or unit.occupant_id or '').strip()
    return {
        'id': str(applicant.id),
        'full_name': name,
        'reference_number': ref,
        'phone_number': (applicant.phone_number or '').strip(),
        'block': block,
        'lot': lot,
        'site_name': site_name,
        'unit_id': str(unit.id),
        'unit_label': f'Block {block} Lot {lot}' if block and lot else '',
        'lot_map_label': f'{block}-{lot}' if block and lot else '',
    }


def _beneficiary_search_payload(applicant):
    """Resolve housing-unit row for an applicant (fallback for create_case linking)."""
    la = (
        LotAward.objects.filter(
            application__applicant=applicant,
            status='active',
        )
        .select_related('application__applicant', 'unit', 'unit__site')
        .order_by('-awarded_at')
        .first()
    )
    if la:
        return _beneficiary_search_payload_from_award(la)
    return {
        'id': str(applicant.id),
        'full_name': applicant.full_name or '',
        'reference_number': applicant.reference_number or '',
        'phone_number': (applicant.phone_number or '').strip(),
        'block': '',
        'lot': '',
        'site_name': '',
        'unit_id': None,
        'unit_label': '',
        'lot_map_label': '',
    }


def _beneficiary_awards_queryset(q):
    """Active lot awards with housing units — same pool as Unit Monitoring."""
    qs = (
        LotAward.objects.filter(status='active', unit__isnull=False)
        .select_related('application__applicant', 'unit', 'unit__site')
    )
    if not q:
        return qs.order_by(
            'unit__block_number',
            'unit__lot_number',
            'application__applicant__full_name',
        )

    block_lot = _parse_block_lot_query(q)
    if block_lot:
        return qs.filter(
            unit__block_number=block_lot[0],
            unit__lot_number=block_lot[1],
        ).order_by(
            'unit__block_number',
            'unit__lot_number',
            'application__applicant__full_name',
        )

    text_filter = (
        models.Q(application__applicant__full_name__icontains=q)
        | models.Q(application__applicant__reference_number__icontains=q)
        | models.Q(application__applicant__phone_number__icontains=q)
        | models.Q(application__applicant__first_name__icontains=q)
        | models.Q(application__applicant__last_name__icontains=q)
        | models.Q(unit__occupant_name__icontains=q)
        | models.Q(unit__occupant_id__icontains=q)
    )
    qs = qs.filter(text_filter)
    for word in q.split():
        if len(word) < 2:
            continue
        qs = qs.filter(
            models.Q(application__applicant__full_name__icontains=word)
            | models.Q(application__applicant__first_name__icontains=word)
            | models.Q(application__applicant__last_name__icontains=word)
            | models.Q(unit__occupant_name__icontains=word)
        )
    return qs.order_by(
        'unit__block_number',
        'unit__lot_number',
        'application__applicant__full_name',
    )


@login_required
@require_http_methods(['GET'])
@verify_position
def beneficiary_search(request, position):
    """
    Search occupied housing-unit beneficiaries for case recording (Module 4 inventory).

    Same people shown on /units/housing-units/<position>/ — active LotAward + unit block/lot.
    Empty q returns the full occupant list (for pick-from-list UI).

    GET /cases/<position>/beneficiary-search/?q=
    """
    q = (request.GET.get('q') or '').strip()
    qs = _beneficiary_awards_queryset(q)
    max_results = 100 if not q else 25

    seen = set()
    results = []
    for award in qs[:max_results * 2]:
        app_id = award.application.applicant_id
        if app_id in seen:
            continue
        seen.add(app_id)
        results.append(_beneficiary_search_payload_from_award(award))
        if len(results) >= max_results:
            break

    return JsonResponse({
        'success': True,
        'results': results,
        'source': 'housing_units',
    })


@login_required
@require_http_methods(["GET"])
@verify_position
def get_case_details(request, position, case_id):
    """
    AJAX endpoint to fetch case details for modal display
    Returns JSON with case record details for the view modal

    URL Route: /cases/<position>/<case_id>/details/
    Cached for 30 seconds per case_id — eliminates 4+ DB round-trips per modal open.
    """
    _detail_cache_key = f'case_detail_{case_id}'
    _cached_payload = cache.get(_detail_cache_key)
    if _cached_payload is not None:
        return JsonResponse(_cached_payload)
    try:
        case = (
            Case.objects
            .select_related(
                'received_by',
                'investigated_by',
                'decided_by',
                'complainant_applicant',
                'subject_applicant',
                'related_unit',
                'related_unit__site',
            )
            .prefetch_related(
                'evidence__uploaded_by',
                'complainant_applicant__household_members',
                'subject_applicant__household_members',
                'actions__created_by',
            )
            .get(id=case_id)
        )

        evidence_data = []
        for ev in case.evidence.all():
            evidence_data.append({
                'id': str(ev.id),
                'caption': ev.caption or '',
                'url': ev.file.url if ev.file and ev.file.name else '',
                'uploaded_by': ev.uploaded_by.get_full_name() if ev.uploaded_by else 'Staff',
                'uploaded_at': ev.uploaded_at.isoformat(),
            })

        complainant_applicant = case.complainant_applicant
        subject_applicant = case.subject_applicant
        unit = case.related_unit
        prior_cases_list = _prior_cases_for_complainant(case, complainant_applicant, unit)
        prior_cases = [_prior_case_detail_payload(pc) for pc in prior_cases_list]

        respondent_prior_list = _prior_cases_for_respondent(case, subject_applicant)
        respondent_prior_cases = [_prior_case_detail_payload(pc) for pc in respondent_prior_list]
        subject_unit = _subject_housing_unit(subject_applicant) or case.related_unit
        respondent_settled_incident_logs = [
            _settled_incident_log_payload(log)
            for log in _settled_incident_logs_for_subject(subject_applicant, subject_unit)
        ]

        beneficiary_profile = None
        if complainant_applicant:
            beneficiary_profile = {
                'applicant_id': str(complainant_applicant.id),
                'sex_display': (
                    complainant_applicant.get_sex_display()
                    if complainant_applicant.sex
                    else '—'
                ),
                'household_members': complainant_applicant.household_member_count,
                'household_member_rows': [
                    {
                        'name': member.full_name,
                        'relationship': member.get_relationship_display(),
                        'sex_display': (
                            member.get_sex_display() if member.sex else '—'
                        ),
                    }
                    # sorted() uses prefetch cache; .order_by() would fire a new query.
                    for member in sorted(
                        complainant_applicant.household_members.all(),
                        key=lambda m: m.created_at,
                    )
                ],
            }

        subject_profile = None
        if subject_applicant:
            subject_profile = {
                'applicant_id': str(subject_applicant.id),
                'sex_display': (
                    subject_applicant.get_sex_display()
                    if subject_applicant.sex
                    else '—'
                ),
                'household_members': subject_applicant.household_member_count,
                'household_member_rows': [
                    {
                        'name': member.full_name,
                        'relationship': member.get_relationship_display(),
                        'sex_display': (
                            member.get_sex_display() if member.sex else '—'
                        ),
                    }
                    # sorted() uses prefetch cache; .order_by() would fire a new query.
                    for member in sorted(
                        subject_applicant.household_members.all(),
                        key=lambda m: m.created_at,
                    )
                ],
            }

        actions_log = [
            {
                'action_type': row.action_type,
                'label': wf.ACTION_LABELS.get(row.action_type, row.get_action_type_display()),
                'details': row.details or '',
                'created_by': row.created_by.get_full_name() if row.created_by else 'Staff',
                'created_at': row.created_at.isoformat(),
            }
            for row in case.actions.all()
        ]
        can_manage = wf.user_can_manage_workflow(request.user)
        can_upload_evidence = wf.user_can_upload_case_evidence(request.user)
        is_monitor_desk = wf.user_is_case_monitor_desk(request.user)
        case_status = wf.normalize_status(case.status)
        _did_auto_transition = False
        if (
            wf.user_can_field_mark_under_review(request.user)
            and case_status == wf.STATUS_UNDER_REVIEW
            and case.field_intake_reviewed_at
            and wf.can_transition(case, 'enter_monitoring')
        ):
            wf.apply_transition(case, 'enter_monitoring')
            case.save(update_fields=['status', 'updated_at'])
            case_status = wf.normalize_status(case.status)
            _did_auto_transition = True
            # Invalidate stale cache entry after state change.
            cache.delete(_detail_cache_key)
            _bump_case_desk_data_version()

        workflow_payload = {
            'can_manage_workflow': can_manage,
            'can_upload_evidence': can_upload_evidence,
            'can_upload_intake_evidence': (
                wf.user_can_upload_case_intake_evidence(request.user)
                and case_status not in (wf.STATUS_RESOLVED, wf.STATUS_CLOSED)
            ),
            'is_monitor_desk': is_monitor_desk,
            'needs_auto_start_review': (
                wf.user_can_field_mark_under_review(request.user)
                and case_status == wf.STATUS_PENDING_REVIEW
            ),
            'can_mark_reviewed': (
                wf.user_can_field_mark_under_review(request.user)
                and case_status == wf.STATUS_UNDER_REVIEW
                and not case.field_intake_reviewed_at
            ),
            'show_case_carousel': (
                bool(case.field_intake_reviewed_at)
                and case_status in (wf.STATUS_MEDIATION, wf.STATUS_RESOLVED)
            ),
            'allowed_actions': wf.allowed_type_actions(case.case_type) if can_manage else [],
            'workflow_buttons': wf.allowed_workflow_buttons(case, request.user) if can_manage else [],
            'type_action_guide': wf.type_action_guide(case.case_type),
            'show_engineering_note': wf.normalize_case_type(case.case_type) == 'lot_boundary',
            'monitoring_alerts': wf.monitoring_alerts(case, len(prior_cases_list)),
            'actions_log': actions_log,
            'is_terminal': wf.normalize_status(case.status) in wf.TERMINAL_STATUSES,
        }

        _response_payload = {
            'success': True,
            'case': {
                'id': str(case.id),
                'case_number': case.case_number,
                'status': wf.normalize_status(case.status),
                'status_display': case.get_status_display(),
                'case_type': case.case_type,
                'case_type_display': case.get_case_type_display(),
                'received_at': case.received_at.isoformat(),
                'received_by': case.received_by.get_full_name() if case.received_by else 'Unknown',
                'received_by_position': (
                    case.received_by.get_position_display() if case.received_by else ''
                ),
                'received_by_position_key': (
                    case.received_by.position if case.received_by else ''
                ),
                'received_by_initials': (
                    f'{case.received_by.first_name[:1]}{case.received_by.last_name[:1]}'.upper()
                    if case.received_by and case.received_by.first_name and case.received_by.last_name
                    else ''
                ),
                'complainant_name': case.complainant_name,
                'complainant_phone': case.complainant_phone or '',
                'complainant_reference': (
                    complainant_applicant.reference_number if complainant_applicant else ''
                ),
                'complainant_unit_label': (
                    f'Block {unit.block_number}, Lot {unit.lot_number}'
                    if unit and unit.block_number and unit.lot_number
                    else (str(unit) if unit else '')
                ),
                'subject_name': case.subject_name or '',
                'subject_phone': subject_applicant.phone_number if subject_applicant else '',
                'subject_reference': (
                    subject_applicant.reference_number if subject_applicant else ''
                ),
                'subject_unit_label': (
                    f'Block {subject_unit.block_number}, Lot {subject_unit.lot_number}'
                    if subject_unit and subject_unit.block_number and subject_unit.lot_number
                    else (str(subject_unit) if subject_unit else '')
                ),
                'initial_description': case.initial_description,
                'investigation_notes': case.investigation_notes or '',
                'investigated_by': case.investigated_by.get_full_name() if case.investigated_by else '',
                'investigated_at': case.investigated_at.isoformat() if case.investigated_at else None,
                'referred_to': case.referred_to or '',
                'referred_at': case.referred_at.isoformat() if case.referred_at else None,
                'referral_notes': case.referral_notes or '',
                'resolution_notes': case.resolution_notes or '',
                'decided_by': case.decided_by.get_full_name() if case.decided_by else '',
                'decided_at': case.decided_at.isoformat() if case.decided_at else None,
                'resolved_at': case.resolved_at.isoformat() if case.resolved_at else None,
                'field_settlement_outcome': case.field_settlement_outcome or '',
                'field_settlement_outcome_display': (
                    case.get_field_settlement_outcome_display()
                    if case.field_settlement_outcome
                    else ''
                ),
                'field_settlement_saved_at': (
                    case.field_settlement_saved_at.isoformat()
                    if case.field_settlement_saved_at
                    else None
                ),
                'related_unit': str(case.related_unit) if case.related_unit else None,
                'days_open': case.days_open,
                'is_stale': case.is_stale,
                'evidence': evidence_data,
                'prior_cases': prior_cases,
                'prior_cases_count': len(prior_cases_list),
                'respondent_prior_cases': respondent_prior_cases,
                'respondent_prior_cases_count': len(respondent_prior_list),
                'respondent_settled_incident_logs': respondent_settled_incident_logs,
                'respondent_settled_incident_logs_count': len(respondent_settled_incident_logs),
                'beneficiary_profile': beneficiary_profile,
                'subject_profile': subject_profile,
                'workflow': workflow_payload,
                'received_at_location_display': case.get_received_at_location_display(),
            }
        }
        # Cache for 30s — skipped when auto-transition fired (state just changed).
        if not _did_auto_transition:
            cache.set(_detail_cache_key, _response_payload, 30)
        return JsonResponse(_response_payload)

    except Case.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Case not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
@verify_position
def create_case(request, position):
    """
    AJAX endpoint to log a new case

    URL Route: /cases/<position>/create/

    POST data:
    - complainant_name: str
    - complainant_phone: str (optional)
    - case_type: case type code
    - received_at_location: 'office' | 'onsite'
    - initial_description: str
    - subject_name: str (required — linked beneficiary)
    """
    try:
        data = json.loads(request.body)

        complainant_name = data.get('complainant_name', '').strip()
        complainant_phone = data.get('complainant_phone', '').strip()
        case_type = data.get('case_type', '').strip()
        received_at_location = data.get('received_at_location', 'office').strip()
        initial_description = data.get('initial_description', '').strip()
        subject_name = data.get('subject_name', '').strip()
        complainant_applicant_id = (data.get('complainant_applicant_id') or '').strip()
        subject_applicant_id = (data.get('subject_applicant_id') or '').strip()
        related_unit_id = (data.get('related_unit_id') or '').strip()
        # Normalize legacy type codes from old forms
        case_type = wf.LEGACY_TYPE_MAP.get(case_type, case_type)

        is_illegal_occupant = case_type == 'illegal_occupant'

        if is_illegal_occupant:
            if not subject_applicant_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Select the beneficiary for this illegal occupant concern.',
                }, status=400)
            complainant_applicant_id = ''
            if not complainant_name:
                complainant_name = 'THA Field Office'
        else:
            if not complainant_applicant_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Select a complainant from the housing unit occupant list.',
                }, status=400)
            if not subject_applicant_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Select a reported party from the housing unit occupant list.',
                }, status=400)
            if _parties_are_same_person(
                complainant_applicant_id,
                subject_applicant_id,
                complainant_name,
                subject_name,
            ):
                return JsonResponse({
                    'success': False,
                    'error': 'Reported party cannot be the same person as the complainant.',
                }, status=400)

        if not all([complainant_name, case_type, initial_description]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        if len(initial_description) > 100:
            return JsonResponse({
                'success': False,
                'error': 'Incident description must be 100 characters or less.',
            }, status=400)

        valid_types = _valid_case_types_for_create(position)
        if case_type not in valid_types:
            return JsonResponse({
                'success': False,
                'error': 'Invalid case type'
            }, status=400)

        complainant_applicant = None
        subject_applicant = None
        related_unit = None
        if complainant_applicant_id:
            complainant_applicant = get_object_or_404(Applicant, id=complainant_applicant_id)
            if not complainant_name:
                complainant_name = complainant_applicant.full_name or complainant_name
            if not complainant_phone:
                complainant_phone = (complainant_applicant.phone_number or '').strip()
        if subject_applicant_id:
            subject_applicant = get_object_or_404(Applicant, id=subject_applicant_id)
            if not subject_name:
                subject_name = subject_applicant.full_name or subject_name
        if related_unit_id:
            related_unit = get_object_or_404(HousingUnit, id=related_unit_id)
        else:
            unit_applicant = subject_applicant if is_illegal_occupant else complainant_applicant
            if unit_applicant:
                la = (
                    LotAward.objects.filter(
                        application__applicant=unit_applicant,
                        status='active',
                    )
                    .select_related('unit')
                    .order_by('-awarded_at')
                    .first()
                )
                if la:
                    related_unit = la.unit

        case = Case.objects.create(
            complainant_name=complainant_name,
            complainant_phone=complainant_phone,
            case_type=case_type,
            status=wf.STATUS_PENDING_REVIEW,
            received_at_location=received_at_location,
            initial_description=initial_description,
            subject_name=subject_name,
            received_by=request.user,
            complainant_applicant=complainant_applicant,
            subject_applicant=subject_applicant,
            related_unit=related_unit,
        )
        # Case recording (Add Case) always starts at Pending Review — never skip to mediation.
        if wf.normalize_status(case.status) != wf.STATUS_PENDING_REVIEW:
            case.status = wf.STATUS_PENDING_REVIEW
            case.save(update_fields=['status'])

        _bump_case_desk_data_version()
        return JsonResponse({
            'success': True,
            'message': (
                f'✓ Case {case.case_number} saved. '
                f'Status: {case.get_status_display()}.'
            ),
            'case': {
                'id': str(case.id),
                'case_number': case.case_number,
                'complainant_name': case.complainant_name,
                'status': case.status,
                'status_display': case.get_status_display(),
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
@verify_position
def create_settled_incident_log(request, position):
    """
    Field desk only — log an on-site incident settled without opening a formal case.
    """
    if position not in wf.FIELD_INSPECTOR_POSITIONS:
        return JsonResponse({'success': False, 'error': 'Field inspector only.'}, status=403)
    try:
        data = json.loads(request.body)
        related_unit_id = (data.get('related_unit_id') or '').strip()
        case_type = (data.get('case_type') or '').strip()
        description = (data.get('description') or '').strip()
        complainant_applicant_id = (data.get('complainant_applicant_id') or '').strip()
        complainant_name = (data.get('complainant_name') or '').strip()
        complainant_phone = (data.get('complainant_phone') or '').strip()
        subject_applicant_id = (data.get('subject_applicant_id') or '').strip()
        subject_name = (data.get('subject_name') or '').strip()
        case_type = wf.LEGACY_TYPE_MAP.get(case_type, case_type)

        if not related_unit_id:
            return JsonResponse({'success': False, 'error': 'Select a complainant with a housing unit.'}, status=400)
        if not case_type:
            return JsonResponse({
                'success': False,
                'error': 'Select a complaint type.',
            }, status=400)
        if not description:
            return JsonResponse({'success': False, 'error': 'Description is required.'}, status=400)
        if len(description) > 150:
            return JsonResponse({
                'success': False,
                'error': 'Description must be 150 characters or less.',
            }, status=400)

        valid_types = _valid_case_types_for_create(position, settled_log=True)
        if case_type not in valid_types:
            return JsonResponse({'success': False, 'error': 'Invalid case type.'}, status=400)

        related_unit = get_object_or_404(HousingUnit, id=related_unit_id)
        complainant_applicant = None
        if complainant_applicant_id:
            complainant_applicant = get_object_or_404(Applicant, id=complainant_applicant_id)
            if not complainant_name:
                complainant_name = complainant_applicant.full_name or ''
            if not complainant_phone:
                complainant_phone = getattr(complainant_applicant, 'phone_number', '') or ''
        if not complainant_applicant_id:
            return JsonResponse({
                'success': False,
                'error': 'Select a complainant from the beneficiary search.',
            }, status=400)
        if not complainant_name:
            return JsonResponse({
                'success': False,
                'error': 'Select a complainant from the beneficiary search.',
            }, status=400)
        if not subject_applicant_id:
            return JsonResponse({
                'success': False,
                'error': 'Select a reported party from the beneficiary search.',
            }, status=400)

        if _parties_are_same_person(
            complainant_applicant_id,
            subject_applicant_id,
            complainant_name,
            subject_name,
        ):
            return JsonResponse({
                'success': False,
                'error': 'Reported party cannot be the same person as the complainant.',
            }, status=400)

        subject_applicant = None
        if subject_applicant_id:
            subject_applicant = get_object_or_404(Applicant, id=subject_applicant_id)
            if not subject_name:
                subject_name = subject_applicant.full_name or ''

        log = FieldSettledIncidentLog.objects.create(
            related_unit=related_unit,
            complainant_applicant=complainant_applicant,
            complainant_name=complainant_name,
            complainant_phone=complainant_phone,
            subject_applicant=subject_applicant,
            subject_name=subject_name,
            case_type=case_type,
            description=description,
            logged_by=request.user,
        )
        _bump_case_desk_data_version()
        return JsonResponse({
            'success': True,
            'message': 'Settled incident logged.',
            'log': _settled_incident_log_payload(log),
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
@verify_position
def delete_settled_incident_log(request, position, log_id):
    """Field desk only — remove an on-site settled incident log entry."""
    if position not in wf.FIELD_INSPECTOR_POSITIONS:
        return JsonResponse({'success': False, 'error': 'Field inspector only.'}, status=403)
    try:
        log = FieldSettledIncidentLog.objects.get(id=log_id)
        log.delete()
        _bump_case_desk_data_version()
        return JsonResponse({'success': True, 'message': 'Incident log removed.'})
    except FieldSettledIncidentLog.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Incident log not found.'}, status=404)


@login_required
@require_POST
@verify_position
def upload_case_evidence(request, position, case_id):
    """Upload optional intake photo/document for a case."""
    if not wf.user_can_upload_case_intake_evidence(request.user):
        return JsonResponse({
            'success': False,
            'error': 'You do not have permission to upload case evidence.',
        }, status=403)
    case = get_object_or_404(Case, id=case_id)
    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'success': False, 'error': 'No file uploaded.'}, status=400)
    if upload.size > 6 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'File must be 6 MB or smaller.'}, status=400)

    allowed = ('image/jpeg', 'image/png', 'image/webp')
    type_error = 'Allowed types: JPEG, PNG, or WebP photos only.'
    if getattr(upload, 'content_type', '') not in allowed:
        return JsonResponse({'success': False, 'error': type_error}, status=400)

    caption = (request.POST.get('caption') or '').strip()[:255]
    evidence = CaseEvidence.objects.create(
        case=case,
        file=upload,
        caption=caption,
        uploaded_by=request.user,
    )
    return JsonResponse({
        'success': True,
        'message': 'Evidence uploaded.',
        'evidence': {
            'id': str(evidence.id),
            'caption': evidence.caption,
            'url': evidence.file.url if evidence.file and evidence.file.name else '',
            'uploaded_by': request.user.get_full_name() or 'Staff',
            'uploaded_at': evidence.uploaded_at.isoformat(),
        },
    })


@login_required
@require_POST
@verify_position
def save_field_settlement(request, position, case_id):
    """Field desk: save settlement outcome, optional photo, and status."""
    if not wf.user_can_upload_case_evidence(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Settlement is handled at the field desk.',
        }, status=403)
    case = get_object_or_404(Case, id=case_id)
    case_status = wf.normalize_status(case.status)
    if not case.field_intake_reviewed_at:
        return JsonResponse({
            'success': False,
            'error': 'Mark the case reviewed before saving settlement.',
        }, status=400)
    if case_status not in (wf.STATUS_MEDIATION, wf.STATUS_RESOLVED):
        return JsonResponse({
            'success': False,
            'error': 'Case must be in Settlement before saving.',
        }, status=400)

    outcome = (request.POST.get('settlement_outcome') or 'settled').strip()
    if outcome not in ('settled', 'not_settled'):
        return JsonResponse({
            'success': False,
            'error': 'Invalid settlement outcome.',
        }, status=400)

    caption = (request.POST.get('caption') or 'Field settlement photograph').strip()[:255]
    uploads = list(request.FILES.getlist('files'))
    single = request.FILES.get('file')
    if single:
        uploads.insert(0, single)

    if outcome == 'settled' and not uploads:
        return JsonResponse({
            'success': False,
            'error': 'Add at least one settlement photograph before marking resolved.',
        }, status=400)

    allowed = ('image/jpeg', 'image/png', 'image/webp')
    for upload in uploads[:4]:
        if upload.size > 6 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File must be 6 MB or smaller.'}, status=400)
        if getattr(upload, 'content_type', '') not in allowed:
            return JsonResponse({
                'success': False,
                'error': 'Allowed types: JPEG, PNG, or WebP photos only.',
            }, status=400)
        CaseEvidence.objects.create(
            case=case,
            file=upload,
            caption=caption,
            uploaded_by=request.user,
        )

    case.field_settlement_outcome = outcome
    case.field_settlement_saved_at = timezone.now()
    case.decided_by = request.user
    case.decided_at = timezone.now()

    if outcome == 'settled':
        case.status = wf.STATUS_RESOLVED
        case.resolved_at = timezone.now()
        case.resolution_notes = caption or 'Settled during field settlement visit.'
    else:
        case.status = wf.STATUS_MEDIATION
        follow_note = caption or 'Not settled — follow-up required.'
        if case.investigation_notes:
            case.investigation_notes = f'{case.investigation_notes}\n{follow_note}'
        else:
            case.investigation_notes = follow_note

    case.save()

    _bump_case_desk_data_version()
    if outcome == 'settled':
        message = 'Case marked resolved.'
    else:
        message = 'Settlement saved (Not settled).'
    return JsonResponse({
        'success': True,
        'message': message,
        'new_status': case.status,
        'status_display': case.get_status_display(),
        'field_settlement_outcome': outcome,
    })


@login_required
@require_POST
@verify_position
def update_case(request, position):
    """
    Workflow updates: review, type actions, status transitions, close.

    POST action:
    - start_review, save_review, record_action, workflow_transition
    - resolve, close
    """
    try:
        data = json.loads(request.body)

        case_id = data.get('case_id')
        action = data.get('action', '').strip()

        case = Case.objects.get(id=case_id)
        transition_key = (data.get('transition') or '').strip()
        field_review_only = (
            wf.user_can_field_mark_under_review(request.user)
            and not wf.user_can_manage_workflow(request.user)
        )
        if field_review_only and action not in (
            'start_review', 'mark_field_reviewed', 'workflow_transition',
        ):
            return JsonResponse({
                'success': False,
                'error': 'Field desk cannot perform that update.',
            }, status=403)
        if field_review_only and action == 'workflow_transition' and transition_key != 'start_review':
            return JsonResponse({
                'success': False,
                'error': 'Field desk cannot perform that update.',
            }, status=403)
        if not wf.user_can_manage_workflow(request.user) and not wf.user_can_field_mark_under_review(request.user):
            return JsonResponse({
                'success': False,
                'error': 'This desk is view-only for case monitoring. New complaints are filed at the field desk.',
            }, status=403)

        if action == 'start_review':
            if not wf.can_transition(case, 'start_review'):
                return JsonResponse({'success': False, 'error': 'Cannot start review from current status.'}, status=400)
            wf.apply_transition(case, 'start_review')
            case.investigated_by = request.user
            case.investigated_at = timezone.now()
            case.save()
            _bump_case_desk_data_version()
            return JsonResponse({
                'success': True,
                'message': 'Case is now Under Review',
                'new_status': case.status,
                'status_display': case.get_status_display(),
            })

        elif action == 'mark_field_reviewed':
            if wf.normalize_status(case.status) != wf.STATUS_UNDER_REVIEW:
                return JsonResponse({
                    'success': False,
                    'error': 'Case must be Under Review before marking reviewed.',
                }, status=400)
            if not case.field_intake_reviewed_at:
                case.field_intake_reviewed_at = timezone.now()
            if wf.can_transition(case, 'enter_monitoring'):
                wf.apply_transition(case, 'enter_monitoring')
            case.save(update_fields=['field_intake_reviewed_at', 'status', 'updated_at'])
            _bump_case_desk_data_version()
            return JsonResponse({
                'success': True,
                'message': 'Case is now in Settlement.',
                'show_case_carousel': True,
                'new_status': case.status,
                'status_display': case.get_status_display(),
            })

        elif action == 'save_review':
            review_notes = data.get('review_notes', '').strip()
            if not review_notes:
                return JsonResponse({'success': False, 'error': 'Review notes required.'}, status=400)
            if wf.normalize_status(case.status) not in (
                wf.STATUS_UNDER_REVIEW,
                wf.STATUS_MEDIATION,
                wf.STATUS_REFERRED_ENGINEERING,
                wf.STATUS_AWAITING_RESPONSE,
                wf.STATUS_PENDING_REVIEW,
            ):
                return JsonResponse({'success': False, 'error': 'Begin review before saving review notes.'}, status=400)
            case.investigation_notes = review_notes
            case.investigated_by = request.user
            case.investigated_at = timezone.now()
            case.save()
            _bump_case_desk_data_version()
            return JsonResponse({'success': True, 'message': 'Review notes saved'})

        elif action == 'record_action':
            if wf.normalize_status(case.status) == wf.STATUS_PENDING_REVIEW:
                return JsonResponse({
                    'success': False,
                    'error': (
                        'Case is still pending review. Mark it under review before '
                        'recording warnings, mediation, or other desk actions.'
                    ),
                }, status=400)
            action_type = data.get('action_type', '').strip()
            details = data.get('details', '').strip()
            follow_up_at = (data.get('follow_up_at') or '').strip()
            allowed_codes = {a['code'] for a in wf.allowed_type_actions(case.case_type)}
            allowed_codes |= set(wf.ACTION_LABELS.keys())  # legacy stored actions
            if action_type not in allowed_codes:
                return JsonResponse({'success': False, 'error': 'Action not allowed for this complaint type.'}, status=400)
            if action_type == wf.ACTION_REFER_ENGINEERING and not wf.refer_engineering_allowed(case):
                return JsonResponse({
                    'success': False,
                    'error': 'Refer to City Engineering is only available for Lot Boundary issues.',
                }, status=400)

            CaseAction.objects.create(
                case=case,
                action_type=action_type,
                details=details,
                created_by=request.user,
            )
            label = wf.ACTION_LABELS.get(action_type, action_type)

            try:
                wf.apply_action_status(case, action_type)
            except ValueError as exc:
                return JsonResponse({'success': False, 'error': str(exc)}, status=400)
            if action_type == wf.ACTION_REFER_ENGINEERING:
                case.referral_notes = details

            if follow_up_at:
                from datetime import datetime
                try:
                    case.follow_up_at = datetime.strptime(follow_up_at, '%Y-%m-%d').date()
                except ValueError:
                    pass

            case.save()
            _bump_case_desk_data_version()
            return JsonResponse({
                'success': True,
                'message': label,
                'new_status': case.status,
                'status_display': case.get_status_display(),
            })

        elif action == 'workflow_transition':
            transition = data.get('transition', '').strip()
            if transition == 'resolve':
                resolution_notes = data.get('resolution_notes', '').strip()
                if not resolution_notes:
                    return JsonResponse({'success': False, 'error': 'Resolution outcome required.'}, status=400)
                case.status = wf.STATUS_RESOLVED
                case.resolution_notes = resolution_notes
                case.decided_by = request.user
                case.decided_at = timezone.now()
                case.resolved_at = timezone.now()
                case.save()
                _bump_case_desk_data_version()
                return JsonResponse({'success': True, 'message': 'Case marked resolved', 'new_status': case.status})
            if transition == 'close':
                closure_outcome = data.get('closure_outcome', '').strip()
                if wf.normalize_status(case.status) != wf.STATUS_RESOLVED:
                    return JsonResponse({'success': False, 'error': 'Resolve the case before closing.'}, status=400)
                if not closure_outcome:
                    return JsonResponse({'success': False, 'error': 'Closure outcome required.'}, status=400)
                case.status = wf.STATUS_CLOSED
                case.closure_outcome = closure_outcome
                case.save()
                _bump_case_desk_data_version()
                return JsonResponse({'success': True, 'message': 'Case archived (closed)', 'new_status': case.status})
            if not wf.can_transition(case, transition):
                return JsonResponse({'success': False, 'error': 'Invalid workflow transition.'}, status=400)
            wf.apply_transition(case, transition)
            if transition == 'start_review':
                case.investigated_by = request.user
                case.investigated_at = timezone.now()
            case.save()
            _bump_case_desk_data_version()
            return JsonResponse({
                'success': True,
                'message': case.get_status_display(),
                'new_status': case.status,
            })

        elif action == 'resolve':
            resolution_notes = data.get('resolution_notes', '').strip()
            if not resolution_notes:
                return JsonResponse({'success': False, 'error': 'Resolution outcome required.'}, status=400)
            if not wf.can_transition(case, 'resolve') and wf.normalize_status(case.status) not in wf.WORKFLOW_TRANSITIONS['resolve']['from']:
                return JsonResponse({'success': False, 'error': 'Case cannot be resolved from current status.'}, status=400)
            case.status = wf.STATUS_RESOLVED
            case.resolution_notes = resolution_notes
            case.decided_by = request.user
            case.decided_at = timezone.now()
            case.resolved_at = timezone.now()
            case.save()
            _bump_case_desk_data_version()
            return JsonResponse({
                'success': True,
                'message': 'Case marked resolved',
                'new_status': 'resolved',
            })

        elif action == 'close':
            closure_outcome = data.get('closure_outcome', '').strip()
            if wf.normalize_status(case.status) != wf.STATUS_RESOLVED:
                return JsonResponse({'success': False, 'error': 'Resolve the case before closing.'}, status=400)
            if not closure_outcome:
                return JsonResponse({'success': False, 'error': 'Closure outcome required.'}, status=400)
            case.status = wf.STATUS_CLOSED
            case.closure_outcome = closure_outcome
            case.save()
            _bump_case_desk_data_version()
            return JsonResponse({
                'success': True,
                'message': 'Case archived (closed)',
                'new_status': 'closed',
            })

        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            }, status=400)

    except Case.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Case not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
