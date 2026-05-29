from django.core.exceptions import ValidationError
from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction, models, IntegrityError
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from collections import OrderedDict
from functools import wraps
import json

from intake.models import Applicant, Barangay, HouseholdMember
from applications.models import QueueEntry, Application
from intake.utils import format_phone_number, send_sms
from units.models import (
    HousingUnit, LotAward, RelocationSite, WeeklyReport,
    ConstructionProgress, ConstructionProgressUpdate, Blacklist, OccupancyMonitoringCycle,
    MonitoringTask, MonitoringReport, ExplanationReview, ExtensionRecord,
)
from accounts.models import FIELD_DESK_POSITIONS
from cases.views import cases_page_url, module5_case_rows_for_unit
from units.housing_unit_status import housing_unit_on_file
from units.monitoring_policy import (
    EXTENSION_BUILD_DAYS,
    EXTENSION_FINAL_INSPECTION_OFFSET_DAYS,
    EXTENSION_MIDPOINT_INSPECTION_OFFSET_DAYS,
    POSSESSION_GRACE_DAYS,
    TASK_TYPE_EXTENSION_FINAL,
    TASK_TYPE_EXTENSION_MIDPOINT,
    TASK_TYPE_FINAL_INSPECTION,
    TASK_TYPE_INITIAL_INSPECTION,
)

# Module 4 inventory: who may add housing units (block/lot rows)
_MODULE4_ADD_HOUSING_UNIT_POSITIONS = frozenset({'fourth_member', 'second_member'})
_MODULE4_CREATE_SITE_POSITIONS = frozenset({'fourth_member', 'second_member'})
_MODULE4_MONITORING_COMPLIANCE_STAFF = _MODULE4_ADD_HOUSING_UNIT_POSITIONS | FIELD_DESK_POSITIONS

_NOTICE_STATUS_VALUES = frozenset({'Under notice (30-day)', 'Final notice (10-day)'})

_HOUSEHOLD_RELATIONSHIP_OPTIONS = [
    {'value': key, 'label': label} for key, label in HouseholdMember.RELATIONSHIP_CHOICES
]


def _explanation_letter_deadline_office_payload(deadline):
    """
    Format ``letter_deadline_at`` for THA office wall clock (``settings.TIME_ZONE``).

    Returns (iso_utc_or_offset, display_str, datetime_local_value). Values are None
    when ``deadline`` is None. ``datetime_local_value`` is suitable for
    ``<input type="datetime-local">`` and must be parsed on save as office time, not
    the browser's local zone.
    """
    if deadline is None:
        return None, None, None
    local = timezone.localtime(deadline)
    return (
        deadline.isoformat(),
        local.strftime('%b %d, %Y %I:%M %p'),
        local.strftime('%Y-%m-%dT%H:%M'),
    )


def _explanation_letter_sms_for_case(unit, applicant, rev):
    """
    Build SMS body and trigger event for the explanation-letter workflow.

    Returns (None, None) when a letter is already on file.
    """
    block = unit.block_number
    lot = unit.lot_number
    ref = applicant.reference_number or '—'
    if rev and rev.letter_document:
        return None, None
    if not rev or not rev.letter_deadline_at:
        return (
            f'THA: Your lot (Block {block} Lot {lot}) was assessed as '
            f'No Progress. Report to the THA office with a written EXPLANATION letter. '
            f'Staff will record your submission deadline in the system. Ref: {ref}'
        ), 'explanation_letter_required'
    local_disp = timezone.localtime(rev.letter_deadline_at).strftime('%b %d, %Y %I:%M %p')
    if timezone.now() >= rev.letter_deadline_at:
        return (
            f'THA NOTICE: The deadline for your written EXPLANATION letter (Block {block} '
            f'Lot {lot}) has passed without a scanned letter on file. '
            f'Report to the Housing Office immediately or your case may be disqualified. '
            f'Ref: {ref}'
        ), 'explanation_letter_deadline_passed'
    return (
        f'THA: Submit your written EXPLANATION letter for Block {block} Lot {lot} '
        f'at the Housing Office no later than {local_disp}. '
        f'Ref: {ref}'
    ), 'explanation_letter_deadline_set'


def _unit_beneficiary_sms_message(unit, applicant, lot_award, progress):
    """
    SMS body for footer Send SMS: explanation-letter case when open, else general unit contact.
    """
    rev = _active_pending_explanation_for_lot_award(lot_award)
    if (
        rev
        and not rev.letter_document
        and _explanation_review_triggered_by_day30_inspection(rev)
    ):
        body, event = _explanation_letter_sms_for_case(unit, applicant, rev)
        if body:
            return body, event

    block = unit.block_number
    lot = unit.lot_number
    ref = applicant.reference_number or '—'
    on_file = housing_unit_on_file(lot_award, progress)
    if on_file:
        return (
            f'THA: Regarding your housing unit at Block {block}, Unit {lot}. '
            f'For occupancy or monitoring concerns, contact the Talisay Housing Office. '
            f'Ref: {ref}'
        ), 'housing_unit_contact'
    return (
        f'THA: Regarding your awarded lot at Block {block}, Lot {lot}. '
        f'For monitoring or housing office concerns, contact the Talisay Housing Office. '
        f'Ref: {ref}'
    ), 'awarded_lot_contact'


def _unit_has_notice_subject(unit, active_award=None):
    """
    Compliance notices apply to an occupying beneficiary. True if there is an active
    lot award or at least a recorded occupant on the unit row.
    """
    if active_award is not None:
        return True
    return bool((unit.occupant_name or '').strip())


def _sync_site_housing_unit_occupancy(site):
    """
    Keep Module 4 unit occupancy aligned with active LotAward rows.

    This fixes stale map badges when old applicant/application records were removed
    but `HousingUnit.status` remained "Occupied".
    """
    if not site:
        return

    active_awards = (
        LotAward.objects
        .filter(unit__site=site, status='active')
        .select_related('application__applicant')
        .order_by('-awarded_at')
    )
    active_award_by_unit_id = {}
    for award in active_awards:
        active_award_by_unit_id.setdefault(award.unit_id, award)

    units = list(
        HousingUnit.objects
        .filter(site=site)
        .only(
            'id', 'status', 'occupant_name', 'occupant_id',
            'notice_type', 'notice_date_issued', 'notice_deadline',
            'updated_at',
        )
    )
    to_update = []
    for unit in units:
        active_award = active_award_by_unit_id.get(unit.id)
        if active_award is None:
            # Only reset stale occupied units; preserve notice/repossessed states.
            if unit.status == 'Occupied':
                unit.status = 'Vacant — available'
                unit.occupant_name = ''
                unit.occupant_id = None
                to_update.append(unit)
            # Notice status with no occupant and no award is invalid (e.g. notice issued on vacant lot).
            elif unit.status in _NOTICE_STATUS_VALUES and not (unit.occupant_name or '').strip():
                unit.status = 'Vacant — available'
                unit.notice_type = None
                unit.notice_date_issued = None
                unit.notice_deadline = None
                to_update.append(unit)
            continue

        # If an active award exists but unit still shows vacant, correct it.
        if unit.status == 'Vacant — available':
            applicant = getattr(active_award.application, 'applicant', None)
            unit.status = 'Occupied'
            unit.occupant_name = applicant.full_name if applicant else ''
            ref = (applicant.reference_number or '') if applicant else ''
            unit.occupant_id = ref[:100] if ref else None
            to_update.append(unit)

    if to_update:
        HousingUnit.objects.bulk_update(
            to_update,
            [
                'status', 'occupant_name', 'occupant_id',
                'notice_type', 'notice_date_issued', 'notice_deadline',
                'updated_at',
            ],
        )


# =============================================================================
# POSITION VERIFICATION DECORATOR
# =============================================================================

def verify_position(view_func):
    """
    Decorator to verify that URL position parameter matches logged-in user's position.
    Security feature: prevents URL manipulation to access other roles' views.
    """
    @wraps(view_func)
    def wrapper(request, position, *args, **kwargs):
        # Check if position in URL matches user's actual position
        if request.user.position != position:
            messages.error(request, f'Access denied. You are logged in as {request.user.get_position_display()}, not {position.replace("_", " ")}.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': (
                        f'Access denied. You are logged in as '
                        f'{request.user.get_position_display()}, not {position.replace("_", " ")}.'
                    ),
                }, status=403)
            return redirect('accounts:dashboard')
        return view_func(request, position, *args, **kwargs)
    return wrapper


# ===================================================================
# HOUSING UNITS MONITORING (Module 4 - Housing Units Dashboard)
# ===================================================================

@login_required
@verify_position
def housing_units_monitoring(request, position):
    """
    Housing Unit & Occupancy Monitoring Dashboard
    Displays all housing units grouped by block with status, occupant info,
    and notice tracking. Supports grid and table views.

    URL: /units/housing-units/<position>/  (e.g. …/second_member/, …/fourth_member/)

    Template: units/housing_units_monitoring.html

    Actors: Second Member, Fourth Member, Field desk, and other staff (nav uses role-specific URL).
    Purpose: Monitor unit occupancy, track compliance notices, manage escalations
    """

    # Get site - assume user is assigned to a site
    # For Fourth Member (Jocel), this would be their primary site
    site_id = request.GET.get('site_id')
    site = None
    all_sites = RelocationSite.objects.all()

    if site_id:
        site = RelocationSite.objects.filter(id=site_id).first()
    else:
        # Default: get first site user has access to
        sites = request.user.assigned_sites.all()
        site = sites.first() if sites.exists() else None

    # If no assigned site, allow staff to view all sites
    # If regular user with no assignment, show first available site
    no_relocation_sites = False
    if not site:
        if all_sites.exists():
            site = all_sites.first()
        else:
            no_relocation_sites = True

    # Reconcile stale occupancy flags before rendering the Module 4 map/KPIs.
    if not no_relocation_sites and site is not None:
        _sync_site_housing_unit_occupancy(site)

    # Get all units for the site with related data (empty when no sites exist yet)
    if no_relocation_sites:
        units = HousingUnit.objects.none()
    else:
        units = (
            HousingUnit.objects
            .filter(site=site)
            .select_related('weekly_report')
            .prefetch_related('lot_awards__application__applicant')
            .order_by('block_number', 'lot_number')
        )

    # Count by status
    occupied_count = units.filter(status='Occupied').count()
    vacant_count = units.filter(status='Vacant — available').count()
    notice_30_count = units.filter(status='Under notice (30-day)').count()
    notice_10_count = units.filter(status='Final notice (10-day)').count()
    repossessed_count = units.filter(status='Repossessed').count()

    # Find critical alerts (final notices escalated)
    escalated_units = units.filter(
        status='Final notice (10-day)',
        is_escalated=True
    ).first()

    critical_alert_message = ""
    has_final_notice_alerts = notice_10_count > 0 or units.filter(is_escalated=True).exists()

    if escalated_units:
        critical_alert_message = (
            f"Block {escalated_units.block_number}, Lot {escalated_units.lot_number} — "
            f"{escalated_units.occupant_name or 'Unknown'}. "
            f"Deadline: {escalated_units.notice_deadline}. No response received — case escalated."
        )

    # Materialize once so per-unit annotations survive into the template
    units_list = list(units)

    # Group units by block (OrderedDict so template can use .items() like a dict)
    units_by_block = OrderedDict()
    for u in units_list:
        units_by_block.setdefault(u.block_number, []).append(u)

    from applications.views import get_module2_permissions

    permissions = get_module2_permissions(request.user)
    can_create_relocation_site = request.user.position in _MODULE4_CREATE_SITE_POSITIONS
    can_add_housing_unit = (
        request.user.position in _MODULE4_ADD_HOUSING_UNIT_POSITIONS
        and not no_relocation_sites
        and site is not None
    )

    # Construction monitoring rollups + per-unit snapshot (MVP)
    construction_not_started = 0
    construction_in_progress = 0
    construction_completed = 0
    construction_delayed = 0
    housing_unit_on_file_count = 0
    progress_by_unit_id = {}

    if not no_relocation_sites and units_list:
        progress_qs = (
            ConstructionProgress.objects.filter(
                lot_award__unit__in=units_list,
                lot_award__status='active',
            )
            .select_related('lot_award__unit')
        )
        for p in progress_qs:
            uid = getattr(p.lot_award, 'unit_id', None)
            if uid and uid not in progress_by_unit_id:
                progress_by_unit_id[uid] = p

        for u in units_list:
            p = progress_by_unit_id.get(u.id)
            setattr(u, '_construction_progress', p)
            la = getattr(p, 'lot_award', None)
            on_file = housing_unit_on_file(la, p)
            setattr(u, 'is_housing_unit_on_file', on_file)
            if on_file:
                housing_unit_on_file_count += 1
            if not p:
                setattr(u, 'construction_tokens', '')
                continue
            tokens = []
            if p.is_delayed:
                construction_delayed += 1
                tokens.append('delayed')
            if p.stage == 'not_started' or p.percent_complete <= 0:
                construction_not_started += 1
                tokens.append('not_started')
            elif p.stage == 'completed' or p.percent_complete >= 100:
                construction_completed += 1
                tokens.append('completed')
            else:
                construction_in_progress += 1
                tokens.append('in_progress')
            setattr(u, 'construction_tokens', ' '.join(tokens))

        ext_failed_unit_ids = _unit_ids_with_extension_month_2_failed(units_list)
        for u in units_list:
            setattr(u, 'extension_final_visit_failed', u.id in ext_failed_unit_ids)
    else:
        for u in units_list:
            setattr(u, 'extension_final_visit_failed', False)

    # Prepare context
    context = {
        'site': site,
        'all_sites': all_sites,
        'no_relocation_sites': no_relocation_sites,
        'show_dev_seed_hint': no_relocation_sites and settings.DEBUG,
        'total_units': units.count(),
        'occupied_count': occupied_count,
        'vacant_count': vacant_count,
        'notice_30_count': notice_30_count,
        'notice_10_count': notice_10_count,
        'repossessed_count': repossessed_count,
        'units_by_block': units_by_block,
        'all_units': units,
        'has_final_notice_alerts': has_final_notice_alerts,
        'critical_alert_message': critical_alert_message,
        # Aliases for template compatibility
        'has_escalation_alerts': has_final_notice_alerts,
        'escalation_message': critical_alert_message,
        'view_mode': request.GET.get('view', 'grid'),
        'permissions': permissions,
        'can_add_housing_unit': can_add_housing_unit,
        'can_create_relocation_site': can_create_relocation_site,
        'barangays': Barangay.objects.filter(is_active=True).order_by('name'),
        'construction_not_started': construction_not_started,
        'construction_in_progress': construction_in_progress,
        'construction_completed': construction_completed,
        'construction_delayed': construction_delayed,
        'housing_unit_on_file_count': housing_unit_on_file_count,
        'explanation_letter_office_tz': str(settings.TIME_ZONE),
    }

    return render(request, 'units/housing_units_monitoring.html', context)


