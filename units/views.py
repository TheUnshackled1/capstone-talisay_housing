from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta, datetime
from collections import OrderedDict
from functools import wraps
import json

from intake.models import Applicant
from applications.models import QueueEntry, Application, ElectricityConnection
from intake.utils import send_sms
from units.models import (
    HousingUnit, LotAward, RelocationSite, ComplianceNotice,
    OccupancyReport, OccupancyReportDetail, CaseRecord, CaseUpdate, WeeklyReport
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

# =============================================================================
# UI #25: COMPLIANCE NOTICE ISSUANCE FORM (Week 2)
# =============================================================================

@login_required
@verify_position
@require_http_methods(["GET", "POST"])
def compliance_notice_issuance(request, position):
    """
    UI #25: Compliance Notice Issuance Form
    Process 8: Occupancy Validation & Compliance - Issue notices to beneficiaries

    Actor: Any staff (typically 2nd Member/Joie for supervision)
    Purpose: Issue 30-day reminders, 10-day final notices, or custom compliance notices
             for occupancy (electricity, documentation, property maintenance, etc.)

    GET: Display form with occupied units and notice templates
    POST: Create compliance notice and send SMS notification

    URL Route: /units/compliance-notice/<position>/
    """

    if request.method == 'POST':
        return process_compliance_notice(request)

    # GET: Prepare form data
    # Get all occupied housing units with their beneficiary info
    occupied_units = (
        HousingUnit.objects
        .filter(status='Occupied')
        .select_related('site')
        .prefetch_related('lot_awards__application__applicant')
        .order_by('site__name', 'block_number', 'lot_number')
    )

    # Get unit groups by site
    units_by_site = {}
    for unit in occupied_units:
        site_name = unit.site.name
        if site_name not in units_by_site:
            units_by_site[site_name] = []
        units_by_site[site_name].append(unit)

    # Notice type choices
    notice_types = [
        ('reminder_30', '30-Day Reminder Notice'),
        ('final_10', '10-Day Final Notice'),
        ('custom', 'Custom Notice Period'),
    ]

    context = {
        'occupied_units': occupied_units,
        'units_by_site': units_by_site,
        'notice_types': notice_types,
        'total_occupied': occupied_units.count(),
    }

    return render(request, 'units/compliance_notice_issuance.html', context)


@login_required
@verify_position
@require_POST
def process_compliance_notice(request, position):
    """
    Handle POST request to issue compliance notice.

    Expected POST data:
    - unit_id: HousingUnit ID
    - notice_type: 'reminder_30', 'final_10', or 'custom'
    - reason: Text describing reason for notice
    - days_granted: (for custom) Number of days to comply
    - custom_period: (for custom) Description of custom period

    URL Route: /units/compliance-notice/process/<position>/
    """
    try:
        unit_id = request.POST.get('unit_id')
        notice_type = request.POST.get('notice_type')
        reason = request.POST.get('reason')
        custom_days = request.POST.get('custom_days', '30')

        # Validate inputs
        if not all([unit_id, notice_type, reason]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        # Get unit and lot award
        unit = HousingUnit.objects.get(id=unit_id)
        lot_award = unit.lot_awards.filter(status='active').first()

        if not lot_award:
            return JsonResponse({'success': False, 'error': 'No active lot award for this unit'})

        # Determine days_granted based on notice type
        if notice_type == 'reminder_30':
            days_granted = 30
        elif notice_type == 'final_10':
            days_granted = 10
        elif notice_type == 'custom':
            try:
                days_granted = int(custom_days)
            except ValueError:
                days_granted = 30
        else:
            return JsonResponse({'success': False, 'error': 'Invalid notice type'})

        # Calculate deadline
        deadline = (timezone.now() + timedelta(days=days_granted)).date()

        # Create compliance notice
        compliance_notice = ComplianceNotice.objects.create(
            lot_award=lot_award,
            unit=unit,
            notice_type=notice_type,
            reason=reason,
            days_granted=days_granted,
            deadline=deadline,
            issued_by=request.user,
            status='active',
        )

        # Get beneficiary info for SMS
        applicant = lot_award.application.applicant
        beneficiary_name = applicant.full_name
        phone_number = applicant.phone_number

        # Send SMS notification
        if phone_number:
            notice_label = dict(ComplianceNotice._meta.get_field('notice_type').choices)[notice_type]
            sms_message = (
                f"⚠️ COMPLIANCE NOTICE\n"
                f"Notice Type: {notice_label}\n"
                f"Unit: Block {unit.block_number}, Lot {unit.lot_number}\n"
                f"Reason: {reason}\n"
                f"Deadline: {deadline.strftime('%B %d, %Y')}\n"
                f"Please contact THA office immediately.\n"
                f"Talisay Housing Authority"
            )
            send_sms(phone_number, sms_message, 'compliance_notice', applicant=applicant)

        return JsonResponse({
            'success': True,
            'message': f'{notice_label} issued to {beneficiary_name}',
            'notice_id': str(compliance_notice.id),
            'notice_type': notice_type,
            'deadline': deadline.strftime('%Y-%m-%d'),
            'days_granted': days_granted,
            'beneficiary': beneficiary_name,
        })

    except HousingUnit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unit not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# UI #22: OCCUPANCY REPORT FORM (Process 8 - Week 2 Day 3-4)
# =============================================================================

@login_required
@verify_position
def occupancy_report_form(request, position):
    """
    UI #22: Occupancy Report Form
    Process 8: Occupancy Validation - Weekly caretaker report

    Actor: Caretaker (e.g., Arcadio Lobaton at GK Cabatangan)
    Purpose: Submit weekly occupancy status for all units at the site

    GET: Display form with all units at caretaker's site
         Pre-fill with last week's report if exists

    URL Route: /units/occupancy-report/<position>/
    """

    # Get caretaker's assigned site
    # Try to get site from user profile or request
    try:
        # For caretaker: they should have site assignment
        # For staff: they might not have a specific site
        caretaker_site = getattr(request.user, 'caretaker_site', None)

        if not caretaker_site:
            # Check if user is caretaker role
            if not hasattr(request.user, 'position') or request.user.position != 'caretaker':
                # Non-caretaker can view but not submit
                sites = RelocationSite.objects.all()
                caretaker_site = sites.first() if sites.exists() else None
            else:
                return render(request, 'staff/access_denied.html',
                              {'message': 'No site assigned to your account.'}, status=403)
    except:
        caretaker_site = RelocationSite.objects.first()

    if not caretaker_site:
        return render(request, 'staff/error.html',
                      {'error': 'No sites configured in system.'}, status=404)

    # Get all units at site (regardless of status)
    units = HousingUnit.objects.filter(site=caretaker_site).order_by('block_number', 'lot_number')

    # Get this week's dates
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=4)  # Friday

    # Check if report already exists for this week
    existing_report = OccupancyReport.objects.filter(
        site=caretaker_site,
        report_week_start=week_start
    ).first()

    # Get last week's report for pre-fill
    last_week_start = week_start - timedelta(days=7)
    last_week_report = OccupancyReport.objects.filter(
        site=caretaker_site,
        report_week_start=last_week_start
    ).prefetch_related('details').first()

    # Prepare context
    context = {
        'site': caretaker_site,
        'units': units,
        'week_start': week_start,
        'week_end': week_end,
        'existing_report': existing_report,
        'last_week_report': last_week_report,
        'unit_count': units.count(),
        'can_submit': request.user.position == 'caretaker' if hasattr(request.user, 'position') else False,
    }

    return render(request, 'units/occupancy_report_form.html', context)


@login_required
@verify_position
@require_POST
def submit_occupancy_report(request, position):
    """
    Handle AJAX POST to submit occupancy report.

    Expected POST data (JSON):
    - site_id: RelocationSite ID
    - report_week_start: Date (YYYY-MM-DD)
    - unit_statuses: JSON array of {unit_id, status, occupant_name, comments}
    - notes: Overall comments

    URL Route: /units/occupancy-report/submit/<position>/
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)

        site_id = data.get('site_id')
        report_week_start_str = data.get('report_week_start')
        unit_statuses = data.get('unit_statuses', [])
        notes = data.get('notes', '')

        # Validate
        if not all([site_id, report_week_start_str, unit_statuses]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        # Parse dates
        week_start = datetime.strptime(report_week_start_str, '%Y-%m-%d').date()
        week_end = week_start + timedelta(days=4)

        # Get site
        site = RelocationSite.objects.get(id=site_id)

        # Authorization: Only caretaker assigned to this site can submit
        if hasattr(request.user, 'position') and request.user.position == 'caretaker':
            if not hasattr(request.user, 'caretaker_site') or request.user.caretaker_site.id != site_id:
                return JsonResponse({'success': False, 'error': 'Not authorized for this site'})

        # Delete existing report for this week (if any)
        OccupancyReport.objects.filter(
            site=site,
            report_week_start=week_start
        ).delete()

        # Count statuses
        occupied_count = sum(1 for u in unit_statuses if u.get('status') == 'occupied')
        vacant_count = sum(1 for u in unit_statuses if u.get('status') == 'unoccupied')
        concern_count = sum(1 for u in unit_statuses if u.get('status') == 'concern')

        # Create OccupancyReport
        report = OccupancyReport.objects.create(
            site=site,
            report_week_start=week_start,
            report_week_end=week_end,
            submitted_by=request.user,
            submitted_at=timezone.now(),
            reported_occupied=occupied_count,
            reported_vacant=vacant_count,
            reported_concerns=concern_count,
            notes=notes,
            status='submitted'
        )

        # Create OccupancyReportDetail records (bulk)
        details_to_create = []
        for u_status in unit_statuses:
            try:
                unit = HousingUnit.objects.get(id=u_status['unit_id'])
                details_to_create.append(OccupancyReportDetail(
                    report=report,
                    unit=unit,
                    status=u_status.get('status', 'unoccupied'),
                    occupant_name=u_status.get('occupant_name', ''),
                    comments=u_status.get('comments', '')
                ))
            except HousingUnit.DoesNotExist:
                pass  # Skip missing units

        if details_to_create:
            OccupancyReportDetail.objects.bulk_create(details_to_create)

        # Send SMS notification to field team supervisor (if phone available)
        # This is optional - depends on system configuration
        try:
            # For now, we'll skip SMS as we need field team phone configuration
            # In future: send_sms(field_team_phone, message, 'occupancy_report')
            pass
        except:
            pass

        return JsonResponse({
            'success': True,
            'message': f'✓ Occupancy report submitted for week of {week_start.strftime("%B %d, %Y")}',
            'report_id': str(report.id),
            'occupied': occupied_count,
            'vacant': vacant_count,
            'concerns': concern_count,
            'timestamp': timezone.now().isoformat(),
        })

    except RelocationSite.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Site not found'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error: {str(e)}'})


# =============================================================================
# UI #23: OCCUPANCY REVIEW FORM (Process 8 - Week 2 Day 5)
# =============================================================================

@login_required
@verify_position
def occupancy_review_list(request, position):
    """
    UI #23: Occupancy Review List
    Process 8: Occupancy Validation - Field team perspective

    Actor: Field Team (Paul, Roberto, Nonoy)
    Purpose: Review and confirm/flag caretaker occupancy reports

    GET: Display all pending occupancy reports awaiting field team confirmation

    URL Route: /units/occupancy-review/<position>/
    """

    # Get all reports with status='submitted' (awaiting review)
    pending_reports = (
        OccupancyReport.objects
        .filter(status='submitted')
        .select_related('site', 'submitted_by')
        .prefetch_related('details__unit')
        .order_by('-report_week_start')
    )

    # Get recent completed reviews (for reference)
    confirmed_reports = (
        OccupancyReport.objects
        .filter(status__in=['confirmed', 'discrepancy'])
        .select_related('site', 'reviewed_by')
        .order_by('-reviewed_at')[:15]
    )

    context = {
        'pending_reports': pending_reports,
        'confirmed_reports': confirmed_reports,
        'pending_count': pending_reports.count(),
        'confirmed_count': confirmed_reports.count(),
    }

    return render(request, 'units/occupancy_review_list.html', context)


@login_required
@verify_position
def occupancy_review_detail(request, position, report_id):
    """
    Display detailed review form for a specific occupancy report

    URL Route: /units/occupancy-review/<position>/<report_id>/
    """

    try:
        report = OccupancyReport.objects.get(id=report_id)
    except OccupancyReport.DoesNotExist:
        return render(request, 'staff/error.html',
                      {'error': 'Report not found'}, status=404)

    # Verify status is 'submitted' (not already reviewed)
    if report.status != 'submitted':
        return render(request, 'staff/error.html',
                      {'error': f'This report has already been {report.status}. Cannot review again.'}, status=400)

    # Get all unit details for this report
    details = report.details.select_related('unit').order_by('unit__block_number', 'unit__lot_number')

    # Format week display
    week_display = f"{report.report_week_start.strftime('%b %d')} - {report.report_week_end.strftime('%b %d, %Y')}"

    context = {
        'report': report,
        'details': details,
        'week_display': week_display,
        'detail_count': details.count(),
    }

    return render(request, 'units/occupancy_review_detail.html', context)


@login_required
@verify_position
@require_POST
def submit_occupancy_review(request, position):
    """
    Handle AJAX POST to confirm or flag occupancy report

    Expected POST data (JSON):
    - report_id: OccupancyReport ID
    - action: 'confirm' or 'flag_discrepancy'
    - confirmed_occupied: count (if confirm)
    - confirmed_vacant: count (if confirm)
    - discrepancy_notes: notes (if flag)

    URL Route: /units/occupancy-review/submit/<position>/
    """
    try:
        data = json.loads(request.body)

        report_id = data.get('report_id')
        action = data.get('action')
        confirmed_occupied = data.get('confirmed_occupied')
        confirmed_vacant = data.get('confirmed_vacant')
        discrepancy_notes = data.get('discrepancy_notes', '')

        # Validate
        if not all([report_id, action]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        # Get report
        report = OccupancyReport.objects.get(id=report_id)

        # Verify status is 'submitted'
        if report.status != 'submitted':
            return JsonResponse({
                'success': False,
                'error': f'Report already {report.status}. Cannot review.'
            })

        # Update based on action
        if action == 'confirm':
            if not all([confirmed_occupied is not None, confirmed_vacant is not None]):
                return JsonResponse({
                    'success': False,
                    'error': 'Please provide confirmed occupied and vacant counts'
                })

            report.status = 'confirmed'
            report.confirmed_occupied = confirmed_occupied
            report.confirmed_vacant = confirmed_vacant
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            message = f'✓ Report confirmed for {report.site.name}'

        elif action == 'flag_discrepancy':
            if not discrepancy_notes:
                return JsonResponse({
                    'success': False,
                    'error': 'Please provide discrepancy notes'
                })

            report.status = 'discrepancy'
            report.discrepancy_notes = discrepancy_notes
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            message = f'⚠️ Discrepancy flagged for {report.site.name}'

        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})

        report.save()

        return JsonResponse({
            'success': True,
            'message': message,
            'new_status': report.status,
            'timestamp': timezone.now().isoformat(),
        })

    except OccupancyReport.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Report not found'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


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

    URL: /units/<position>/housing-units/

    Actors: Fourth Member (Jocel), Field Team
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
    if not site:
        if all_sites.exists():
            site = all_sites.first()
        else:
            return render(request, 'staff/error.html',
                          {'error': 'No relocation sites available in the system.'})

    # Get all units for the site with related data
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

    # Prepare context
    context = {
        'site': site,
        'all_sites': all_sites,
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
    }

    return render(request, 'units/housing_units_monitoring.html', context)


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
    - notice_type: '30-day' or '10-day'
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

        if notice_type not in ['30-day', '10-day']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid notice type. Must be "30-day" or "10-day"'
            })

        # Get unit
        unit = HousingUnit.objects.get(id=unit_id)

        # Update unit status and notice
        unit.notice_type = notice_type
        unit.notice_date_issued = timezone.now()

        if notice_type == '30-day':
            unit.status = 'Under notice (30-day)'
            unit.notice_deadline = (timezone.now() + timedelta(days=30)).date()
            days = 30
        else:
            unit.status = 'Final notice (10-day)'
            unit.notice_deadline = (timezone.now() + timedelta(days=10)).date()
            days = 10

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


from django.db import models
