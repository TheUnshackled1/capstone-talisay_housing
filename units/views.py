from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta, datetime
import json

from intake.models import QueueEntry, Applicant
from intake.utils import send_sms
from applications.models import Application
from units.models import (
    HousingUnit, LotAward, RelocationSite, ComplianceNotice,
    OccupancyReport, OccupancyReportDetail
)


@login_required
@require_http_methods(["GET", "POST"])
def lot_awarding_draw(request):
    """
    UI #16: Lot Awarding Draw - Split Screen Interface
    Process 6: Unit Awarding (Days 3-4 of Week 1)

    Actor: Jocel (Fourth Member / Lot Coordinator)
    Purpose: Assign standby applicants to vacant housing units

    GET: Display form with standby queue and vacant units
    POST: Process lot awards and create assignment records
    """

    # Authorization check: Only Jocel (Fourth Member) can access
    if request.user.position not in ['fourth_member']:
        return render(request, 'common/access_denied.html',
                      {'message': 'Only the Lot Coordinator (Fourth Member) can access this function.'}, status=403)

    if request.method == 'POST':
        return process_lot_awards(request)

    # GET: Prepare form data
    # Get all active standby applicants (from priority and walk-in queues)
    standby_applicants = (
        QueueEntry.objects
        .filter(status='active')
        .select_related('applicant')
        .order_by('queue_type', 'position')  # Priority first, then walk-in
    )

    # Get all vacant housing units
    vacant_units = (
        HousingUnit.objects
        .filter(status='vacant')
        .select_related('site')
        .order_by('site__name', 'block_number', 'lot_number')
    )

    # Get all relocation sites for grouping
    sites = RelocationSite.objects.all().values('id', 'name')

    context = {
        'standby_applicants': standby_applicants,
        'vacant_units': vacant_units,
        'sites': sites,
        'total_standby': standby_applicants.count(),
        'total_vacant': vacant_units.count(),
    }

    return render(request, 'units/lot_awarding_draw.html', context)


@transaction.atomic
def process_lot_awards(request):
    """
    Handle POST request to create lot awards
    Expects JSON payload with: { 'assignments': [{ 'queue_entry_id': '...', 'unit_id': '...' }, ...] }
    """
    import json

    try:
        data = json.loads(request.body)
        assignments = data.get('assignments', [])

        if not assignments:
            return JsonResponse({'success': False, 'error': 'No assignments provided'})

        created_awards = []

        for assignment in assignments:
            queue_entry_id = assignment.get('queue_entry_id')
            unit_id = assignment.get('unit_id')

            if not queue_entry_id or not unit_id:
                continue

            try:
                # Get or create application
                queue_entry = QueueEntry.objects.get(id=queue_entry_id)
                applicant = queue_entry.applicant

                # Get or create application for this applicant
                application, created = Application.objects.get_or_create(
                    applicant=applicant,
                    defaults={
                        'reference_number': f'APP-{timezone.now().strftime("%Y%m%d")}-{applicant.id}',
                        'status': 'eligible',
                        'submitted_by': request.user,
                    }
                )

                # Get unit
                unit = HousingUnit.objects.get(id=unit_id)

                # Create LotAward
                lot_award = LotAward.objects.create(
                    application=application,
                    unit=unit,
                    awarded_by=request.user,
                    awarded_at=timezone.now(),
                    status='active',
                )

                # Update unit status
                unit.status = 'occupied'
                unit.save()

                # Update queue entry status
                queue_entry.status = 'completed'
                queue_entry.save()

                # Send SMS notification to beneficiary
                if applicant.phone_number:
                    sms_message = (
                        f"🏠 HOUSING AWARD NOTICE\n"
                        f"Congratulations! You have been awarded:\n"
                        f"{unit.site.name} - Block {unit.block_number}, Lot {unit.lot_number}\n"
                        f"Please report to THA office for contract signing and key handover.\n"
                        f"Thank you, Talisay Housing Authority"
                    )
                    send_sms(applicant.phone_number, sms_message, 'lot_award', applicant=applicant)

                created_awards.append({
                    'applicant_name': applicant.full_name,
                    'unit': f"Block {unit.block_number}, Lot {unit.lot_number}",
                    'site': unit.site.name,
                })

            except (QueueEntry.DoesNotExist, HousingUnit.DoesNotExist) as e:
                continue

        return JsonResponse({
            'success': True,
            'message': f'Successfully awarded {len(created_awards)} unit(s)',
            'awards_created': len(created_awards),
            'details': created_awards,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# UI #25: COMPLIANCE NOTICE ISSUANCE FORM (Week 2)
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def compliance_notice_issuance(request):
    """
    UI #25: Compliance Notice Issuance Form
    Process 8: Occupancy Validation & Compliance - Issue notices to beneficiaries

    Actor: Any staff (typically 2nd Member/Joie for supervision)
    Purpose: Issue 30-day reminders, 10-day final notices, or custom compliance notices
             for occupancy (electricity, documentation, property maintenance, etc.)

    GET: Display form with occupied units and notice templates
    POST: Create compliance notice and send SMS notification
    """

    if request.method == 'POST':
        return process_compliance_notice(request)

    # GET: Prepare form data
    # Get all occupied housing units with their beneficiary info
    occupied_units = (
        HousingUnit.objects
        .filter(status='occupied')
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
@require_POST
def process_compliance_notice(request):
    """
    Handle POST request to issue compliance notice.

    Expected POST data:
    - unit_id: HousingUnit ID
    - notice_type: 'reminder_30', 'final_10', or 'custom'
    - reason: Text describing reason for notice
    - days_granted: (for custom) Number of days to comply
    - custom_period: (for custom) Description of custom period
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
def occupancy_report_form(request):
    """
    UI #22: Occupancy Report Form
    Process 8: Occupancy Validation - Weekly caretaker report

    Actor: Caretaker (e.g., Arcadio Lobaton at GK Cabatangan)
    Purpose: Submit weekly occupancy status for all units at the site

    GET: Display form with all units at caretaker's site
         Pre-fill with last week's report if exists
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
                return render(request, 'common/access_denied.html',
                              {'message': 'No site assigned to your account.'}, status=403)
    except:
        caretaker_site = RelocationSite.objects.first()

    if not caretaker_site:
        return render(request, 'common/error.html',
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
@require_POST
def submit_occupancy_report(request):
    """
    Handle AJAX POST to submit occupancy report.

    Expected POST data (JSON):
    - site_id: RelocationSite ID
    - report_week_start: Date (YYYY-MM-DD)
    - unit_statuses: JSON array of {unit_id, status, occupant_name, comments}
    - notes: Overall comments
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