def _gk_masterlist_site(request):
    """Resolve relocation site for GK masterlist (same rules as monitoring dashboard)."""
    site_id = request.GET.get('site_id')
    if site_id:
        site = RelocationSite.objects.filter(id=site_id).first()
        if site:
            return site
    sites = request.user.assigned_sites.all()
    if sites.exists():
        return sites.first()
    return RelocationSite.objects.order_by('name').first()


def _gk_masterlist_rows(site):
    """
    People currently tied to housing inventory at a site: lot beneficiaries
    plus registered household members (active lot award), or legacy occupant_name.
    """
    if site is None:
        return []

    active_award_qs = (
        LotAward.objects.filter(status='active')
        .select_related('application__applicant')
        .prefetch_related('application__applicant__household_members')
    )
    units = (
        HousingUnit.objects.filter(site=site)
        .prefetch_related(Prefetch('lot_awards', queryset=active_award_qs))
        .order_by('block_number', 'lot_number')
    )

    rows = []
    seen_keys = set()

    def _append_row(*, unit_id, name, role_label, reference, block_lot, is_primary=False):
        name_clean = (name or '').strip()
        if not name_clean:
            return
        key = (str(unit_id), name_clean.lower(), (role_label or '').lower())
        if key in seen_keys:
            return
        seen_keys.add(key)
        rows.append({
            'unit_id': unit_id,
            'name': name_clean,
            'role_label': role_label or '—',
            'reference': (reference or '').strip(),
            'block_lot': block_lot,
            'is_primary': is_primary,
            'sort_key': name_clean.lower(),
        })

    for unit in units:
        block_lot = f"Block {unit.block_number} · Lot {unit.lot_number}"
        active_award = None
        for award in unit.lot_awards.all():
            if award.status == 'active':
                active_award = award
                break
        if active_award:
            applicant = getattr(active_award.application, 'applicant', None)
            if applicant:
                _append_row(
                    unit_id=unit.id,
                    name=applicant.full_name,
                    role_label='Head / Beneficiary',
                    reference=applicant.reference_number,
                    block_lot=block_lot,
                    is_primary=True,
                )
                for member in applicant.household_members.all().order_by('created_at'):
                    _append_row(
                        unit_id=unit.id,
                        name=member.full_name,
                        role_label=member.get_relationship_display(),
                        reference=applicant.reference_number,
                        block_lot=block_lot,
                        is_primary=False,
                    )
                continue
        if (unit.occupant_name or '').strip():
            _append_row(
                unit_id=unit.id,
                name=unit.occupant_name,
                role_label='Occupant (on file)',
                reference=unit.occupant_id or '',
                block_lot=block_lot,
                is_primary=True,
            )

    rows.sort(key=lambda r: (r['sort_key'], r['block_lot']))
    return rows


@login_required
@verify_position
def gk_masterlist(request, position):
    """
    GK Masterlist — all beneficiaries and household members on housing units at a site.
    URL: /units/housing-units/<position>/gk-masterlist/
    """
    site = _gk_masterlist_site(request)
    all_sites = RelocationSite.objects.filter(is_active=True).order_by('name')
    no_relocation_sites = not all_sites.exists()

    search = (request.GET.get('search') or '').strip().lower()
    masterlist_rows = _gk_masterlist_rows(site)
    if search:
        masterlist_rows = [
            row for row in masterlist_rows
            if search in row['name'].lower()
            or search in (row['reference'] or '').lower()
            or search in row['block_lot'].lower()
            or search in row['role_label'].lower()
        ]

    monitoring_url = reverse('units:housing_units_monitoring', kwargs={'position': position})
    if site:
        monitoring_url = f"{monitoring_url}?site_id={site.id}"

    context = {
        'site': site,
        'all_sites': all_sites,
        'no_relocation_sites': no_relocation_sites,
        'masterlist_rows': masterlist_rows,
        'masterlist_total': len(masterlist_rows),
        'search': request.GET.get('search', '').strip(),
        'monitoring_url': monitoring_url,
    }
    return render(request, 'units/gk_masterlist.html', context)


@login_required
@verify_position
@require_POST
def create_relocation_site(request, position):
    """
    Bootstrap endpoint for fresh databases: create first relocation site from Module 4 UI.
    """
    if request.user.position not in _MODULE4_CREATE_SITE_POSITIONS:
        return JsonResponse(
            {'success': False, 'error': 'Only housing staff (4th / 2nd Member) can create relocation sites.'},
            status=403,
        )

    name = (request.POST.get('name') or '').strip()[:100]
    code = (request.POST.get('code') or '').strip()[:20].upper()
    address = (request.POST.get('address') or '').strip()
    barangay_id = (request.POST.get('barangay_id') or '').strip()
    notes = (request.POST.get('notes') or '').strip()[:500]
    try:
        total_blocks = int((request.POST.get('total_blocks') or '0').strip() or 0)
        total_lots = int((request.POST.get('total_lots') or '0').strip() or 0)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Total blocks/lots must be whole numbers.'}, status=400)

    if not name or not code or not address or not barangay_id:
        return JsonResponse(
            {'success': False, 'error': 'Name, code, barangay, and address are required.'},
            status=400,
        )

    barangay = Barangay.objects.filter(id=barangay_id, is_active=True).first()
    if not barangay:
        return JsonResponse({'success': False, 'error': 'Invalid barangay.'}, status=400)

    if RelocationSite.objects.filter(name__iexact=name).exists():
        return JsonResponse({'success': False, 'error': 'A relocation site with this name already exists.'}, status=400)
    if RelocationSite.objects.filter(code__iexact=code).exists():
        return JsonResponse({'success': False, 'error': 'Site code already exists.'}, status=400)

    try:
        site = RelocationSite.objects.create(
            name=name,
            code=code,
            address=address,
            barangay=barangay,
            total_blocks=max(total_blocks, 0),
            total_lots=max(total_lots, 0),
            is_active=True,
            notes=notes,
            caretaker=request.user,
        )
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse(
        {
            'success': True,
            'message': f'Relocation site created: {site.name}.',
            'site': {'id': str(site.id), 'name': site.name, 'code': site.code},
        }
    )


@login_required
@verify_position
@require_POST
def create_housing_unit(request, position):
    """
    Add a new HousingUnit (block + lot) to a relocation site inventory.
    New units start as Vacant — available.

    URL: /units/housing-units/<position>/unit/create/

    POST: site_id, block_number, lot_number
    """
    _DUPLICATE_UNIT_MSG = 'Existing block or lot!'

    if request.user.position not in _MODULE4_ADD_HOUSING_UNIT_POSITIONS:
        return JsonResponse(
            {'success': False, 'error': 'Only housing staff (4th / 2nd Member) can add units.'},
            status=403,
        )

    site_id = (request.POST.get('site_id') or '').strip()
    block_number = (request.POST.get('block_number') or '').strip()[:10]
    lot_number = (request.POST.get('lot_number') or '').strip()[:10]
    location_notes = (request.POST.get('location_notes') or '').strip()[:500]

    if not block_number or not lot_number:
        return JsonResponse(
            {'success': False, 'error': 'Block and lot are required.'},
            status=400,
        )

    if not block_number.isdigit() or not lot_number.isdigit():
        return JsonResponse(
            {'success': False, 'error': 'Block and lot must be digits only (0-9).'},
            status=400,
        )

    site = RelocationSite.objects.filter(id=site_id, is_active=True).first()
    if not site:
        return JsonResponse(
            {'success': False, 'error': 'Invalid or inactive relocation site.'},
            status=400,
        )

    try:
        unit = HousingUnit.objects.create(
            site=site,
            block_number=block_number,
            lot_number=lot_number,
            status='Vacant — available',
            location_notes=location_notes,
        )
    except IntegrityError:
        return JsonResponse(
            {
                'success': False,
                'error': (
                    f'Block {block_number} Lot {lot_number} already exists at {site.name}. '
                    'Use different numbers or edit the existing unit.'
                ),
            },
            status=400,
        )
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse(
        {
            'success': True,
            'message': f'Added Block {block_number} Lot {lot_number} at {site.name}.',
            'unit': {'id': str(unit.id), 'block': block_number, 'lot': lot_number},
        }
    )


def _month_2_inspection_marked_no_progress(lot_award):
    """
    True when the extension final visit (month_2_inspection) is complete and staff
    assessed it as no_progress ("Failed" in UI).
    """
    if not lot_award:
        return False
    task = (
        MonitoringTask.objects.filter(
            lot_award=lot_award,
            task_type=TASK_TYPE_EXTENSION_FINAL,
            status='completed',
        )
        .order_by('-due_date', '-id')
        .first()
    )
    if not task:
        return False
    report = task.reports.order_by('-submitted_at').first()
    return bool(
        report
        and report.progress_assessment == 'no_progress'
        and report.assessed_at
    )


def _unit_ids_with_extension_month_2_failed(units_list):
    """For site map: units whose extension 30 Day visit was assessed Failed."""
    if not units_list:
        return frozenset()
    unit_ids = [u.id for u in units_list]
    failed = set()
    tasks = MonitoringTask.objects.filter(
        lot_award__unit_id__in=unit_ids,
        lot_award__status='active',
        task_type=TASK_TYPE_EXTENSION_FINAL,
        status='completed',
    ).select_related('lot_award')
    for t in tasks:
        report = t.reports.order_by('-submitted_at').first()
        if (
            report
            and report.progress_assessment == 'no_progress'
            and report.assessed_at
        ):
            failed.add(t.lot_award.unit_id)
    return frozenset(failed)


_FINAL_MONITORING_TASK_TYPES = frozenset({TASK_TYPE_FINAL_INSPECTION, TASK_TYPE_EXTENSION_FINAL})


def _report_indicates_housing_unit_ready(report):
    """Final 30 Day caretaker report: properly occupied + build finished → staff should choose Housing unit."""
    if not report:
        return False
    return (
        (report.occupancy_status or '').strip() == 'properly_occupied'
        and (report.construction_status or '').strip() == 'completed_occupied'
    )


def _beneficiary_subject_pronoun(applicant):
    """he / she / they for staff-facing monitoring messages."""
    sex = (getattr(applicant, 'sex', None) or '').strip().upper()
    if sex == 'F':
        return 'she'
    if sex == 'M':
        return 'he'
    return 'they'


def _staff_progress_assessment_display(task_type, assessment):
    """Staff decision label; final visits use outcome wording instead of Normal/No Progress."""
    if not assessment:
        return ''
    if assessment == 'normal_progress' and task_type in _FINAL_MONITORING_TASK_TYPES:
        return 'Housing unit'
    if assessment == 'no_progress':
        if task_type == TASK_TYPE_EXTENSION_FINAL:
            return 'Failed'
        if task_type == TASK_TYPE_FINAL_INSPECTION:
            return 'Explanation letter'
    return dict(MonitoringReport.PROGRESS_ASSESSMENT_CHOICES).get(assessment, assessment)


