from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction, models, IntegrityError
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta, datetime
from collections import OrderedDict
from functools import wraps
import json

from intake.models import Applicant, Barangay
from applications.models import QueueEntry, Application
from intake.utils import send_sms
from units.models import (
    HousingUnit, LotAward, RelocationSite, CaseRecord, CaseUpdate, WeeklyReport,
    ConstructionProgress,
)
from accounts.models import FIELD_DESK_POSITIONS

# Module 4 inventory: who may add housing units (block/lot rows)
_MODULE4_ADD_HOUSING_UNIT_POSITIONS = frozenset({'fourth_member', 'second_member'})
_MODULE4_CREATE_SITE_POSITIONS = frozenset({'fourth_member', 'second_member'})

_NOTICE_STATUS_VALUES = frozenset({'Under notice (30-day)', 'Final notice (10-day)'})


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

    # Group units by block (OrderedDict so template can use .items() like a dict)
    blocks = units.values_list('block_number', flat=True).distinct().order_by('block_number')
    units_by_block = OrderedDict()
    for block in blocks:
        units_by_block[block] = units.filter(block_number=block)

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
    progress_by_unit_id = {}

    if not no_relocation_sites and units.exists():
        progress_qs = (
            ConstructionProgress.objects.filter(
                lot_award__unit__in=units,
                lot_award__status='active',
            )
            .select_related('lot_award__unit')
        )
        for p in progress_qs:
            uid = getattr(p.lot_award, 'unit_id', None)
            if uid and uid not in progress_by_unit_id:
                progress_by_unit_id[uid] = p

        for u in units:
            p = progress_by_unit_id.get(u.id)
            setattr(u, '_construction_progress', p)
            if not p:
                continue
            if p.is_delayed:
                construction_delayed += 1
            if p.stage == 'not_started' or p.percent_complete <= 0:
                construction_not_started += 1
            elif p.stage == 'completed' or p.percent_complete >= 100:
                construction_completed += 1
            else:
                construction_in_progress += 1

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
    }

    return render(request, 'units/housing_units_monitoring.html', context)


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

    POST: site_id, block_number, lot_number, location_notes (optional)
    """
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
        possession_info = None
        beneficiary_info = None
        if active_lot_award and active_lot_award.awarded_at:
            awarded_at = active_lot_award.awarded_at
            now = timezone.now()
            days_possessed = max(0, (now.date() - awarded_at.date()).days)
            possession_info = {
                'awarded_at': awarded_at.isoformat(),
                'possessed_at': awarded_at.isoformat(),
                'days_possessed': days_possessed,
            }
        if active_lot_award:
            applicant = getattr(active_lot_award.application, 'applicant', None)
            if applicant:
                beneficiary_info = {
                    'full_name': applicant.full_name or '',
                    'reference_number': applicant.reference_number or '',
                    'household_members': applicant.household_member_count,
                }
        if beneficiary_info is None and (unit.occupant_name or '').strip():
            beneficiary_info = {
                'full_name': (unit.occupant_name or '').strip(),
                'reference_number': (unit.occupant_id or '').strip(),
                'household_members': None,
            }
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

        return JsonResponse({
            'success': True,
            'unit': {
                'id': str(unit.id),
                'block': unit.block_number,
                'lot': unit.lot_number,
                'status': unit.status,
                'occupant_name': unit.occupant_name or '',
                'occupant_id': unit.occupant_id or '',
                'is_escalated': unit.is_escalated,
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
                'construction_monitoring': {
                    'site_name': unit.site.name if unit.site else '',
                    'status_filter': cm_filter,
                    'count_not_started': count_not_started,
                    'count_in_progress': count_in_progress,
                    'count_completed': count_completed,
                    'count_delayed': count_delayed,
                    'rows': site_rows_payload,
                },
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
    Case Management Dashboard
    Displays all case records with search, filtering, and status tracking

    URL: /units/<position>/cases/

    Actors: All staff
    Purpose: Track complaints, disputes, and case resolutions
    """

    # Get all cases
    cases = (
        CaseRecord.objects
        .select_related('handled_by', 'created_by')
        .prefetch_related('updates')
        .order_by('-date_received')
    )

    # Count by status
    open_count = cases.filter(status='Open').count()
    referred_count = cases.filter(status='Referred').count()
    resolved_count = cases.filter(status='Resolved').count()

    # Search and filter
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', 'all')
    filter_type = request.GET.get('type', 'all')

    if search_query:
        cases = cases.filter(
            models.Q(complainant_name__icontains=search_query) |
            models.Q(case_number__icontains=search_query) |
            models.Q(description__icontains=search_query)
        )

    if filter_status != 'all':
        cases = cases.filter(status=filter_status)

    if filter_type != 'all':
        cases = cases.filter(complaint_type=filter_type)

    context = {
        'cases': cases,
        'open_count': open_count,
        'referred_count': referred_count,
        'resolved_count': resolved_count,
        'search_query': search_query,
        'filter_status': filter_status,
        'filter_type': filter_type,
    }

    return render(request, 'units/case_management.html', context)


