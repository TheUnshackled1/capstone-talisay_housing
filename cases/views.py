from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.db import models
from django.utils import timezone
from functools import wraps
import json
import re
from urllib.parse import urlencode

from intake.models import Applicant
from units.models import LotAward, HousingUnit
from .models import Case, CaseAction, CaseEvidence
from . import workflow as wf
from accounts.models import FIELD_DESK_POSITIONS


def cases_page_url(position, **query):
    """Canonical Module 5 page URL for a staff position (accounts routes or legacy /cases/)."""
    if position in FIELD_DESK_POSITIONS:
        base = reverse('accounts:field_cases')
    elif position in ('second_member', 'fourth_member'):
        base = reverse('accounts:second_member_cases')
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

    # Get all cases with related data
    cases = (
        Case.objects
        .select_related('received_by', 'investigated_by', 'decided_by', 'complainant_applicant', 'subject_applicant', 'related_unit')
        .order_by('-received_at')
    )

    status_counts = {
        'pending_review': cases.filter(status=wf.STATUS_PENDING_REVIEW).count(),
        'under_review': cases.filter(status=wf.STATUS_UNDER_REVIEW).count(),
        'mediation_monitoring': cases.filter(status=wf.STATUS_MEDIATION).count(),
        'awaiting_response': cases.filter(status=wf.STATUS_AWAITING_RESPONSE).count(),
        'referred_engineering': cases.filter(status=wf.STATUS_REFERRED_ENGINEERING).count(),
        'resolved': cases.filter(status=wf.STATUS_RESOLVED).count(),
        'closed': cases.filter(status=wf.STATUS_CLOSED).count(),
    }

    resolved_cases = (
        Case.objects
        .filter(status=wf.STATUS_RESOLVED)
        .select_related('received_by', 'complainant_applicant')
        .order_by('-resolved_at', '-received_at')
    )

    # Search and filter
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', 'all')
    filter_type = request.GET.get('type', 'all')

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

    open_new_case = request.GET.get('new_case', '').strip() in ('1', 'true', 'yes')
    open_case_id = request.GET.get('case_id', '').strip()

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
        'ronda': 'accounts/field/case_management.html',
        'field': 'accounts/field/case_management.html',
        'second_member': 'accounts/second_member/case_management.html',
        'fourth_member': 'accounts/second_member/case_management.html',
    }
    template_name = case_templates.get(position, 'accounts/second_member/case_management.html')

    context = {
        'cases': cases,
        'resolved_cases': resolved_cases,
        'status_counts': status_counts,
        'search_query': search_query,
        'filter_status': filter_status,
        'filter_type': filter_type,
        'case_type_choices': Case.CASE_TYPE_CHOICES,
        'open_new_case': open_new_case,
        'open_case_id': open_case_id,
        'prefill_beneficiary': prefill_beneficiary,
        'case_position': position,
        'case_desk_mode': wf.case_desk_mode_for_position(position),
        'field_intake_positions': tuple(wf.FIELD_DESK_POSITIONS),
        'monitor_intake_positions': tuple(wf.CASE_MONITOR_DESK_POSITIONS),
    }

    return render(request, template_name, context)


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
    return list(qs.order_by('-received_at')[:limit])


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
    return list(qs.order_by('-received_at')[:limit])


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
    """
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
                'actions__created_by',
            )
            .get(id=case_id)
        )

        evidence_data = []
        for ev in case.evidence.all():
            evidence_data.append({
                'id': str(ev.id),
                'caption': ev.caption or '',
                'url': request.build_absolute_uri(ev.file.url) if ev.file else '',
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
                    for member in complainant_applicant.household_members.all().order_by(
                        'created_at'
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
        if (
            wf.user_can_field_mark_under_review(request.user)
            and case_status == wf.STATUS_UNDER_REVIEW
            and case.field_intake_reviewed_at
            and wf.can_transition(case, 'enter_monitoring')
        ):
            wf.apply_transition(case, 'enter_monitoring')
            case.save(update_fields=['status', 'updated_at'])
            case_status = wf.normalize_status(case.status)

        workflow_payload = {
            'can_manage_workflow': can_manage,
            'can_upload_evidence': can_upload_evidence,
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

        return JsonResponse({
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
                'subject_reference': (
                    subject_applicant.reference_number if subject_applicant else ''
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
                'beneficiary_profile': beneficiary_profile,
                'workflow': workflow_payload,
                'received_at_location_display': case.get_received_at_location_display(),
            }
        })

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
    - subject_name: str (optional)
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

        # Validate required fields
        if not complainant_applicant_id:
            return JsonResponse({
                'success': False,
                'error': 'Select a complainant from the housing unit occupant list.',
            }, status=400)
        if (
            subject_applicant_id
            and complainant_applicant_id
            and subject_applicant_id == complainant_applicant_id
        ):
            return JsonResponse({
                'success': False,
                'error': 'Respondent cannot be the same person as the complainant.',
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

        # Validate case type
        valid_types = [code for code, _ in Case.CASE_TYPE_CHOICES]
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
        elif complainant_applicant:
            la = (
                LotAward.objects.filter(
                    application__applicant=complainant_applicant,
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
def upload_case_evidence(request, position, case_id):
    """Upload photo or document for a case (field desk intake)."""
    if not wf.user_can_upload_case_evidence(request.user):
        return JsonResponse({
            'success': False,
            'error': 'Evidence uploads are handled at the field desk.',
        }, status=403)
    case = get_object_or_404(Case, id=case_id)
    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'success': False, 'error': 'No file uploaded.'}, status=400)
    if upload.size > 6 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'File must be 6 MB or smaller.'}, status=400)

    if wf.user_can_upload_case_evidence(request.user):
        allowed = ('image/jpeg', 'image/png', 'image/webp')
        type_error = 'Allowed types: JPEG, PNG, or WebP photos only.'
    else:
        allowed = ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')
        type_error = 'Allowed types: JPEG, PNG, WebP, or PDF.'
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
            'url': request.build_absolute_uri(evidence.file.url),
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

    caption = (request.POST.get('caption') or '').strip()[:255]
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
                return JsonResponse({'success': True, 'message': 'Case archived (closed)', 'new_status': case.status})
            if not wf.can_transition(case, transition):
                return JsonResponse({'success': False, 'error': 'Invalid workflow transition.'}, status=400)
            wf.apply_transition(case, transition)
            if transition == 'start_review':
                case.investigated_by = request.user
                case.investigated_at = timezone.now()
            case.save()
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