@login_required
@verify_position
@require_http_methods(["GET"])
def get_unit_details(request, position, unit_id):
    """
    AJAX endpoint to fetch unit details for modal display
    Returns JSON with unit info, occupant, notices, and weekly report

    URL: /units/<position>/detail/<unit_id>/
    """
    try:
        unit = HousingUnit.objects.prefetch_related('weekly_report').get(id=unit_id)

        # Prepare notice info
        notice_info = None
        if unit.notice_date_issued:
            notice_info = {
                'type': unit.notice_type,
                'issued': unit.notice_date_issued.isoformat(),
                'deadline': unit.notice_deadline.isoformat() if unit.notice_deadline else None,
            }

        # Prepare weekly report
        weekly_report = None
        try:
            if unit.weekly_report:
                weekly_report = {
                    'reported_status': unit.weekly_report.reported_status,
                    'concern_notes': unit.weekly_report.concern_notes,
                    'last_updated': unit.weekly_report.last_updated.isoformat(),
                }
        except HousingUnit.weekly_report.RelatedObjectDoesNotExist:
            weekly_report = None

        # Construction snapshot + last updates (MVP)
        progress = (
            ConstructionProgress.objects.filter(lot_award__unit=unit, lot_award__status='active')
            .select_related('updated_by')
            .first()
        )
        active_lot_award = (
            LotAward.objects
            .filter(unit=unit, status='active')
            .select_related('application__applicant')
            .order_by('-awarded_at')
            .first()
        )
        extension_final_visit_failed = (
            _month_2_inspection_marked_no_progress(active_lot_award) if active_lot_award else False
        )
        possession_info = None
        beneficiary_info = None
        monitoring_history = []
        compliance_records = []
        applicant_for_household = None
        if active_lot_award and active_lot_award.awarded_at:
            awarded_at = active_lot_award.awarded_at
            now = timezone.now()
            monitoring_start_date = awarded_at.date() + timedelta(days=POSSESSION_GRACE_DAYS)
            days_possessed = max(0, (now.date() - awarded_at.date()).days)
            possession_info = {
                'awarded_at': awarded_at.isoformat(),
                'possessed_at': awarded_at.isoformat(),
                'days_possessed': days_possessed,
                'monitoring_starts_on': monitoring_start_date.isoformat(),
                'days_until_monitoring': max(0, (monitoring_start_date - now.date()).days),
            }
        if active_lot_award:
            applicant = getattr(active_lot_award.application, 'applicant', None)
            if applicant:
                applicant_for_household = applicant
                household_member_rows = [
                    {
                        'id': str(member.id),
                        'name': member.full_name,
                        'relationship': member.get_relationship_display(),
                        'sex_display': member.get_sex_display() if member.sex else '—',
                        'age': int(member.age) if member.age is not None else 0,
                    }
                    for member in applicant.household_members.all().order_by('created_at')
                ]
                beneficiary_info = {
                    'applicant_id': str(applicant.id),
                    'full_name': applicant.full_name or '',
                    'reference_number': applicant.reference_number or '',
                    'household_members': applicant.household_member_count,
                    'household_member_rows': household_member_rows,
                    'sex': applicant.sex or '',
                    'sex_display': applicant.get_sex_display() if applicant.sex else '—',
                }
        if beneficiary_info is None and (unit.occupant_name or '').strip():
            beneficiary_info = {
                'full_name': (unit.occupant_name or '').strip(),
                'reference_number': (unit.occupant_id or '').strip(),
                'household_members': None,
                'household_member_rows': [],
                'sex': '',
                'sex_display': '—',
            }
        monitoring_tasks = []
        explanation_extension_final_task = None
        explanation_build_extension = None
        extension_monitoring_active = False
        pending_explanation_rev = None
        ext_cycle = None
        if active_lot_award:
            ext_cycle = (
                OccupancyMonitoringCycle.objects.filter(
                    lot_award=active_lot_award,
                    is_active=True,
                )
                .exclude(cycle_stage='original_30_day')
                .order_by('-created_at')
                .first()
            )
            extension_monitoring_active = ext_cycle is not None
            pending_explanation_rev = _active_pending_explanation_for_lot_award(active_lot_award)
            if pending_explanation_rev and not _explanation_review_triggered_by_day30_inspection(
                pending_explanation_rev
            ):
                pending_explanation_rev = None
            today = timezone.now().date()
            grace_monitoring_start = (
                (active_lot_award.awarded_at.date() + timedelta(days=POSSESSION_GRACE_DAYS)).isoformat()
                if active_lot_award.awarded_at
                else ''
            )
            ext_monitoring_start = (
                ext_cycle.stage_start_date.isoformat()
                if ext_cycle and ext_cycle.stage_start_date
                else ''
            )
            ext_row = None
            if extension_monitoring_active and ext_cycle:
                ext_row = (
                    ExtensionRecord.objects.filter(
                        lot_award=active_lot_award,
                        explanation_review__isnull=False,
                    )
                    .order_by('-extension_start_date')
                    .first()
                )
            letter_extension_cards = ext_row is not None
            if ext_row:
                explanation_build_extension = {
                    'start_date': ext_row.extension_start_date.isoformat(),
                    'end_date': ext_row.extension_end_date.isoformat(),
                }
            task_types = (
                [TASK_TYPE_INITIAL_INSPECTION, TASK_TYPE_FINAL_INSPECTION, TASK_TYPE_EXTENSION_FINAL, TASK_TYPE_EXTENSION_MIDPOINT]
                if letter_extension_cards
                else [TASK_TYPE_INITIAL_INSPECTION, TASK_TYPE_FINAL_INSPECTION]
            )
            extension_final_30day_cleared = True
            if letter_extension_cards:
                m2 = (
                    MonitoringTask.objects.filter(
                        lot_award=active_lot_award,
                        task_type=TASK_TYPE_EXTENSION_FINAL,
                    )
                    .first()
                )
                if m2:
                    r2 = m2.reports.order_by('-submitted_at').first()
                    extension_final_30day_cleared = bool(
                        m2.status == 'completed' and r2 and r2.progress_assessment
                    )
                else:
                    extension_final_30day_cleared = False
            for task in (
                MonitoringTask.objects
                .filter(lot_award=active_lot_award, task_type__in=task_types)
                .order_by('due_date', 'scheduled_date', 'task_type')
            ):
                report = (
                    task.reports
                    .select_related('submitted_by', 'assessed_by')
                    .order_by('-submitted_at')
                    .first()
                )
                report_summary = None
                if report:
                    photo_urls = [photo.image.url for photo in report.photos.all() if photo.image]
                    if not photo_urls and report.photo_evidence:
                        photo_urls = [report.photo_evidence.url]
                    report_summary = {
                        'id': str(report.id),
                        'occupancy_status': report.get_occupancy_status_display(),
                        'occupancy_status_key': report.occupancy_status,
                        'occupancy_notes': report.occupancy_notes or '',
                        'construction_status': report.get_construction_status_display(),
                        'construction_status_key': report.construction_status,
                        'percent_complete': report.percent_complete,
                        'progress_notes': report.progress_notes or '',
                        'general_remarks': report.general_remarks or '',
                        'photo_url': report.photo_evidence.url if report.photo_evidence else '',
                        'photo_urls': photo_urls,
                        'submitted_at': report.submitted_at.isoformat(),
                        'submitted_by': report.submitted_by.get_full_name() if report.submitted_by else '—',
                        'progress_assessment': report.progress_assessment,
                        'progress_assessment_label': _staff_progress_assessment_display(
                            task.task_type, report.progress_assessment
                        ) if report.progress_assessment else '',
                        'assessed_at': report.assessed_at.isoformat() if report.assessed_at else '',
                        'assessed_by': report.assessed_by.get_full_name() if report.assessed_by else '',
                    }
                initial_monitoring_complete = (
                    task.task_type == TASK_TYPE_INITIAL_INSPECTION
                    and report_summary
                    and bool(report_summary.get('progress_assessment'))
                )
                final_monitoring_program_complete = (
                    task.task_type in (TASK_TYPE_FINAL_INSPECTION, TASK_TYPE_EXTENSION_FINAL)
                    and report_summary
                    and report_summary.get('progress_assessment') == 'normal_progress'
                    and housing_unit_on_file(active_lot_award, progress)
                )
                if task.task_type in (TASK_TYPE_INITIAL_INSPECTION, TASK_TYPE_EXTENSION_MIDPOINT):
                    _task_title = '60 Day Inspection'
                    _history_row_label = '60 Day'
                    if task.task_type == TASK_TYPE_EXTENSION_MIDPOINT:
                        monitoring_window_line = 'Extension monitoring — 60-day midpoint'
                    else:
                        monitoring_window_line = 'Initial monitoring — first 60 days'
                elif task.task_type in (TASK_TYPE_FINAL_INSPECTION, TASK_TYPE_EXTENSION_FINAL):
                    _task_title = '30 Day Inspection'
                    _history_row_label = '30 Day'
                    monitoring_window_line = 'Final monitoring — confirm lot build is finished'
                else:
                    _task_title = task.get_task_type_display()
                    _history_row_label = task.get_task_type_display().replace(' Inspection', '')
                    monitoring_window_line = (
                        f'{task.days_from_award} days after monitoring starts'
                        if task.days_from_award is not None
                        else 'scheduled monitoring visit'
                    )
                monitoring_starts_on = (
                    ext_monitoring_start
                    if (
                        letter_extension_cards
                        and ext_monitoring_start
                        and task.task_type == TASK_TYPE_EXTENSION_FINAL
                    )
                    else grace_monitoring_start
                )
                task_row = {
                    'id': str(task.id),
                    'task_type': task.task_type,
                    'label': _task_title,
                    'unit_label': f'Block {unit.block_number} Lot {unit.lot_number}',
                    'monitoring_window_line': monitoring_window_line,
                    'award_date': active_lot_award.awarded_at.date().isoformat() if active_lot_award.awarded_at else '',
                    'monitoring_starts_on': monitoring_starts_on,
                    'scheduled_date': task.scheduled_date.isoformat(),
                    'due_date': task.due_date.isoformat(),
                    'days_from_award': task.days_from_award,
                    'status': task.status,
                    'status_label': task.get_status_display(),
                    'is_due': task.scheduled_date <= today,
                    'is_overdue': task.is_overdue,
                    'notified_at': task.notified_at.isoformat() if task.notified_at else '',
                    'report': report_summary,
                    'initial_monitoring_complete': initial_monitoring_complete,
                    'final_monitoring_program_complete': final_monitoring_program_complete,
                    # Deprecated alias — use initial_monitoring_complete for 60 Day only.
                    'initial_monitoring_program_complete': initial_monitoring_complete,
                }
                if letter_extension_cards and task.task_type == TASK_TYPE_EXTENSION_FINAL:
                    task_row['extension_30day_blocked'] = False
                    explanation_extension_final_task = task_row
                elif letter_extension_cards and task.task_type == TASK_TYPE_EXTENSION_MIDPOINT:
                    if settings.EXTENSION_30DAY_SKIP_MIDPOINT_BLOCK:
                        task_row['extension_midpoint_blocked'] = False
                    else:
                        task_row['extension_midpoint_blocked'] = not extension_final_30day_cleared
                    monitoring_tasks.append(task_row)
                else:
                    monitoring_tasks.append(task_row)
                monitoring_history.append({
                    'label': _history_row_label,
                    'date': task.due_date.isoformat(),
                    'result': report.get_construction_status_display() if report else task.get_status_display(),
                    'decision': _staff_progress_assessment_display(
                        task.task_type, report.progress_assessment
                    ) if report and report.progress_assessment else '',
                })
            if unit.notice_date_issued:
                deadline_text = unit.notice_deadline.isoformat() if unit.notice_deadline else ''
                compliance_records.append({
                    'title': unit.notice_type or 'Compliance notice',
                    'status': 'Notice active' if unit.notice_deadline and unit.notice_deadline >= today else 'Notice recorded',
                    'detail': f"Deadline: {deadline_text}" if deadline_text else 'Notice issued',
                })
            for cycle in (
                active_lot_award.monitoring_cycles
                .filter(is_active=True)
                .exclude(cycle_stage='original_30_day')
                .order_by('-created_at')[:3]
            ):
                cycle_title = (
                    'Final Grace Period Active'
                    if cycle.cycle_stage == 'final_notice_30_day'
                    else cycle.get_cycle_stage_display()
                )
                compliance_records.append({
                    'title': cycle_title,
                    'status': 'Active',
                    'detail': f"{cycle.stage_start_date.isoformat()} to {cycle.stage_end_date.isoformat()}",
                })
            for extension in active_lot_award.extensions.select_related('approved_by').all()[:3]:
                compliance_records.append({
                    'title': 'Extension Approved',
                    'status': f"{extension.extension_duration_months} month(s)",
                    'detail': f"Until {extension.extension_end_date.isoformat()}",
                })
            for review in active_lot_award.explanation_reviews.select_related('reviewed_by').all()[:3]:
                if pending_explanation_rev and review.pk == pending_explanation_rev.pk:
                    continue
                compliance_records.append({
                    'title': 'Explanation Review',
                    'status': review.get_review_status_display(),
                    'detail': review.staff_decision_notes or review.extension_reason or 'No staff notes recorded',
                })
        updates = []
        if progress:
            for u in progress.updates.select_related('created_by').all()[:10]:
                updates.append({
                    'stage': u.stage,
                    'stage_label': u.get_stage_display(),
                    'percent_complete': u.percent_complete,
                    'visit_date': u.visit_date.isoformat(),
                    'notes': (u.notes or ''),
                    'created_by': u.created_by.get_full_name() if u.created_by else '—',
                    'created_at': u.created_at.isoformat(),
                })

        can_update_construction = request.user.position in (_MODULE4_ADD_HOUSING_UNIT_POSITIONS | FIELD_DESK_POSITIONS)

        # Construction monitoring snapshot (site-level) for drawer table + KPI chips.
        cm_filter = (request.GET.get('cm_filter') or 'all').strip()
        site_progress_rows = list(
            ConstructionProgress.objects
            .filter(lot_award__status='active', lot_award__unit__site=unit.site)
            .select_related('lot_award__unit__site', 'lot_award__application__applicant')
            .order_by('lot_award__unit__block_number', 'lot_award__unit__lot_number')
        )
        count_not_started = sum(1 for p in site_progress_rows if p.stage == 'not_started' or (p.percent_complete or 0) <= 0)
        count_completed = sum(1 for p in site_progress_rows if p.stage == 'completed' or (p.percent_complete or 0) >= 100)
        count_delayed = sum(1 for p in site_progress_rows if p.is_delayed)
        count_in_progress = sum(
            1 for p in site_progress_rows
            if 0 < (p.percent_complete or 0) < 100 and p.stage != 'completed'
        )
        if cm_filter == 'not_started':
            site_progress_rows = [p for p in site_progress_rows if p.stage == 'not_started' or (p.percent_complete or 0) <= 0]
        elif cm_filter == 'in_progress':
            site_progress_rows = [p for p in site_progress_rows if 0 < (p.percent_complete or 0) < 100 and p.stage != 'completed']
        elif cm_filter == 'completed':
            site_progress_rows = [p for p in site_progress_rows if p.stage == 'completed' or (p.percent_complete or 0) >= 100]
        elif cm_filter == 'delayed':
            site_progress_rows = [p for p in site_progress_rows if p.is_delayed]

        site_rows_payload = []
        for p in site_progress_rows:
            app = getattr(p.lot_award, 'application', None)
            applicant = getattr(app, 'applicant', None)
            site_rows_payload.append({
                'unit_label': f"Block {p.lot_award.unit.block_number}, Lot {p.lot_award.unit.lot_number}",
                'site_name': p.lot_award.unit.site.name if p.lot_award.unit.site else '',
                'beneficiary_name': applicant.full_name if applicant else '—',
                'beneficiary_ref': applicant.reference_number if applicant else '',
                'stage_label': p.get_stage_display(),
                'percent_complete': int(p.percent_complete or 0),
                'is_delayed': bool(p.is_delayed),
                'last_inspected_at': p.last_inspected_at.isoformat() if p.last_inspected_at else None,
            })

        explanation_case = None
        if pending_explanation_rev:
            rev = pending_explanation_rev
            now = timezone.now()
            has_doc = bool(rev.letter_document)
            deadline = rev.letter_deadline_at
            deadline_passed = bool(deadline and now > deadline)
            _iso, _disp, _local_inp = _explanation_letter_deadline_office_payload(deadline)
            _app_for_sms = getattr(active_lot_award, 'application', None) if active_lot_award else None
            applicant_for_sms = getattr(_app_for_sms, 'applicant', None) if _app_for_sms else None
            beneficiary_phone = (
                (applicant_for_sms.phone_number or '').strip() if applicant_for_sms else ''
            )
            explanation_case = {
                'review_id': str(rev.id),
                'trigger_kind': rev.trigger_kind,
                'letter_deadline_at': _iso,
                'letter_deadline_display': _disp,
                'letter_deadline_local_input': _local_inp,
                'has_letter_document': has_doc,
                'can_set_deadline': deadline is None and not has_doc,
                'can_upload_letter': bool(deadline) and not has_doc,
                'can_disqualify': bool(
                    (deadline and deadline_passed and not has_doc) or extension_final_visit_failed
                ),
                'beneficiary_has_phone': bool(beneficiary_phone),
                'can_send_explanation_sms': bool(beneficiary_phone and not has_doc),
                'letter_document_url': (
                    rev.letter_document.url
                    if has_doc and rev.letter_document
                    else None
                ),
            }
            if explanation_case['can_disqualify']:
                ex_row_status = (
                    'Extension final visit — Failed (blacklist beneficiary available)'
                    if extension_final_visit_failed
                    else 'Deadline passed — no letter on file'
                )
            elif explanation_case['has_letter_document']:
                ex_row_status = 'Letter on file'
            elif explanation_case['letter_deadline_at']:
                ex_row_status = 'Awaiting scanned letter'
            else:
                ex_row_status = 'Register office deadline'
            if explanation_case['letter_deadline_at']:
                ex_detail = (
                    f"Office deadline {timezone.localtime(deadline).strftime('%b %d, %Y %I:%M %p')}. "
                    'After a compliant letter is on file, the beneficiary receives another 30 days to build; '
                    'if the deadline passes with no letter, staff may disqualify.'
                )
            else:
                ex_detail = (
                    'Opened when the final 30 Day Inspection was marked No Progress (not the 60 Day). '
                    'Set the letter deadline in the panel below, notify by SMS, then scan the letter to grant another 30 days to build.'
                )
            compliance_records.insert(0, {
                'title': 'Final 30 Day No Progress — explanation letter',
                'status': ex_row_status,
                'detail': ex_detail,
            })

        explanation_letter_view_url = None
        if active_lot_award and pending_explanation_rev is None:
            for _r in (
                ExplanationReview.objects.filter(lot_award=active_lot_award)
                .select_related('triggered_by_report__task')
                .order_by('-updated_at')
            ):
                if not _explanation_review_triggered_by_day30_inspection(_r):
                    continue
                if _r.letter_document and getattr(_r.letter_document, 'name', None):
                    explanation_letter_view_url = _r.letter_document.url
                    break

        explanation_letter_workflow_applies = bool(
            active_lot_award
            and (explanation_case or explanation_letter_view_url)
        )

        can_add_household_members = bool(
            applicant_for_household
            and request.user.position in _MODULE4_MONITORING_COMPLIANCE_STAFF
        )

        is_housing_unit_on_file = housing_unit_on_file(active_lot_award, progress)

        beneficiary_phone = ''
        if applicant_for_household:
            beneficiary_phone = (applicant_for_household.phone_number or '').strip()
        can_send_beneficiary_sms = bool(
            active_lot_award
            and applicant_for_household
            and request.user.position in _MODULE4_MONITORING_COMPLIANCE_STAFF
        )
        beneficiary_sms_compose = None
        if can_send_beneficiary_sms:
            default_body, _default_event = _unit_beneficiary_sms_message(
                unit, applicant_for_household, active_lot_award, progress
            )
            beneficiary_sms_compose = {
                'applicant_id': str(applicant_for_household.id),
                'full_name': applicant_for_household.full_name or '',
                'reference_number': applicant_for_household.reference_number or '',
                'phone_number': beneficiary_phone,
                'default_message': default_body or '',
            }

        module5_cases = module5_case_rows_for_unit(
            unit,
            applicant_for_household,
            position=position,
        )
        record_case_query = {}
        if applicant_for_household:
            record_case_query['applicant_id'] = str(applicant_for_household.id)
        record_case_query['unit_id'] = str(unit.id)
        record_case_query['new_case'] = '1'

        return JsonResponse({
            'success': True,
            'unit': {
                'id': str(unit.id),
                'block': unit.block_number,
                'lot': unit.lot_number,
                'status': unit.status,
                'is_housing_unit_on_file': is_housing_unit_on_file,
                'status_display': (
                    'Housing unit'
                    if is_housing_unit_on_file
                    else (
                        'Failed'
                        if extension_final_visit_failed
                        else unit.status
                    )
                ),
                'occupant_name': unit.occupant_name or '',
                'occupant_id': unit.occupant_id or '',
                'is_escalated': unit.is_escalated,
                'extension_final_visit_failed': extension_final_visit_failed,
                'lot_award_id': str(active_lot_award.id) if active_lot_award else None,
                'beneficiary_has_phone': bool(beneficiary_phone),
                'can_send_beneficiary_sms': can_send_beneficiary_sms,
                'beneficiary_sms_compose': beneficiary_sms_compose,
                'can_add_household_members': can_add_household_members,
                'household_relationship_options': _HOUSEHOLD_RELATIONSHIP_OPTIONS,
                'notice': notice_info,
                'weekly_report': weekly_report,
                'construction': (
                    {
                        'stage': progress.stage,
                        'stage_label': progress.get_stage_display(),
                        'percent_complete': progress.percent_complete,
                        'last_inspected_at': progress.last_inspected_at.isoformat() if progress.last_inspected_at else None,
                        'is_delayed': progress.is_delayed,
                        'expected_completion_date': progress.expected_completion_date.isoformat() if progress.expected_completion_date else None,
                    } if progress else None
                ),
                'construction_updates': updates,
                'can_update_construction': can_update_construction,
                'possession_info': possession_info,
                'beneficiary_info': beneficiary_info,
                'monitoring_tasks': monitoring_tasks,
                'explanation_extension_final_task': explanation_extension_final_task,
                'monitoring_history': monitoring_history,
                'compliance_records': compliance_records,
                'explanation_letter_case': explanation_case,
                'explanation_letter_view_url': explanation_letter_view_url,
                'explanation_letter_workflow_applies': explanation_letter_workflow_applies,
                'explanation_build_extension': explanation_build_extension,
                'construction_monitoring': {
                    'site_name': unit.site.name if unit.site else '',
                    'status_filter': cm_filter,
                    'count_not_started': count_not_started,
                    'count_in_progress': count_in_progress,
                    'count_completed': count_completed,
                    'count_delayed': count_delayed,
                    'rows': site_rows_payload,
                },
                'module5_cases': module5_cases,
                'module5_cases_url': cases_page_url(position),
                'module5_record_case_url': (
                    cases_page_url(position, **record_case_query)
                    if applicant_for_household
                    else None
                ),
            }
        })

    except HousingUnit.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Unit not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@verify_position