@login_required
@verify_position
@require_http_methods(["GET"])
def get_case_details(request, position, case_id):
    """
    AJAX endpoint to fetch case details for modal display
    Returns JSON with case info, updates, and timeline

    URL: /units/<position>/case/<case_id>/
    """
    try:
        case = CaseRecord.objects.prefetch_related('updates').get(id=case_id)

        # Prepare updates list
        updates = [
            {
                'notes': update.notes,
                'updated_by': update.updated_by.get_full_name() if update.updated_by else 'Unknown',
                'updated_at': update.updated_at.isoformat(),
            }
            for update in case.updates.all()
        ]

        return JsonResponse({
            'success': True,
            'case': {
                'id': str(case.id),
                'case_number': case.case_number,
                'status': case.status,
                'date_received': case.date_received.isoformat(),
                'complainant_name': case.complainant_name,
                'complainant_id': case.complainant_id or '',
                'complaint_type': case.complaint_type,
                'description': case.description,
                'handled_by': case.handled_by.get_full_name() if case.handled_by else 'Unassigned',
                'referred_to': case.referred_to or None,
                'referral_date': case.referral_date.isoformat() if case.referral_date else None,
                'outcome': case.outcome or '',
                'resolved_date': case.resolved_date.isoformat() if case.resolved_date else None,
                'updates': updates,
            }
        })

    except CaseRecord.DoesNotExist:
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
@verify_position
@require_POST
def create_case(request, position):
    """
    AJAX endpoint to create a new case record

    URL: /units/<position>/case/create/

    POST data:
    - complainant_name: str
    - complainant_id: str (optional)
    - complaint_type: 'Boundary Dispute' | 'Structural Issue' | 'Interpersonal Conflict' | 'Other'
    - date_received: date string (YYYY-MM-DD)
    - description: str
    - handled_by_user_id: UUID (user to assign as handler)
    """
    try:
        data = json.loads(request.body)

        complainant_name = data.get('complainant_name', '').strip()
        complainant_id = data.get('complainant_id', '').strip()
        complaint_type = data.get('complaint_type', '').strip()
        date_received = data.get('date_received', '').strip()
        description = data.get('description', '').strip()
        handled_by_user_id = data.get('handled_by_user_id')

        # Validate required fields
        if not all([complainant_name, complaint_type, date_received, description]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        if complaint_type not in ['Boundary Dispute', 'Structural Issue', 'Interpersonal Conflict', 'Other']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid complaint type'
            }, status=400)

        # Get handler user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        handled_by = None
        if handled_by_user_id:
            try:
                handled_by = User.objects.get(id=handled_by_user_id)
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Handler user not found'
                }, status=404)

        # Create case
        case = CaseRecord.objects.create(
            complainant_name=complainant_name,
            complainant_id=complainant_id,
            complaint_type=complaint_type,
            date_received=date_received,
            description=description,
            handled_by=handled_by,
            created_by=request.user,
        )

        return JsonResponse({
            'success': True,
            'message': f'✓ Case {case.case_number} created successfully',
            'case': {
                'id': str(case.id),
                'case_number': case.case_number,
                'complainant_name': case.complainant_name,
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
@verify_position
@require_POST
def update_case(request, position):
    """
    AJAX endpoint to update case status, add notes, or resolve

    URL: /units/<position>/case/update/

    POST data:
    - case_id: UUID
    - action: 'add_note' | 'change_status' | 'refer' | 'resolve'
    - notes: str (for add_note)
    - new_status: 'Open' | 'Referred' | 'Resolved' (for change_status)
    - referred_to: str (for refer)
    - outcome: str (for resolve)
    """
    try:
        data = json.loads(request.body)

        case_id = data.get('case_id')
        action = data.get('action', '').strip()

        # Get case
        case = CaseRecord.objects.get(id=case_id)

        if action == 'add_note':
            notes = data.get('notes', '').strip()
            if not notes:
                return JsonResponse({
                    'success': False,
                    'error': 'Notes cannot be empty'
                }, status=400)

            # Create case update
            CaseUpdate.objects.create(
                case=case,
                notes=notes,
                updated_by=request.user,
            )

            return JsonResponse({
                'success': True,
                'message': '✓ Note added to case',
                'case_number': case.case_number,
            })

        elif action == 'change_status':
            new_status = data.get('new_status', '').strip()
            if new_status not in ['Open', 'Referred', 'Resolved']:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid status'
                }, status=400)

            case.status = new_status
            case.save()

            return JsonResponse({
                'success': True,
                'message': f'✓ Case status changed to {new_status}',
                'case_number': case.case_number,
                'new_status': new_status,
            })

        elif action == 'refer':
            referred_to = data.get('referred_to', '').strip()
            if not referred_to:
                return JsonResponse({
                    'success': False,
                    'error': 'Referral target required'
                }, status=400)

            case.referred_to = referred_to
            case.referral_date = timezone.now().date()
            case.status = 'Referred'
            case.save()

            return JsonResponse({
                'success': True,
                'message': f'✓ Case referred to {referred_to}',
                'case_number': case.case_number,
                'new_status': 'Referred',
            })

        elif action == 'resolve':
            outcome = data.get('outcome', '').strip()
            if not outcome:
                return JsonResponse({
                    'success': False,
                    'error': 'Outcome/resolution required'
                }, status=400)

            case.status = 'Resolved'
            case.outcome = outcome
            case.resolved_date = timezone.now().date()
            case.save()

            return JsonResponse({
                'success': True,
                'message': '✓ Case resolved and closed',
                'case_number': case.case_number,
                'new_status': 'Resolved',
            })

        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            }, status=400)

    except CaseRecord.DoesNotExist:
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