@require_POST
def add_household_member_for_unit(request, position, unit_id):
    """
    Module 4 unit detail: staff adds a HouseholdMember row for the active lot award applicant.
    """
    if request.user.position not in _MODULE4_MONITORING_COMPLIANCE_STAFF:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)

    full_name = (payload.get('full_name') or '').strip()
    relationship = (payload.get('relationship') or '').strip()
    sex_raw = (payload.get('sex') or '').strip().upper()[:1]
    sex = sex_raw if sex_raw in ('M', 'F') else ''
    age_raw = payload.get('age')
    try:
        age = int(age_raw) if age_raw is not None and str(age_raw).strip() != '' else 0
    except (TypeError, ValueError):
        age = 0
    if age < 0 or age > 120:
        return JsonResponse({'success': False, 'error': 'Age must be between 0 and 120.'}, status=400)

    valid_rel = {k for k, _ in HouseholdMember.RELATIONSHIP_CHOICES}
    if not full_name:
        return JsonResponse({'success': False, 'error': 'Full name is required.'}, status=400)
    if len(full_name) > 30:
        return JsonResponse({'success': False, 'error': 'Full name must be 30 characters or fewer.'}, status=400)
    if relationship not in valid_rel:
        return JsonResponse({'success': False, 'error': 'Choose a valid relationship to the beneficiary.'}, status=400)

    try:
        unit = HousingUnit.objects.get(id=unit_id)
    except HousingUnit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found'}, status=404)

    la = (
        LotAward.objects.filter(unit=unit, status='active')
        .select_related('application__applicant')
        .order_by('-awarded_at')
        .first()
    )
    applicant = getattr(getattr(la, 'application', None), 'applicant', None) if la else None
    if not applicant:
        return JsonResponse({
            'success': False,
            'error': 'No active lot award with a linked applicant for this unit.',
        }, status=400)

    try:
        member = HouseholdMember(
            applicant=applicant,
            full_name=full_name[:30],
            relationship=relationship,
            age=age,
            sex=sex,
        )
        member.full_clean()
        member.save()
    except ValidationError as e:
        parts = []
        if hasattr(e, 'error_dict') and e.error_dict:
            for errs in e.error_dict.values():
                parts.extend(str(x) for x in errs)
        else:
            parts = list(e.messages) if hasattr(e, 'messages') else [str(e)]
        return JsonResponse({'success': False, 'error': '; '.join(parts) or 'Validation failed.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({
        'success': True,
        'message': f'Added household member “{member.full_name}”.',
        'member': {
            'id': str(member.id),
            'name': member.full_name,
            'relationship': member.get_relationship_display(),
            'sex_display': member.get_sex_display() if member.sex else '—',
            'age': int(member.age) if member.age is not None else 0,
        },
    })


@login_required
@verify_position
@require_POST
def set_explanation_letter_deadline(request, position, unit_id):
    if request.user.position not in _MODULE4_MONITORING_COMPLIANCE_STAFF:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    deadline_local = (payload.get('deadline_local') or '').strip()
    raw_iso = payload.get('deadline') or payload.get('deadline_at')
    deadline = None
    if deadline_local:
        try:
            parsed_local = datetime.fromisoformat(deadline_local)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid deadline date and time.'}, status=400)
        if timezone.is_naive(parsed_local):
            try:
                office_tz = ZoneInfo(str(settings.TIME_ZONE))
            except Exception:
                office_tz = timezone.get_current_timezone()
            deadline = timezone.make_aware(parsed_local, office_tz)
        else:
            deadline = parsed_local
    elif raw_iso:
        deadline = parse_datetime(raw_iso)
        if deadline and timezone.is_naive(deadline):
            deadline = timezone.make_aware(deadline, timezone.get_current_timezone())
    if not deadline:
        return JsonResponse({
            'success': False,
            'error': 'Choose a deadline date and time (housing office local time).',
        }, status=400)
    if deadline <= timezone.now():
        return JsonResponse({'success': False, 'error': 'Deadline must be in the future.'}, status=400)
    notify = bool(payload.get('notify_beneficiary', True))

    try:
        unit = HousingUnit.objects.get(id=unit_id)
    except HousingUnit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found'}, status=404)

    la = (
        LotAward.objects.filter(unit=unit, status='active')
        .select_related('application__applicant')
        .order_by('-awarded_at')
        .first()
    )
    if not la:
        return JsonResponse({'success': False, 'error': 'No active lot award for this unit.'}, status=400)

    rev = _active_pending_explanation_for_lot_award(la)
    if not rev:
        return JsonResponse({
            'success': False,
            'error': 'No pending explanation letter workflow for this unit. Mark the monitoring report as No Progress first.',
        }, status=400)
    if not _explanation_review_triggered_by_day30_inspection(rev):
        return JsonResponse({
            'success': False,
            'error': 'Explanation letter workflow applies only after the 30 Day Inspection is marked No Progress.',
        }, status=400)
    if rev.letter_document:
        return JsonResponse({'success': False, 'error': 'Letter already uploaded for this case.'}, status=400)
    if ExtensionRecord.objects.filter(explanation_review=rev).exists():
        return JsonResponse({'success': False, 'error': 'Extension already granted; deadline cannot be changed.'}, status=400)

    rev.letter_deadline_at = deadline
    rev.save(update_fields=['letter_deadline_at', 'updated_at'])

    sms_sent = False
    if notify:
        applicant = la.application.applicant
        phone = (applicant.phone_number or '').strip()
        if phone:
            body, event = _explanation_letter_sms_for_case(unit, applicant, rev)
            if body:
                sms_sent = bool(send_sms(phone, body, event, applicant=applicant, module='units'))

    _iso, _disp, _local_inp = _explanation_letter_deadline_office_payload(rev.letter_deadline_at)
    return JsonResponse({
        'success': True,
        'letter_deadline_at': _iso,
        'letter_deadline_display': _disp,
        'letter_deadline_local_input': _local_inp,
        'sms_sent': sms_sent,
    })


@login_required
@verify_position
@require_POST
def send_unit_beneficiary_sms(request, position, unit_id):
    """Staff-triggered SMS to the active lot award beneficiary (footer Send SMS modal)."""
    if request.user.position not in _MODULE4_MONITORING_COMPLIANCE_STAFF:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)

    message = (payload.get('message') or '').strip()
    if len(message) < 10:
        return JsonResponse({
            'success': False,
            'error': 'Message must be at least 10 characters.',
        }, status=400)
    if len(message) > 900:
        return JsonResponse({
            'success': False,
            'error': 'Message must be 900 characters or fewer.',
        }, status=400)

    phone_raw = (payload.get('phone_number') or '').strip()
    save_phone = bool(payload.get('save_phone_to_applicant', True))

    try:
        unit = HousingUnit.objects.get(id=unit_id)
    except HousingUnit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found'}, status=404)

    la = (
        LotAward.objects.filter(unit=unit, status='active')
        .select_related('application__applicant')
        .order_by('-awarded_at')
        .first()
    )
    if not la:
        return JsonResponse({'success': False, 'error': 'No active lot award for this unit.'}, status=400)

    application = getattr(la, 'application', None)
    if not application:
        return JsonResponse({'success': False, 'error': 'Lot award has no linked application.'}, status=400)
    applicant = getattr(application, 'applicant', None)
    if not applicant:
        return JsonResponse({'success': False, 'error': 'Application has no linked beneficiary record.'}, status=400)

    phone = format_phone_number(phone_raw or (applicant.phone_number or ''))
    if not phone.startswith('09') or len(phone) != 11:
        return JsonResponse({
            'success': False,
            'error': 'Enter a valid Philippine mobile number (09XXXXXXXXX).',
        }, status=400)

    progress = (
        ConstructionProgress.objects.filter(lot_award=la, lot_award__status='active').first()
    )
    default_body, default_event = _unit_beneficiary_sms_message(unit, applicant, la, progress)
    if message == (default_body or '').strip():
        body, event = default_body, default_event
    else:
        body, event = message, 'unit_beneficiary_manual'

    if not body:
        return JsonResponse({'success': False, 'error': 'SMS is not applicable for this case.'}, status=400)

    phone_updated = False
    if save_phone and phone != format_phone_number(applicant.phone_number or ''):
        applicant.phone_number = phone
        applicant.save(update_fields=['phone_number', 'updated_at'])
        phone_updated = True

    sent = send_sms(phone, body, event, applicant=applicant, module='units')
    if not sent:
        return JsonResponse({
            'success': False,
            'error': 'SMS could not be sent. Check the phone number format and Semaphore configuration.',
        }, status=502)

    return JsonResponse({
        'success': True,
        'sms_sent': True,
        'phone_updated': phone_updated,
        'phone_number': phone,
        'message': (
            'SMS sent to the beneficiary. Contact number updated on file.'
            if phone_updated
            else 'SMS sent to the beneficiary.'
        ),
    })


send_explanation_letter_sms = send_unit_beneficiary_sms


@login_required
@verify_position
@require_POST
def upload_explanation_letter(request, position, unit_id):
    if request.user.position not in _MODULE4_MONITORING_COMPLIANCE_STAFF:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    f = request.FILES.get('letter_file') or request.FILES.get('file')
    if not f:
        return JsonResponse({'success': False, 'error': 'letter_file is required.'}, status=400)

    try:
        unit = HousingUnit.objects.get(id=unit_id)
    except HousingUnit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found'}, status=404)

    la = LotAward.objects.filter(unit=unit, status='active').order_by('-awarded_at').first()
    if not la:
        return JsonResponse({'success': False, 'error': 'No active lot award for this unit.'}, status=400)

    rev = _active_pending_explanation_for_lot_award(la)
    if not rev:
        return JsonResponse({'success': False, 'error': 'No pending explanation case.'}, status=400)
    if not _explanation_review_triggered_by_day30_inspection(rev):
        return JsonResponse({
            'success': False,
            'error': 'Explanation letter workflow applies only after the 30 Day Inspection is marked No Progress.',
        }, status=400)
    if not rev.letter_deadline_at:
        return JsonResponse({'success': False, 'error': 'Set the submission deadline before scanning the letter.'}, status=400)
    if rev.letter_document:
        return JsonResponse({'success': False, 'error': 'Letter already on file.'}, status=400)

    with transaction.atomic():
        locked = ExplanationReview.objects.select_for_update().get(pk=rev.pk)
        if locked.letter_document:
            return JsonResponse({'success': False, 'error': 'Letter already on file.'}, status=400)
        locked.letter_document = f
        locked.save(update_fields=['letter_document', 'updated_at'])
        _grant_monitoring_extension_from_explanation_review(locked, request.user)

    return JsonResponse({
        'success': True,
        'message': 'Explanation letter stored. A 60-day extension and monitoring tasks were created.',
    })


@login_required
@verify_position
@require_POST
def disqualify_beneficiary_monitoring(request, position, unit_id):
    if request.user.position not in _MODULE4_MONITORING_COMPLIANCE_STAFF:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    reason = (payload.get('reason') or '').strip()
    if len(reason) < 10:
        return JsonResponse({'success': False, 'error': 'reason must be at least 10 characters.'}, status=400)

    try:
        unit = HousingUnit.objects.get(id=unit_id)
    except HousingUnit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found'}, status=404)

    la = (
        LotAward.objects.filter(unit=unit, status='active')
        .select_related('application__applicant')
        .order_by('-awarded_at')
        .first()
    )
    if not la:
        return JsonResponse({'success': False, 'error': 'No active lot award for this unit.'}, status=400)

    application = getattr(la, 'application', None)
    if not application:
        return JsonResponse({'success': False, 'error': 'Lot award has no linked application.'}, status=400)
    applicant = getattr(application, 'applicant', None)
    if not applicant:
        return JsonResponse({'success': False, 'error': 'Application has no linked beneficiary record.'}, status=400)

    extension_final_failed = _month_2_inspection_marked_no_progress(la)

    rev = _active_pending_explanation_for_lot_award(la)
    if not rev and extension_final_failed:
        rev = _latest_day30_triggered_explanation_review(la)
    if not rev:
        return JsonResponse({'success': False, 'error': 'No explanation letter case found for this lot award.'}, status=400)
    if not _explanation_review_triggered_by_day30_inspection(rev):
        return JsonResponse({
            'success': False,
            'error': 'Explanation letter workflow applies only after the 30 Day Inspection is marked No Progress.',
        }, status=400)
    if not extension_final_failed:
        if not rev.letter_deadline_at:
            return JsonResponse({
                'success': False,
                'error': 'A deadline must be recorded before blacklisting for non-compliance.',
            }, status=400)
        now = timezone.now()
        if not (rev.letter_deadline_at < now and not rev.letter_document):
            return JsonResponse({
                'success': False,
                'error': 'Blacklist beneficiary is available only after the explanation letter deadline has passed with no letter on file.',
            }, status=400)

    if Blacklist.objects.filter(applicant_id=applicant.pk).exists():
        return JsonResponse({
            'success': False,
            'error': 'This applicant is already on the Blacklisted Beneficiaries registry.',
        }, status=400)

    with transaction.atomic():
        locked_rev = ExplanationReview.objects.select_for_update().get(pk=rev.pk)
        if locked_rev.letter_document and not extension_final_failed:
            return JsonResponse({'success': False, 'error': 'A letter is now on file; blacklist beneficiary is no longer applicable.'}, status=400)
        if not extension_final_failed:
            if not (locked_rev.letter_deadline_at and locked_rev.letter_deadline_at < timezone.now()):
                return JsonResponse({'success': False, 'error': 'Deadline has not passed yet.'}, status=400)

        locked_applicant = Applicant.objects.select_for_update().get(pk=applicant.pk)
        if locked_applicant.status == 'disqualified':
            return JsonResponse({'success': False, 'error': 'Applicant is already disqualified.'}, status=400)
        locked_applicant.status = 'disqualified'
        locked_applicant.disqualification_reason = reason
        locked_applicant.save(update_fields=['status', 'disqualification_reason', 'updated_at'])

        locked_rev.review_status = 'denied'
        locked_rev.staff_decision_notes = reason
        locked_rev.reviewed_by = request.user
        locked_rev.reviewed_at = timezone.now()
        locked_rev.save(
            update_fields=['review_status', 'staff_decision_notes', 'reviewed_by', 'reviewed_at', 'updated_at']
        )

        Blacklist.objects.create(
            applicant=locked_applicant,
            original_lot_award=la,
            original_unit=unit,
            reason='repossession',
            reason_details=reason,
            blacklisted_by=request.user,
            supporting_notes=(
                'Module 4 — Extension final monitoring visit (after explanation letter) assessed Failed; '
                'beneficiary disqualified from the awarded lot per staff decision.'
            )
            if extension_final_failed
            else (
                'Module 4 — Final 30 Day No Progress: explanation letter office deadline passed '
                'with no scanned or uploaded letter on file; beneficiary disqualified from the awarded lot.'
            ),
        )

        locked_la = LotAward.objects.select_for_update().get(pk=la.pk)
        now_ts = timezone.now()
        locked_la.status = 'repossessed'
        locked_la.ended_at = now_ts
        locked_la.end_reason = (
            (
                'Extension final monitoring visit assessed Failed (lot build not substantially complete at final '
                f'extension inspection). Staff notes: {reason[:1500]}'
            )
            if extension_final_failed
            else (
                'Explanation letter non-compliance after 30 Day No Progress (deadline passed, no letter on file). '
                f'Staff notes: {reason[:1500]}'
            )
        )
        locked_la.save(update_fields=['status', 'ended_at', 'end_reason'])

        OccupancyMonitoringCycle.objects.filter(
            lot_award_id=locked_la.pk,
            is_active=True,
        ).update(is_active=False)

        MonitoringTask.objects.filter(
            lot_award_id=locked_la.pk,
            status__in=['pending', 'overdue'],
        ).update(status='cancelled')

        locked_unit = HousingUnit.objects.select_for_update().get(pk=unit.pk)
        locked_unit.status = 'Vacant — available'
        locked_unit.occupant_name = ''
        locked_unit.occupant_id = None
        locked_unit.notice_type = None
        locked_unit.notice_date_issued = None
        locked_unit.notice_deadline = None
        locked_unit.is_escalated = False
        locked_unit.escalation_reason = ''
        locked_unit.save(
            update_fields=[
                'status',
                'occupant_name',
                'occupant_id',
                'notice_type',
                'notice_date_issued',
                'notice_deadline',
                'is_escalated',
                'escalation_reason',
                'updated_at',
            ]
        )

    if unit.site_id:
        _sync_site_housing_unit_occupancy(unit.site)

    return JsonResponse({
        'success': True,
        'message': (
            'Beneficiary blacklisted (disqualified), added to Blacklisted Beneficiaries, and removed from this block/lot. '
            'The lot award was repossessed and the unit is vacant for reassignment.'
        ),
    })


@login_required
@verify_position
@require_POST
def issue_compliance_notice(request, position):
    """
    AJAX endpoint to issue a compliance notice to a housing unit
    Updates unit status and sends SMS notification

    URL: /units/<position>/notice/issue/

    POST data:
    - unit_id: UUID
    - notice_type: '7-day', '15-day', or '30-day'
    - reason: Text reason for notice
    """
    try:
        data = json.loads(request.body)

        unit_id = data.get('unit_id')
        notice_type = data.get('notice_type')
        reason = data.get('reason', '')

        if not all([unit_id, notice_type]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields: unit_id, notice_type'
            })

        if notice_type not in ['7-day', '15-day', '30-day']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid notice type. Must be "7-day", "15-day", or "30-day"'
            })

        # Get unit
        unit = HousingUnit.objects.get(id=unit_id)

        active_award = (
            LotAward.objects
            .filter(unit=unit, status='active')
            .select_related('application__applicant')
            .order_by('-awarded_at')
            .first()
        )
        if not _unit_has_notice_subject(unit, active_award):
            return JsonResponse(
                {
                    'success': False,
                    'error': (
                        'Cannot issue a compliance notice: this lot has no active award '
                        'and no recorded occupant. Assign or record an occupant first.'
                    ),
                },
                status=400,
            )

        # Update unit status and notice
        unit.notice_type = notice_type
        unit.notice_date_issued = timezone.now()

        notice_days = {
            '7-day': 7,
            '15-day': 15,
            '30-day': 30,
        }
        days = notice_days[notice_type]
        # Keep a single monitored status family while notice_type carries exact day window.
        unit.status = 'Under notice (30-day)'
        unit.notice_deadline = (timezone.now() + timedelta(days=days)).date()

        unit.save()

        # Send SMS to occupant if available
        # (Would integrate with send_sms() utility if occupant phone is available)
        message_text = (
            f"Notice: Your unit at Block {unit.block_number} Lot {unit.lot_number} has been flagged. "
            f"You have {days} days to visit the Housing Office and submit an explanation."
        )

        return JsonResponse({
            'success': True,
            'message': f'✓ {notice_type.title()} notice issued to Block {unit.block_number}, Lot {unit.lot_number}',
            'unit': {
                'id': str(unit.id),
                'status': unit.status,
                'notice_deadline': unit.notice_deadline.isoformat(),
            }
        })

    except HousingUnit.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Unit not found'
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


@login_required
@verify_position
@require_POST
def add_construction_update(request, position):
    """
    Append a construction progress update (timeline) for an occupied unit with an active lot award.
    """
    if request.user.position not in (_MODULE4_ADD_HOUSING_UNIT_POSITIONS | FIELD_DESK_POSITIONS):
        return JsonResponse({'success': False, 'error': 'Access denied.'}, status=403)

    unit_id = (request.POST.get('unit_id') or '').strip()
    stage = (request.POST.get('stage') or '').strip()
    percent_raw = (request.POST.get('percent_complete') or '').strip()
    visit_date_raw = (request.POST.get('visit_date') or '').strip()
    notes = (request.POST.get('notes') or '').strip()[:2000]

    if not unit_id or not stage or not percent_raw or not visit_date_raw:
        return JsonResponse({'success': False, 'error': 'Missing required fields.'}, status=400)

    try:
        percent = int(percent_raw)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Percent must be a whole number.'}, status=400)

    if percent < 0 or percent > 100:
        return JsonResponse({'success': False, 'error': 'Percent must be between 0 and 100.'}, status=400)

    try:
        visit_date = datetime.fromisoformat(visit_date_raw).date()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Visit date must be YYYY-MM-DD.'}, status=400)

    if stage not in dict(ConstructionProgress.STAGE_CHOICES):
        return JsonResponse({'success': False, 'error': 'Invalid stage.'}, status=400)

    unit = HousingUnit.objects.filter(id=unit_id).first()
    if not unit:
        return JsonResponse({'success': False, 'error': 'Unit not found.'}, status=404)

    active_award = unit.lot_awards.filter(status='active').first()
    if not active_award:
        return JsonResponse({'success': False, 'error': 'No active lot award for this unit.'}, status=400)

    progress, _ = ConstructionProgress.objects.get_or_create(
        lot_award=active_award,
        defaults={'stage': 'not_started', 'percent_complete': 0, 'updated_by': request.user},
    )

    with transaction.atomic():
        from units.models import ConstructionProgressUpdate
        ConstructionProgressUpdate.objects.create(
            progress=progress,
            stage=stage,
            percent_complete=percent,
            visit_date=visit_date,
            notes=notes,
            created_by=request.user,
        )
        progress.stage = stage
        progress.percent_complete = percent
        progress.last_inspected_at = timezone.now()
        progress.updated_by = request.user
        progress.save(update_fields=['stage', 'percent_complete', 'last_inspected_at', 'updated_by', 'updated_at'])

    return JsonResponse({'success': True})


# ===================================================================
# CASE MANAGEMENT (Module 5 - Case Management Dashboard)
# ===================================================================

@login_required
@verify_position
def case_management(request, position):
    """
    Legacy URL: /units/cases/<position>/

    Case management UI and primary data model live in the ``cases`` app
    (``/accounts/second-member/cases/``, ``/accounts/field/cases/``; legacy ``/cases/<position>/`` redirects).
    Legacy ``/units/cases/`` JSON paths proxy to ``cases.views`` (see ``units.urls``).
    """
    return redirect('cases:case_dashboard', position=position)


# Legacy CaseRecord create/update/details handlers removed — use cases app.


@login_required
@verify_position
@login_required
@verify_position
def blacklist_management(request, position):
    """
    Renders the blacklist ledger showing all permanently disqualified applicants.
    """
    search_query = request.GET.get('search', '').strip()
    
    queryset = Blacklist.objects.select_related('applicant', 'blacklisted_by')
    
    if search_query:
        queryset = queryset.filter(
            models.Q(applicant__first_name__icontains=search_query)
            | models.Q(applicant__last_name__icontains=search_query)
            | models.Q(applicant__full_name__icontains=search_query)
            | models.Q(applicant__reference_number__icontains=search_query)
        )
        
    queryset = queryset.order_by('-blacklisted_at')
    
    import re
    # Clean and generate beautiful, highly readable administrative prose for all blacklist records
    for item in queryset:
        # 1. Format the official system notes (supporting_notes)
        notes = (item.supporting_notes or '').strip()
        if 'Extension final monitoring visit' in notes or 'Extension final monitoring' in notes or 'Extension final' in notes:
            item.formatted_notes = (
                "Failed to meet house construction progress compliance standards during the "
                "final extension monitoring phase. The housing lot has been repossessed and "
                "the beneficiary permanently disqualified."
            )
        elif 'Final 30 Day No Progress' in notes or 'deadline passed' in notes or 'Final 30 Day' in notes:
            item.formatted_notes = (
                "Failed to submit the required written explanation letter within the official "
                "30-day grace period for non-compliance (No Progress). The housing lot has been "
                "repossessed and the beneficiary permanently disqualified."
            )
        else:
            item.formatted_notes = notes or "Disqualified due to resettlement housing program policy violations."
            
        # 2. Format and clean up custom staff remarks (reason_details)
        details = (item.reason_details or '').strip()
        # Detect if details are gibberish (e.g. "tessstttttt", "Testttssssssssssssssssssssssss", or similar repetitive or extremely short non-prose)
        is_gibberish = False
        if len(details) < 15:
            # Short typical placeholder/test inputs
            if re.match(r'^(test+|tess+t+|asdf+|qwerty+|xyz+|123+|ok+|none+|n/a+)$', details, re.IGNORECASE):
                is_gibberish = True
        if len(details) >= 15 and len(set(details.lower())) <= 6:
            # Low character entropy (e.g. repeated letters like 'testsssssssssssssssss')
            is_gibberish = True
            
        if is_gibberish or not details:
            item.formatted_details = (
                "Official record: Housing construction progress was determined as non-compliant "
                "with the Talisay Housing Authority resettlement development guidelines."
            )
        else:
            # Clean up the formatting of real details (e.g. ensure sentence case, strip extra whitespace)
            if details:
                cleaned = details[0].upper() + details[1:]
                item.formatted_details = cleaned
            else:
                item.formatted_details = "No additional staff remarks provided."
    
    # We could add pagination here if needed, but keeping it simple for now
    
    # Paginate — 10 records per page
    from django.core.paginator import Paginator
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'blacklists': page_obj,
        'page_obj': page_obj,
        'search': search_query,
    }
    return render(request, 'units/blacklist_management.html', context)


# =============================================================================
# PHASE 3: CARETAKER MONITORING DASHBOARD
# =============================================================================

@login_required
@require_POST
def notify_monitoring_task(request, task_id):
    """
    Mark a scheduled monitoring task as notified so the field desk dashboard can
    surface it for planning before the official inspection date.
    """
    allowed_positions = _MODULE4_ADD_HOUSING_UNIT_POSITIONS | FIELD_DESK_POSITIONS
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        task = MonitoringTask.objects.select_related('unit', 'lot_award').get(id=task_id)
    except MonitoringTask.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)

    if task.task_type == TASK_TYPE_EXTENSION_MIDPOINT:
        m2 = (
            MonitoringTask.objects
            .filter(lot_award=task.lot_award, task_type=TASK_TYPE_EXTENSION_FINAL)
            .first()
        )
        m2_report = m2.reports.order_by('-submitted_at').first() if m2 else None
        if not (
            m2
            and m2.status == 'completed'
            and m2_report
            and m2_report.progress_assessment
        ):
            return JsonResponse({
                'success': False,
                'error': (
                    'Extension 60 Day midpoint is locked until the extension 30 Day Inspection '
                    'is completed and reviewed by staff.'
                ),
            }, status=400)

    if task.task_type == TASK_TYPE_FINAL_INSPECTION:
        initial_task = (
            MonitoringTask.objects
            .filter(lot_award=task.lot_award, task_type=TASK_TYPE_INITIAL_INSPECTION)
            .first()
        )
        initial_report = initial_task.reports.order_by('-submitted_at').first() if initial_task else None
        if not (
            initial_task
            and initial_task.status == 'completed'
            and initial_report
            and initial_report.progress_assessment
        ):
            return JsonResponse({
                'success': False,
                'error': 'Day 30 is locked until the 60 Day Inspection is completed and reviewed by staff.',
            }, status=400)

    task.notified_at = timezone.now()
    task.notified_by = request.user
    task.save(update_fields=['notified_at', 'notified_by', 'updated_at'])

    return JsonResponse({
        'success': True,
        'message': f'{task.get_task_type_display()} notified and waiting for caretaker monitoring.',
        'notified_at': task.notified_at.isoformat(),
    })


def _active_pending_explanation_for_lot_award(lot_award):
    return (
        ExplanationReview.objects.filter(
            lot_award=lot_award,
            review_status='pending_review',
        )
        .select_related('triggered_by_report__task')
        .order_by('-created_at')
        .first()
    )


def _latest_day30_triggered_explanation_review(lot_award):
    """
    Most recent explanation case opened from a 30 Day No Progress assessment.
    Used when the letter workflow moved the review out of pending_review (e.g. approved
    after letter on file) but staff must still disqualify after extension final Failed.
    """
    if not lot_award:
        return None
    qs = (
        ExplanationReview.objects.filter(lot_award=lot_award)
        .select_related('triggered_by_report__task')
        .order_by('-updated_at', '-created_at')
    )
    for rev in qs:
        if _explanation_review_triggered_by_day30_inspection(rev):
            return rev
    return None


def _explanation_review_triggered_by_day30_inspection(rev):
    """True when the case was opened from a 30 Day Inspection monitoring report."""
    if not rev or not rev.triggered_by_report_id:
        return False
    report = rev.triggered_by_report
    task = getattr(report, 'task', None)
    return bool(task and task.task_type == TASK_TYPE_FINAL_INSPECTION)


def _open_explanation_review_after_no_progress(report, _acting_user):
    """
    When staff marks the **30 Day** monitoring report as No Progress, open (or reuse)
    an explanation review and notify the beneficiary to submit a written explanation letter.

    If a pending explanation case already exists for this lot award, do not create a
    second case or send duplicate SMS.
    """
    if ExplanationReview.objects.filter(triggered_by_report=report).exists():
        return
    if _active_pending_explanation_for_lot_award(report.lot_award):
        return
    ExplanationReview.objects.create(
        lot_award=report.lot_award,
        unit=report.unit,
        triggered_by_report=report,
        review_status='pending_review',
        trigger_kind='staff_no_progress',
    )
    applicant = report.lot_award.application.applicant
    phone = (applicant.phone_number or '').strip()
    if not phone:
        return
    body, event = _explanation_letter_sms_for_case(report.unit, applicant, None)
    if body:
        send_sms(phone, body, event, applicant=applicant, module='units')


def _grant_monitoring_extension_from_explanation_review(review, approved_by_user):
    """
    After staff uploads the explanation letter on file, grant a 60-day extension window
    with Month 1 / Month 2 monitoring tasks (extension 30 Day at day 30, midpoint at day 60).

    The extension must begin only after initial monitoring has finished: the first day
    of the build extension is the calendar day after the letter is received, and is
    never earlier than the day after the original 30 Day inspection due date that
    triggered this case.
    """
    if ExtensionRecord.objects.filter(explanation_review=review).exists():
        return
    now = timezone.now()
    today = now.date()
    lot_award = review.lot_award
    unit = review.unit
    caretaker = unit.site.caretaker if unit.site else None

    day30_due = None
    trig = getattr(review, 'triggered_by_report', None)
    if trig:
        t0 = getattr(trig, 'task', None)
        if t0 and t0.task_type == TASK_TYPE_FINAL_INSPECTION and t0.due_date:
            day30_due = t0.due_date
    if day30_due is None:
        d30 = (
            MonitoringTask.objects.filter(
                lot_award=lot_award,
                task_type=TASK_TYPE_FINAL_INSPECTION,
            )
            .order_by('-due_date')
            .first()
        )
        if d30 and d30.due_date:
            day30_due = d30.due_date

    earliest_start = day30_due + timedelta(days=1) if day30_due else today + timedelta(days=1)
    # First build-extension day: day after letter on file, but not before initial 30 Day window has ended.
    start = max(today + timedelta(days=1), earliest_start)
    end = start + timedelta(days=EXTENSION_BUILD_DAYS)

    with transaction.atomic():
        review.letter_received_at = now
        review.review_status = 'approved'
        review.extension_approved = True
        review.extension_months = 1
        review.reviewed_by = approved_by_user
        review.reviewed_at = now
        review.staff_decision_notes = (review.staff_decision_notes or '').strip()
        if not review.staff_decision_notes:
            review.staff_decision_notes = 'Written explanation letter received and scanned on file.'
        review.save(
            update_fields=[
                'letter_received_at',
                'review_status',
                'extension_approved',
                'extension_months',
                'reviewed_by',
                'reviewed_at',
                'staff_decision_notes',
                'updated_at',
            ]
        )

        ExtensionRecord.objects.create(
            lot_award=lot_award,
            explanation_review=review,
            extension_duration_months=1,
            extension_start_date=start,
            extension_end_date=end,
            approved_by=approved_by_user,
            approval_notes='60-day extension after explanation letter compliance.',
        )

        OccupancyMonitoringCycle.objects.filter(lot_award=lot_award, is_active=True).update(is_active=False)
        OccupancyMonitoringCycle.objects.create(
            lot_award=lot_award,
            cycle_stage='extension_month_1',
            stage_start_date=start,
            stage_end_date=end,
            days_allowed=EXTENSION_BUILD_DAYS,
            is_active=True,
        )

        MonitoringTask.objects.create(
            unit=unit,
            lot_award=lot_award,
            task_type=TASK_TYPE_EXTENSION_MIDPOINT,
            scheduled_date=start + timedelta(days=EXTENSION_MIDPOINT_INSPECTION_OFFSET_DAYS),
            due_date=start + timedelta(days=EXTENSION_MIDPOINT_INSPECTION_OFFSET_DAYS),
            days_from_award=EXTENSION_MIDPOINT_INSPECTION_OFFSET_DAYS,
            status='pending',
            assigned_to=caretaker,
        )
        MonitoringTask.objects.create(
            unit=unit,
            lot_award=lot_award,
            task_type=TASK_TYPE_EXTENSION_FINAL,
            scheduled_date=start + timedelta(days=EXTENSION_FINAL_INSPECTION_OFFSET_DAYS),
            due_date=start + timedelta(days=EXTENSION_FINAL_INSPECTION_OFFSET_DAYS),
            days_from_award=EXTENSION_FINAL_INSPECTION_OFFSET_DAYS,
            status='pending',
            assigned_to=caretaker,
        )


def _complete_original_program_on_day30_normal_progress(task, acting_user):
    """
    When staff marks the Day 30 report as Normal Progress while the original 30-day
    monitoring cycle is still active (no extension cycle running), close out that
    cycle, finalize construction progress for the awarded lot (lot → housing unit on
    file), and clear monitoring escalation on the unit row.
    """
    if task.task_type != TASK_TYPE_FINAL_INSPECTION:
        return None
    lot_award = task.lot_award
    unit = task.unit
    now_dt = timezone.now()
    today = now_dt.date()

    if OccupancyMonitoringCycle.objects.filter(
        lot_award=lot_award,
        is_active=True,
    ).exclude(cycle_stage='original_30_day').exists():
        return None

    cycles_closed = OccupancyMonitoringCycle.objects.filter(
        lot_award=lot_award,
        is_active=True,
        cycle_stage='original_30_day',
    ).update(is_active=False)

    progress, _ = ConstructionProgress.objects.get_or_create(
        lot_award=lot_award,
        defaults={'stage': 'not_started', 'percent_complete': 0, 'updated_by': acting_user},
    )
    ConstructionProgressUpdate.objects.create(
        progress=progress,
        stage='completed',
        percent_complete=100,
        visit_date=today,
        notes='Day 30 inspection: Normal Progress — final monitoring complete; awarded lot recorded as housing unit with construction complete.',
        created_by=acting_user,
    )
    progress.stage = 'completed'
    progress.percent_complete = 100
    progress.last_inspected_at = now_dt
    progress.updated_by = acting_user
    progress.is_delayed = False
    progress.save(
        update_fields=[
            'stage',
            'percent_complete',
            'last_inspected_at',
            'updated_by',
            'is_delayed',
            'updated_at',
        ]
    )

    esc_fields = []
    if unit.is_escalated:
        unit.is_escalated = False
        esc_fields.append('is_escalated')
    if (unit.escalation_reason or '').strip():
        unit.escalation_reason = ''
        esc_fields.append('escalation_reason')
    if esc_fields:
        esc_fields.append('updated_at')
        unit.save(update_fields=esc_fields)

    return {
        'cycles_deactivated': cycles_closed,
        'construction_finalized': True,
    }


def _complete_extension_on_month2_normal_progress(task, acting_user):
    """
    When staff marks the extension final visit (month_2_inspection) as Housing unit,
    close active monitoring cycles and record construction complete for inventory.
    """
    if task.task_type != TASK_TYPE_EXTENSION_FINAL:
        return None
    lot_award = task.lot_award
    unit = task.unit
    now_dt = timezone.now()
    today = now_dt.date()

    cycles_closed = OccupancyMonitoringCycle.objects.filter(
        lot_award=lot_award,
        is_active=True,
    ).update(is_active=False)

    progress, _ = ConstructionProgress.objects.get_or_create(
        lot_award=lot_award,
        defaults={'stage': 'not_started', 'percent_complete': 0, 'updated_by': acting_user},
    )
    ConstructionProgressUpdate.objects.create(
        progress=progress,
        stage='completed',
        percent_complete=100,
        visit_date=today,
        notes=(
            'Extension final 30 Day visit: Housing unit — monitoring complete; '
            'awarded lot recorded as housing unit with construction complete.'
        ),
        created_by=acting_user,
    )
    progress.stage = 'completed'
    progress.percent_complete = 100
    progress.last_inspected_at = now_dt
    progress.updated_by = acting_user
    progress.is_delayed = False
    progress.save(
        update_fields=[
            'stage',
            'percent_complete',
            'last_inspected_at',
            'updated_by',
            'is_delayed',
            'updated_at',
        ]
    )

    esc_fields = []
    if unit.is_escalated:
        unit.is_escalated = False
        esc_fields.append('is_escalated')
    if (unit.escalation_reason or '').strip():
        unit.escalation_reason = ''
        esc_fields.append('escalation_reason')
    if esc_fields:
        esc_fields.append('updated_at')
        unit.save(update_fields=esc_fields)

    return {
        'cycles_deactivated': cycles_closed,
        'construction_finalized': True,
    }


@login_required
@require_POST
def assess_monitoring_report(request, task_id):
    """
    Staff marks a submitted caretaker monitoring report as normal progress or no progress.

    Day 30 + Normal Progress while the original monitoring cycle is active closes the
    award-cycle monitoring program and finalizes construction for the lot (housing unit framing).

    No Progress on the **30 Day Inspection** opens the explanation-letter workflow
    (deadline, scan, extension / disqualify). No Progress on the 60 Day Inspection does not.
    """
    allowed_positions = _MODULE4_ADD_HOUSING_UNIT_POSITIONS | FIELD_DESK_POSITIONS
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    decision = (request.POST.get('decision') or '').strip()
    valid_decisions = {'normal_progress', 'no_progress'}
    if decision not in valid_decisions:
        return JsonResponse({'success': False, 'error': 'Invalid progress assessment.'}, status=400)

    try:
        task = MonitoringTask.objects.select_related('unit', 'lot_award').get(id=task_id, status='completed')
    except MonitoringTask.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Completed monitoring task not found.'}, status=404)

    report = task.reports.order_by('-submitted_at').first()
    if not report:
        return JsonResponse({'success': False, 'error': 'No submitted monitoring report found.'}, status=404)

    program_payload = None
    with transaction.atomic():
        report.progress_assessment = decision
        report.assessed_by = request.user
        report.assessed_at = timezone.now()
        report.save(update_fields=['progress_assessment', 'assessed_by', 'assessed_at', 'updated_at'])

        if decision == 'no_progress' and task.task_type == TASK_TYPE_FINAL_INSPECTION:
            _open_explanation_review_after_no_progress(report, request.user)
        elif decision == 'normal_progress':
            program_payload = _complete_original_program_on_day30_normal_progress(task, request.user)
            if program_payload is None:
                program_payload = _complete_extension_on_month2_normal_progress(task, request.user)

    ext_failed = False
    if task.lot_award_id:
        ext_failed = _month_2_inspection_marked_no_progress(task.lot_award)

    payload = {
        'success': True,
        'decision': report.progress_assessment,
        'decision_label': _staff_progress_assessment_display(
            task.task_type, report.progress_assessment
        ),
        'assessed_at': report.assessed_at.isoformat(),
        'assessed_by': request.user.get_full_name() or request.user.username,
        'extension_final_visit_failed': ext_failed,
    }
    if program_payload:
        payload['monitoring_program_complete'] = True
        payload['housing_unit_on_file'] = True
        payload['monitoring_program_detail'] = program_payload
    return JsonResponse(payload)


def _module1_staff_handled_user(applicant):
    """Staff who proceeded from Module 1; falls back to encoder."""
    if not applicant:
        return None
    return getattr(applicant, 'module2_handoff_by', None) or getattr(applicant, 'registered_by', None)


def _enrich_monitoring_task_staff(task):
    """Attach staff-handled display fields for monitoring desk tables."""
    applicant = None
    lot_award = getattr(task, 'lot_award', None)
    application = getattr(lot_award, 'application', None) if lot_award else None
    if application:
        applicant = application.applicant
    user = _module1_staff_handled_user(applicant)
    task.staff_handled_user = user
    if not user:
        task.staff_initials = ''
        task.staff_name = ''
        task.staff_role = ''
        task.staff_position_key = ''
        return
    first = (user.first_name or '')[:1]
    last = (user.last_name or '')[:1]
    task.staff_initials = (first + last).upper() or '??'
    task.staff_name = user.get_full_name()
    if hasattr(user, 'get_position_display_short'):
        task.staff_role = user.get_position_display_short()
    else:
        task.staff_role = user.get_position_display()
    task.staff_position_key = getattr(user, 'position', '') or ''


def _enrich_monitoring_tasks_staff(tasks):
    for task in tasks:
        _enrich_monitoring_task_staff(task)


@login_required
def caretaker_monitoring_dashboard(request):
    """
    Caretaker/Ronda dashboard for viewing and submitting monitoring reports.
    Displays all assigned monitoring tasks with filtering and modal-based report submission.

    URL: /units/monitoring-dashboard/
    """
    # Restrict to field desk users. Unassigned tasks are visible to the shared desk.
    if request.user.position not in FIELD_DESK_POSITIONS:
        return HttpResponseForbidden("Only field desk staff can access this dashboard.")

    # Field desk only works on monitoring tasks that staff explicitly notified.
    today = timezone.now().date()
    tasks = MonitoringTask.objects.filter(
        models.Q(assigned_to_id=request.user.id) | models.Q(assigned_to__isnull=True),
        notified_at__isnull=False,
        status__in=['pending', 'overdue'],
    ).select_related(
        'unit',
        'lot_award',
        'lot_award__application__applicant',
        'lot_award__application__applicant__registered_by',
        'lot_award__application__applicant__module2_handoff_by',
        'unit__site',
        'assigned_to',
    ).order_by('notified_at', 'due_date', 'pk')

    # Calculate KPIs
    pending_count = tasks.filter(status='pending').count()
    overdue_count = tasks.filter(due_date__lt=today, status='pending').count()
    completed_count = MonitoringTask.objects.filter(
        models.Q(assigned_to_id=request.user.id) | models.Q(assigned_to__isnull=True),
        notified_at__isnull=False,
        status='completed'
    ).count()
    active_units = tasks.values('unit_id').distinct().count()

    tasks_list = list(tasks)
    _enrich_monitoring_tasks_staff(tasks_list)

    scheduled_tasks = [t for t in tasks_list if t.status == 'pending' and t.due_date >= today]
    overdue_tasks = [t for t in tasks_list if t.status == 'pending' and t.due_date < today]
    completed_tasks = MonitoringTask.objects.filter(
        models.Q(assigned_to_id=request.user.id) | models.Q(assigned_to__isnull=True),
        notified_at__isnull=False,
        status='completed'
    ).select_related(
        'unit',
        'lot_award',
        'lot_award__application__applicant',
        'lot_award__application__applicant__registered_by',
        'lot_award__application__applicant__module2_handoff_by',
        'unit__site',
        'assigned_to',
    ).prefetch_related(
        Prefetch(
            'reports',
            queryset=MonitoringReport.objects.select_related('submitted_by').order_by(
                '-submitted_at'
            ),
        )
    ).order_by('-completed_at', '-due_date')
    active_unit_tasks = sorted(
        tasks_list,
        key=lambda t: (t.unit_id, t.notified_at or timezone.now(), t.due_date, t.pk),
    )

    context = {
        'tasks': tasks_list,
        'pending_count': pending_count,
        'overdue_count': overdue_count,
        'completed_count': completed_count,
        'active_units': active_units,
        'scheduled_tasks': scheduled_tasks,
        'overdue_tasks': overdue_tasks,
        'completed_tasks': completed_tasks,
        'active_unit_tasks': active_unit_tasks,
        'today': today,
        'selected_task_id': (request.GET.get('task') or '').strip(),
        'task_notified': request.GET.get('notified') == '1',
    }

    return render(request, 'units/caretaker_monitoring_dashboard.html', context)


# =============================================================================
# PHASE 4: REPORT SUBMISSION
# =============================================================================

@login_required
@require_POST
def submit_monitoring_report(request, task_id):
    """
    Caretaker submits monitoring report for a specific task.
    Validates occupancy and construction status, then evaluates for auto-escalation.

    URL: /units/monitoring-report/<task_id>/submit/
    """
    if request.user.position not in FIELD_DESK_POSITIONS:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)

    try:
        task = MonitoringTask.objects.select_related(
            'unit', 'lot_award', 'lot_award__application__applicant'
        ).get(id=task_id)

        if task.assigned_to_id and task.assigned_to_id != request.user.id:
            return JsonResponse({
                'success': False,
                'error': 'This monitoring task is assigned to another staff member.',
            }, status=403)

        allow_early_inspection = request.POST.get('allow_early_inspection') == '1'
        if task.scheduled_date > timezone.now().date() and not allow_early_inspection:
            return JsonResponse({
                'success': False,
                'error': f'This monitoring task is scheduled on {task.scheduled_date}.',
            }, status=400)

        construction_status = request.POST.get('construction_status', '').strip()
        if construction_status == 'ongoing':
            construction_status = 'ongoing_construction'
        occupancy_radio = request.POST.get('occupancy_status', '').strip()

        if not construction_status:
            return JsonResponse({
                'success': False,
                'error': 'Construction status is required.'
            }, status=400)

        if not occupancy_radio:
            return JsonResponse({
                'success': False,
                'error': 'Occupancy status is required.'
            }, status=400)

        occupancy_notes = request.POST.get('occupancy_notes', '').strip()
        if len(occupancy_notes) < 8:
            if occupancy_radio == 'occupied':
                occupancy_notes = (
                    'Monitoring visit: caretaker classified the unit as properly occupied.'
                )
            else:
                occupancy_notes = (
                    'Monitoring visit: caretaker classified the unit as unoccupied.'
                )

        progress_notes = request.POST.get('progress_notes', '').strip()
        is_final_monitoring_task = task.task_type in (TASK_TYPE_FINAL_INSPECTION, TASK_TYPE_EXTENSION_FINAL)
        if is_final_monitoring_task:
            if construction_status == 'completed_occupied' and len(progress_notes) < 8:
                progress_notes = (
                    'Final monitoring visit: lot build appears finished on site.'
                )
            elif construction_status == 'no_structure' and len(progress_notes) < 8:
                progress_notes = (
                    'Final monitoring visit: no finished structure observed on site.'
                )
            elif not progress_notes:
                progress_notes = 'Final monitoring visit: construction status recorded.'
        elif construction_status == 'ongoing_construction':
            if len(progress_notes) < 8:
                progress_notes = (
                    'Monitoring visit: ongoing construction observed on site.'
                )
        elif not progress_notes:
            progress_notes = 'No construction progress.'


        photo_evidence_files = request.FILES.getlist('photo_evidence')
        if not photo_evidence_files:
            return JsonResponse({
                'success': False,
                'error': 'Photo evidence is required for monitoring reports.'
            }, status=400)
        if len(photo_evidence_files) > 4:
            return JsonResponse({
                'success': False,
                'error': 'Maximum of 4 photo evidence files allowed.'
            }, status=400)

        percent_by_status = {
            'no_structure': 0,
            'ongoing_construction': 25,
            'site_clearing': 10,
            'foundation': 25,
            'wall_framing': 50,
            'roofing': 75,
            'finishing': 90,
            'completed_occupied': 100,
        }
        percent_complete = percent_by_status.get(construction_status, 0)

        # Determine occupancy status from radio or notes
        if occupancy_radio == 'occupied':
            occupancy_status = 'properly_occupied'
        elif occupancy_radio == 'unoccupied':
            occupancy_status = 'unoccupied_abandoned'
        else:
            # Fallback to text analysis if for some reason radio is missing but notes exist
            occupancy_status = 'properly_occupied'
            occupancy_text = occupancy_notes.lower()
            if any(term in occupancy_text for term in ['abandon', 'unoccupied', 'empty', 'no occupant', 'no one']):
                occupancy_status = 'unoccupied_abandoned'
            elif any(term in occupancy_text for term in ['temporary', 'vacant', 'away']):
                occupancy_status = 'temporarily_vacant'

        # Create monitoring report
        with transaction.atomic():
            report = MonitoringReport.objects.create(
                task=task,
                lot_award=task.lot_award,
                unit=task.unit,
                submitted_by=request.user,
                occupancy_status=occupancy_status,
                construction_status=construction_status,
                percent_complete=percent_complete,
                people_observed=request.POST.get('people_observed', ''),
                occupancy_notes=occupancy_notes,
                progress_notes=progress_notes,
                photo_evidence=photo_evidence_files[0],
                general_remarks='',
                is_complete=True,
            )
            for photo in photo_evidence_files:
                report.photos.create(image=photo)

            stage_map = {
                'no_structure': 'not_started',
                'ongoing_construction': 'foundation',
                'site_clearing': 'site_clearing',
                'foundation': 'foundation',
                'wall_framing': 'wall_framing',
                'roofing': 'roofing',
                'finishing': 'finishing',
                'completed_occupied': 'completed',
            }
            stage = stage_map.get(construction_status, 'not_started')
            if is_final_monitoring_task and stage == 'completed' and percent_complete >= 100:
                stage = 'finishing'
                percent_complete = 90
            progress, _created = ConstructionProgress.objects.get_or_create(
                lot_award=task.lot_award,
                defaults={'updated_by': request.user},
            )
            progress.stage = stage
            progress.percent_complete = percent_complete
            progress.last_inspected_at = timezone.now()
            progress.updated_by = request.user
            if stage != 'not_started' and progress.started_at is None:
                progress.started_at = timezone.now()
            progress.save()
            progress.updates.create(
                stage=stage,
                percent_complete=percent_complete,
                visit_date=timezone.now().date(),
                notes=progress_notes,
                created_by=request.user,
            )

            # Mark task as completed
            if task.assigned_to_id is None:
                task.assigned_to = request.user
            task.status = 'completed'
            task.save()

            # Evaluate report for auto-escalation
            evaluation = _evaluate_monitoring_report(report)

            return JsonResponse({
                'success': True,
                'message': 'Report submitted successfully',
                'report_id': str(report.id),
                'evaluation': evaluation,
            })

    except MonitoringTask.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Task not found'}, status=404)
    except Exception as e:
        import sys
        sys.stderr.write(f"\n[ERROR] Failed to submit monitoring report: {str(e)}\n")
        sys.stderr.flush()
        return JsonResponse({
            'success': False,
            'error': f'Failed to submit report: {str(e)}'
        }, status=500)


# =============================================================================
# PHASE 5: EVALUATION ENGINE & AUTO-ESCALATION
# =============================================================================

def _evaluate_monitoring_report(report):
    """
    Evaluates monitoring report against three rules for auto-escalation.
    - Rule 1: Detect no progress at Day 30
    - Rule 2: Handle extension period failures
    - Rule 3: Continue normal monitoring if progress shown
    """
    result = {
        'status': 'unknown',
        'actions': [],
        'escalated': False,
    }

    try:
        lot_award = report.lot_award
        today = timezone.now().date()
        award_date = lot_award.awarded_at.date()
        days_since_award = (today - award_date).days

        # Find the active monitoring cycle
        monitoring_cycle = OccupancyMonitoringCycle.objects.filter(
            lot_award=lot_award, is_active=True
        ).first()

        if not monitoring_cycle:
            result['status'] = 'unknown'
            return result

        # RULE 1: Original 30-day period with no progress
        if (days_since_award >= 30 and
            monitoring_cycle.cycle_stage == 'original_30_day' and
            report.construction_status == 'no_structure' and
            report.occupancy_status in ['temporarily_vacant', 'unoccupied_abandoned']):

            result['status'] = 'no_progress_detected'
            result['escalated'] = True

            # Create explanation review
            explanation = ExplanationReview.objects.create(
                lot_award=lot_award,
                unit=report.unit,
                triggered_by_report=report,
                review_status='pending_review',
                trigger_kind='auto_rule',
            )

            result['actions'].append({
                'type': 'explanation_review',
                'message': 'No construction progress detected. Beneficiary must provide explanation.',
                'review_id': str(explanation.id),
            })

            # Send SMS
            if lot_award.application.applicant.phone_number:
                send_sms(
                    lot_award.application.applicant.phone_number,
                    f"No construction progress detected on your lot (Block {report.unit.block_number} Lot {report.unit.lot_number}). "
                    f"Please explain the delay. Reference: {lot_award.application.applicant.reference_number}",
                    'no_progress',
                    applicant=lot_award.application.applicant,
                    module='units',
                )

        # RULE 2: Extension period ended - Still no progress
        elif (monitoring_cycle.cycle_stage.startswith('extension') and
              today > monitoring_cycle.stage_end_date and
              report.construction_status == 'no_structure'):

            result['status'] = 'extension_failed'
            result['escalated'] = True

            # Move to final notice stage
            monitoring_cycle.is_active = False
            monitoring_cycle.save()

            final_cycle = OccupancyMonitoringCycle.objects.create(
                lot_award=lot_award,
                cycle_stage='final_notice_30_day',
                stage_start_date=today,
                stage_end_date=today + timedelta(days=30),
                days_allowed=30,
                is_active=True,
            )

            MonitoringTask.objects.create(
                unit=report.unit,
                lot_award=lot_award,
                task_type='final_inspection',
                scheduled_date=today,
                due_date=today + timedelta(days=30),
                days_from_award=days_since_award,
                status='pending',
                assigned_to=report.unit.site.caretaker,
            )

            result['actions'].append({
                'type': 'final_notice',
                'message': 'Extension period ended. Final 30-day notice issued.',
                'cycle_id': str(final_cycle.id),
            })

            # Send SMS
            if lot_award.application.applicant.phone_number:
                send_sms(
                    lot_award.application.applicant.phone_number,
                    f"FINAL NOTICE: You have 30 days to show construction progress on Block {report.unit.block_number} Lot {report.unit.lot_number}. "
                    f"Deadline: {final_cycle.stage_end_date}. Reference: {lot_award.application.applicant.reference_number}",
                    'final_notice',
                    applicant=lot_award.application.applicant,
                    module='units',
                )

        # RULE 3: Normal progress - Continue monitoring
        elif report.construction_status != 'no_structure' or report.occupancy_status == 'properly_occupied':
            result['status'] = 'progress_detected'
            result['actions'].append({
                'type': 'continue_monitoring',
                'message': f'Construction at {report.construction_status}. Monitoring continues.',
            })

        return result

    except Exception as e:
        import sys
        sys.stderr.write(f"\n[ERROR] Failed to evaluate monitoring report: {str(e)}\n")
        sys.stderr.flush()
        result['status'] = 'error'
        result['error'] = str(e)
        return result
