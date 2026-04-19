from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta, date
from .forms import LoginForm
from intake.models import Applicant, QueueEntry, CDRRMOCertification, SMSLog, Blacklist
from cases.models import Case
from applications.models import Application, SignatoryRouting, RequirementSubmission
from units.models import ComplianceNotice, HousingUnit, ElectricityConnection
import json


def _applicant_missing_intake_doc_q():
    """Any of the seven Module 1 intake checklist documents not yet marked received."""
    return (
        Q(doc_brgy_residency=False)
        | Q(doc_brgy_indigency=False)
        | Q(doc_cedula=False)
        | Q(doc_police_clearance=False)
        | Q(doc_no_property=False)
        | Q(doc_2x2_picture=False)
        | Q(doc_sketch_location=False)
    )


def _applicant_intake_docs_done_count(applicant):
    keys = (
        'doc_brgy_residency',
        'doc_brgy_indigency',
        'doc_cedula',
        'doc_police_clearance',
        'doc_no_property',
        'doc_2x2_picture',
        'doc_sketch_location',
    )
    return sum(1 for k in keys if getattr(applicant, k, False))


def _serialize_units_electricity_connection(conn):
    """units.ElectricityConnection → dict for dashboard templates (2nd / 5th member)."""
    unit = conn.lot_award.unit
    person = conn.lot_award.application.applicant
    st = conn.status
    progress_map = {
        'pending': 25,
        'docs_submitted': 45,
        'coordinating': 65,
        'approved': 90,
        'completed': 100,
    }
    step_map = {'pending': 1, 'docs_submitted': 2, 'coordinating': 3, 'approved': 3, 'completed': 4}
    return {
        'beneficiary': person.full_name,
        'beneficiary_name': person.full_name,
        'block': unit.block_number,
        'lot': unit.lot_number,
        'status': st,
        'status_display': conn.get_status_display(),
        'progress': progress_map.get(st, 15),
        'step': step_map.get(st, 1),
        'last_updated': conn.updated_at,
    }


def login_view(request):
    """Staff login page."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    # Get the requested role from URL parameter
    role = request.GET.get('role', '')
    role_display = None
    
    # Map role codes to display names
    role_map = {
        'head': 'Head / First Member',
        'oic': 'OIC-THA',
        'second_member': 'Second Member',
        'fourth_member': 'Fourth Member',
        'fifth_member': 'Fifth Member',
        'caretaker': 'Caretaker',
        'ronda': 'Ronda / Field Personnel',
    }
    role_display = role_map.get(role, None)
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # ENFORCE: Verify the user's position matches the requested role
                if role and user.position != role:
                    messages.error(
                        request, 
                        f'Access Denied: Your account is registered as {user.get_position_display()}, '
                        f'not {role_display}. Please use the correct login portal for your position.'
                    )
                    return redirect('accounts:login')  # Return to login without authenticating
                
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next', 'accounts:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please enter both username and password.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {
        'form': form,
        'role': role,
        'role_display': role_display,
    })


def logout_view(request):
    """Log out and redirect to home."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def dashboard_redirect(request):
    """
    Redirect to the appropriate position-specific dashboard.
    This ensures users always land on their designated dashboard.
    """
    user = request.user
    position = user.position
    
    # Map position to URL name
    position_urls = {
        'head': 'accounts:dashboard_head',
        'oic': 'accounts:dashboard_oic',
        'second_member': 'accounts:dashboard_second_member',
        'fourth_member': 'accounts:dashboard_fourth_member',
        'fifth_member': 'accounts:dashboard_fifth_member',
        'caretaker': 'accounts:dashboard_caretaker',
        'ronda': 'accounts:dashboard_field',
        'field': 'accounts:dashboard_field',
    }
    
    # Get URL for user's position, default to field dashboard
    url_name = position_urls.get(position, 'accounts:dashboard_field')
    return redirect(url_name)


@login_required
def dashboard_head(request):
    """
    Dashboard for Head / First Member (Arthur Maramba)
    Responsibilities: M1 (applicant oversight), M2 (final signatory), M6 (receives reports)

    MODULE 1: Applicant Intake Breakdown, Eligibility Metrics, Queue Status, Critical Alerts
    MODULE 2: Applications Awaiting Head Signature
    MODULE 6: System Overview & Reports
    """
    # Verify user has correct position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This dashboard is for the Head position only.')
        return redirect('accounts:dashboard')

    # ==================== MODULE 1: INTAKE AND ELIGIBILITY METRICS ====================
    # Total applicants
    total_applicants = Applicant.objects.count()

    # Channel breakdown
    channel_a = Applicant.objects.filter(channel='A').count()
    channel_b = Applicant.objects.filter(channel='B').count()
    channel_c = Applicant.objects.filter(channel='C').count()

    # Eligibility breakdown
    eligible_count = Applicant.objects.filter(status='eligible').count()
    disqualified_count = Applicant.objects.filter(status='disqualified').count()

    # Calculate pass rate
    if total_applicants > 0:
        eligibility_pass_rate = int((eligible_count / total_applicants) * 100)
    else:
        eligibility_pass_rate = 0

    # Queue breakdown
    priority_queue_count = QueueEntry.objects.filter(queue_type='priority', status='active').count()
    walkin_queue_count = QueueEntry.objects.filter(queue_type='walkin', status='active').count()

    # CDRRMO alerts
    overdue_threshold = timezone.now() - timedelta(days=14)
    overdue_cdrrmo = CDRRMOCertification.objects.filter(status='pending', requested_at__lt=overdue_threshold).count()

    # Blacklist summary
    blacklist_count = Blacklist.objects.count()

    # SMS failures (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    sms_failed_recent = SMSLog.objects.filter(status='failed', sent_at__gte=seven_days_ago).count()

    # ==================== MODULE 2: APPLICATIONS AWAITING HEAD SIGNATURE ====================
    # Applications awaiting head signature (status='forwarded_head')
    pending_head_signature_applications = Application.objects.filter(
        status='head_signed'  # Applications that reached head signature step
    ).exclude(
        routing_steps__step='signed_head'  # But don't have the signed_head step yet
    ).select_related('applicant').prefetch_related('routing_steps').distinct()

    # Actually, better approach: applications in 'head_signed' status awaiting final sign-off
    # Or where last routing step is 'forwarded_head'
    pending_head_applications = []
    pending_head_applications_qs = Application.objects.filter(
        status='head_signed',
    ).select_related('applicant').prefetch_related('routing_steps')

    for app in pending_head_applications_qs:
        last_routing = app.routing_steps.exclude(step='signed_head').order_by('-action_at').first()
        if last_routing:
            days_waiting = last_routing.days_since_action
            pending_head_applications.append({
                'applicant_name': app.applicant.full_name,
                'reference': app.application_number,
                'forwarded_date': last_routing.action_at,
                'days_waiting': days_waiting,
            })

    awaiting_head_signature_count = len(pending_head_applications)

    # ==================== MODULE 6: SYSTEM OVERVIEW & REPORTS ====================
    # Total housing units
    total_housing_units = HousingUnit.objects.count()

    # Occupancy rate calculation
    occupied_units = HousingUnit.objects.filter(status='Occupied').count()
    if total_housing_units > 0:
        occupancy_rate = int((occupied_units / total_housing_units) * 100)
    else:
        occupancy_rate = 0

    # Approved this month
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded',
        updated_at__gte=this_month_start
    ).count()

    # Recent reports (mock - in real system would come from Reports model)
    recent_reports = []

    context = {
        'page_title': 'Head Dashboard',
        'user_position': 'head',

        # ========== MODULE 1: INTAKE METRICS ==========
        'total_applicants': total_applicants,
        'channel_a': channel_a,
        'channel_b': channel_b,
        'channel_c': channel_c,
        'eligible_count': eligible_count,
        'disqualified_count': disqualified_count,
        'eligibility_pass_rate': eligibility_pass_rate,
        'priority_queue_count': priority_queue_count,
        'walkin_queue_count': walkin_queue_count,
        'overdue_cdrrmo': overdue_cdrrmo,
        'blacklist_count': blacklist_count,
        'sms_failed_recent': sms_failed_recent,

        # ========== MODULE 2: APPLICATIONS AWAITING SIGNATURE ==========
        'pending_approvals': pending_head_applications,
        'awaiting_signature': awaiting_head_signature_count,

        # ========== MODULE 6: SYSTEM OVERVIEW & REPORTS ==========
        'housing_units': total_housing_units,
        'occupancy_rate': occupancy_rate,
        'approved_this_month': approved_this_month,
        'recent_reports': recent_reports,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_oic(request):
    """
    Dashboard for OIC-THA (Victor Fregil)
    Responsibilities: M1 (queue oversight), M2 (OIC signatory), M4 (compliance), M5 (escalated complaints)

    PHASE 1 Implementation:
    - M2 (OIC Signatory): Pending signature tracking with >3 day delay flags
    - M4 (Compliance): Awaiting decision count
    - M5 (Escalated Cases): Escalated to OIC count
    - M6 (Analytics): Pipeline, turnaround time, compliance rates
    """
    if request.user.position != 'oic':
        messages.error(request, 'Access denied. This dashboard is for the OIC position only.')
        return redirect('accounts:dashboard')

    # ==================== MODULE 2: OIC SIGNATORY (PRIORITY) ====================
    from applications.models import Application, SignatoryRouting

    # Applications awaiting OIC signature
    pending_signature_applications = Application.objects.filter(
        status='routing'
    ).select_related('applicant').prefetch_related(
        'routing_steps'
    )

    # Enrich with routing information and days waiting
    pending_sigs_with_days = []
    for app in pending_signature_applications:
        last_routing = app.routing_steps.filter(
            step='forwarded_oic'
        ).order_by('-action_at').first()

        if last_routing:
            days_waiting = last_routing.days_since_action
            is_overdue = days_waiting > 3
            pending_sigs_with_days.append({
                'application': app,
                'reference': app.application_number,
                'applicant_name': app.applicant.full_name,
                'days_waiting': days_waiting,
                'is_overdue': is_overdue,
                'forwarded_at': last_routing.action_at,
            })

    # Sort by oldest first (longest waiting)
    pending_sigs_with_days.sort(key=lambda x: x['days_waiting'], reverse=True)

    # Count overdue signatures
    overdue_signatures = sum(1 for item in pending_sigs_with_days if item['is_overdue'])
    pending_signature_count = len(pending_sigs_with_days)

    # ==================== MODULE 1: QUEUE & SMS METRICS ====================
    # Queue counts
    priority_queue_count = QueueEntry.objects.filter(queue_type='priority', status='active').count()
    walkin_queue_count = QueueEntry.objects.filter(queue_type='walkin', status='active').count()
    total_in_queue = priority_queue_count + walkin_queue_count

    # SMS metrics
    total_sms = SMSLog.objects.count()
    sent_sms = SMSLog.objects.filter(status='sent').count()
    failed_sms = SMSLog.objects.filter(status='failed').count()
    pending_sms = SMSLog.objects.filter(status='pending').count()

    # Calculate success rate
    if total_sms > 0:
        success_rate = int((sent_sms / total_sms) * 100)
    else:
        success_rate = 0

    # Failed SMS alerts (last 10)
    failed_sms_list = SMSLog.objects.filter(status='failed').order_by('-sent_at')[:10]

    # ==================== MODULE 4: COMPLIANCE DECISIONS ====================
    from units.models import ComplianceNotice

    # Active compliance notices awaiting OIC decision
    active_compliance_notices = ComplianceNotice.objects.filter(
        status='active'
    ).select_related('lot_award__application__applicant', 'unit').order_by('deadline')

    # Enrich with decision tracking
    pending_compliance_decisions = []
    urgent_compliance_count = 0  # Approaching deadline (<= 5 days)

    for notice in active_compliance_notices:
        is_approaching = notice.is_approaching_deadline
        is_overdue = notice.is_overdue

        pending_compliance_decisions.append({
            'notice': notice,
            'applicant_name': notice.lot_award.application.applicant.full_name,
            'unit_display': str(notice.unit),
            'notice_type': notice.get_notice_type_display(),
            'days_remaining': notice.days_remaining,
            'is_approaching_deadline': is_approaching,
            'is_overdue': is_overdue,
            'deadline': notice.deadline,
            'reason': notice.reason,
        })

        if is_approaching or is_overdue:
            urgent_compliance_count += 1

    compliance_decision_count = len(pending_compliance_decisions)

    # ==================== CDRRMO & BLACKLIST ====================
    # CDRRMO metrics
    pending_cdrrmo = CDRRMOCertification.objects.filter(status='pending').count()
    overdue_threshold = timezone.now() - timedelta(days=14)
    overdue_cdrrmo = CDRRMOCertification.objects.filter(status='pending', requested_at__lt=overdue_threshold).count()

    # Blacklist count
    blacklist_count = Blacklist.objects.count()
    recent_blacklist = Blacklist.objects.all().order_by('-blacklisted_at')[:5]

    # Total applicants
    total_applicants = Applicant.objects.count()

    # ==================== MODULE 6: APPLICATION PIPELINE FUNNEL (M2/M6) ====================
    # Application pipeline stages with counts and conversion rates
    pipeline_stages = [
        ('draft', 'Form Generated'),
        ('completed', 'Applicant Signed'),
        ('routing', 'Signatory Routing'),
        ('oic_signed', 'OIC Approved'),
        ('head_signed', 'Head Approved'),
        ('standby', 'On Standby'),
        ('awarded', 'Lot Awarded'),
    ]

    # Get counts for each stage
    stage_counts = {}
    for status, label in pipeline_stages:
        stage_counts[status] = Application.objects.filter(status=status).count()

    # Calculate conversion rates
    funnel_data = []
    total_applications = sum(stage_counts.values())

    for i, (status, label) in enumerate(pipeline_stages):
        count = stage_counts[status]

        # Percentage of total applications
        pct_of_total = int((count / total_applications * 100)) if total_applications > 0 else 0

        # Conversion rate from previous stage
        conversion_rate = None
        if i > 0 and funnel_data:
            prev_count = funnel_data[i-1]['count']
            conversion_rate = int((count / prev_count * 100)) if prev_count > 0 else 0

        funnel_data.append({
            'status': status,
            'label': label,
            'count': count,
            'pct_of_total': pct_of_total,
            'conversion_rate': conversion_rate,
            'position': i,
        })

    # ==================== MODULE 6: SIGNATORY TURNAROUND TIME (M2/M6) ====================
    # Signatory routing step definitions
    routing_steps_definitions = [
        ('forwarded_oic', 'Forwarded to Victor', 'oic', None),  # First step, no previous
        ('signed_oic', 'Victor Approves', 'oic', 'forwarded_oic'),  # Previous step: forwarded_oic
        ('forwarded_head', 'Forwarded to Arthur', 'head', 'signed_oic'),  # Previous step: signed_oic
        ('signed_head', 'Arthur Completes', 'head', 'forwarded_head'),  # Previous step: forwarded_head
    ]

    # Calculate turnaround time for each routing step
    turnaround_analytics = []

    for step_code, step_label, responsible_role, prev_step_code in routing_steps_definitions:
        # Get all completed routing steps for this step
        completed_steps = SignatoryRouting.objects.filter(
            step=step_code
        ).select_related('application', 'action_by').order_by('action_at')

        # Get currently pending at this step (forwarded but not yet completed)
        if step_code == 'received':
            # First step: applications with routing status but no 'received' step yet
            pending_at_step = 0
            overdue_at_step = 0
        else:
            # Other steps: applications that have completed previous step but not this one
            apps_with_prev_step = Application.objects.filter(
                routing_steps__step=prev_step_code
            ).distinct()
            apps_with_current_step = Application.objects.filter(
                routing_steps__step=step_code
            ).distinct()
            pending_apps = apps_with_prev_step.exclude(
                id__in=apps_with_current_step.values_list('id', flat=True)
            )
            pending_at_step = pending_apps.count()

            # Count overdue at this step (pending > 3 days)
            overdue_at_step = 0
            for app in pending_apps:
                last_prev = app.routing_steps.filter(
                    step=prev_step_code
                ).order_by('-action_at').first()
                if last_prev and last_prev.is_delayed:
                    overdue_at_step += 1

        # Calculate turnaround time metrics for completed steps
        turnaround_times = []
        for routing in completed_steps:
            if prev_step_code:
                # Find previous step for this application
                prev_routing = routing.application.routing_steps.filter(
                    step=prev_step_code
                ).order_by('-action_at').first()

                if prev_routing:
                    turnaround_days = (routing.action_at - prev_routing.action_at).days
                    turnaround_times.append(turnaround_days)

        # Calculate statistics
        if turnaround_times:
            avg_turnaround = int(sum(turnaround_times) / len(turnaround_times))
            max_turnaround = max(turnaround_times)
            min_turnaround = min(turnaround_times)
            completed_count = len(turnaround_times)
        else:
            avg_turnaround = 0
            max_turnaround = 0
            min_turnaround = 0
            completed_count = 0

        turnaround_analytics.append({
            'step_code': step_code,
            'step_label': step_label,
            'responsible_role': responsible_role,
            'avg_turnaround': avg_turnaround,
            'max_turnaround': max_turnaround,
            'min_turnaround': min_turnaround,
            'completed_count': completed_count,
            'pending_count': pending_at_step,
            'overdue_count': overdue_at_step,
            'sla_target': 3,  # 3-day SLA
            'is_exceeding_sla': avg_turnaround > 3 if completed_count > 0 else False,
        })

    # ==================== MODULE 6: COMPLIANCE RATE ANALYTICS (M4/M6) ====================
    # Calculate overall compliance metrics
    complied_count = ComplianceNotice.objects.filter(status='complied').count()
    escalated_count = ComplianceNotice.objects.filter(status='escalated').count()
    active_count = ComplianceNotice.objects.filter(status='active').count()
    cancelled_count = ComplianceNotice.objects.filter(status='cancelled').count()

    # Total notices (all statuses)
    total_notices = complied_count + escalated_count + active_count + cancelled_count

    # Calculate compliance rate: complied / (complied + escalated)
    # Only count resolved cases (complied + escalated), NOT active
    resolved_count = complied_count + escalated_count
    if resolved_count > 0:
        compliance_rate = int((complied_count / resolved_count) * 100)
        escalation_rate = int((escalated_count / resolved_count) * 100)
    else:
        compliance_rate = 0
        escalation_rate = 0

    # Calculate average resolution time for complied notices
    from django.db.models import F
    from datetime import timedelta as td

    complied_notices = ComplianceNotice.objects.filter(
        status='complied',
        resolved_at__isnull=False
    ).select_related('lot_award__application__applicant')

    resolution_times = []
    for notice in complied_notices:
        if notice.resolved_at and notice.issued_at:
            resolution_days = (notice.resolved_at - notice.issued_at).days
            resolution_times.append(resolution_days)

    if resolution_times:
        avg_resolution_days = int(sum(resolution_times) / len(resolution_times))
        fastest_resolution = min(resolution_times)
        slowest_resolution = max(resolution_times)
    else:
        avg_resolution_days = 0
        fastest_resolution = 0
        slowest_resolution = 0

    # Compliance performance rating
    if compliance_rate >= 90:
        compliance_rating = '🟢 EXCELLENT'
        compliance_color = '#10b981'
    elif compliance_rate >= 75:
        compliance_rating = '🟡 GOOD'
        compliance_color = '#f59e0b'
    elif compliance_rate >= 50:
        compliance_rating = '⚠️ FAIR'
        compliance_color = '#f59e0b'
    else:
        compliance_rating = '🔴 POOR'
        compliance_color = '#ef4444'

    # ==================== SHARED DASHBOARD STATS ====================
    # Total housing units (for dashboard stat cards)
    total_housing_units = HousingUnit.objects.count()

    # Approved this month (for dashboard stat cards)
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded',
        updated_at__gte=this_month_start
    ).count()

    # ==================== MODULE 5: ESCALATED CASES (M5) ====================
    # Cases awaiting OIC decision (open, investigation, pending_decision, referred)
    escalated_cases_queryset = Case.objects.filter(
        status__in=['open', 'investigation', 'pending_decision', 'referred']
    ).order_by('-received_at').select_related('received_by', 'complainant_applicant', 'related_unit', 'subject_applicant')

    # Enrich with statistics
    escalated_cases_with_stats = []
    stale_cases_count = 0  # Cases open > 14 days
    urgent_cases_count = 0  # Cases open > 7 days
    case_type_distribution = {}  # Count by case type

    for case in escalated_cases_queryset:
        days_open = case.days_open
        is_stale = case.is_stale  # > 14 days
        is_urgent = days_open > 7  # > 7 days

        # Track type distribution
        case_type = case.get_case_type_display()
        case_type_distribution[case_type] = case_type_distribution.get(case_type, 0) + 1

        escalated_cases_with_stats.append({
            'case': case,
            'case_number': case.case_number,
            'case_type': case_type,
            'status_display': case.get_status_display(),
            'complainant': case.complainant_name,
            'subject': case.subject_name or (case.subject_applicant.full_name if case.subject_applicant else 'N/A'),
            'days_open': days_open,
            'is_stale': is_stale,
            'is_urgent': is_urgent,
            'received_at': case.received_at,
            'description_snippet': case.initial_description[:100] + '...' if len(case.initial_description) > 100 else case.initial_description,
        })

        if is_stale:
            stale_cases_count += 1
        if is_urgent:
            urgent_cases_count += 1

    total_escalated_cases = len(escalated_cases_with_stats)

    context = {
        'page_title': 'OIC Dashboard',
        'user_position': 'oic',

        # ========== MODULE 2: OIC SIGNATORY (PHASE 1) ==========
        'pending_signature_count': pending_signature_count,
        'overdue_signatures': overdue_signatures,
        'pending_sigs_with_days': pending_sigs_with_days,  # Enhanced list with days waiting

        # ========== MODULE 4: COMPLIANCE DECISIONS (PHASE 1) ==========
        'compliance_decision_count': compliance_decision_count,
        'urgent_compliance_count': urgent_compliance_count,
        'pending_compliance_decisions': pending_compliance_decisions,

        # ========== MODULE 6: APPLICATION PIPELINE FUNNEL (PHASE 1 #3) ==========
        'funnel_data': funnel_data,
        'total_applications': total_applications,

        # ========== MODULE 6: SIGNATORY TURNAROUND TIME (PHASE 1 #4) ==========
        'turnaround_analytics': turnaround_analytics,

        # ========== MODULE 6: COMPLIANCE RATE ANALYTICS (PHASE 1 #5) ==========
        'compliance_rate': compliance_rate,
        'escalation_rate': escalation_rate,
        'compliance_rating': compliance_rating,
        'compliance_color': compliance_color,
        'complied_count': complied_count,
        'escalated_count': escalated_count,
        'active_count': active_count,
        'cancelled_count': cancelled_count,
        'total_notices': total_notices,
        'resolved_count': resolved_count,
        'avg_resolution_days': avg_resolution_days,
        'fastest_resolution': fastest_resolution,
        'slowest_resolution': slowest_resolution,

        # ========== MODULE 1: SYSTEM HEALTH METRICS ==========
        'total_in_queue': total_in_queue,
        'priority_queue_count': priority_queue_count,
        'walkin_queue_count': walkin_queue_count,
        'sms_sent': sent_sms,
        'sms_failed': failed_sms,
        'sms_pending': pending_sms,
        'sms_total': total_sms,
        'success_rate': success_rate,
        'failed_sms_list': failed_sms_list,
        'pending_cdrrmo': pending_cdrrmo,
        'overdue_cdrrmo': overdue_cdrrmo,
        'blacklist_count': blacklist_count,
        'recent_blacklist': recent_blacklist,
        'total_applicants': total_applicants,

        # ========== PLACEHOLDERS FOR FUTURE MODULES ==========
        'awaiting_signature': pending_signature_count,  # M2 (updated from TODO)
        'housing_units': total_housing_units,  # Shared stat card
        'approved_this_month': approved_this_month,  # Shared stat card
        'escalated_complaints': total_escalated_cases,  # M5 (escalated cases awaiting OIC)
        'escalated_cases': escalated_cases_with_stats,  # M5 (detailed list)
        'stale_cases_count': stale_cases_count,  # M5 (cases open > 14 days)
        'urgent_cases_count': urgent_cases_count,  # M5 (cases open > 7 days)
        'case_type_distribution': case_type_distribution,  # M5 (breakdown by case type)
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_second_member(request):
    """
    Dashboard for Second Member (Lourynie Joie V. Tingson)
    Responsibilities: M2 (notices, electricity), M3 (docs), M4 (compliance), M6 (reports)
    """
    if request.user.position != 'second_member':
        messages.error(request, 'Access denied. This dashboard is for the Second Member position only.')
        return redirect('accounts:dashboard')

    # ==================== MODULE 4: COMPLIANCE NOTICES (M4) ====================
    # Active compliance notices awaiting decision or response
    pending_notices = ComplianceNotice.objects.filter(
        status='active'
    ).select_related('lot_award__application__applicant', 'unit').order_by('issued_at')

    # Enrich with details for display
    notices_to_prepare = []
    urgent_notices_count = 0

    for notice in pending_notices:
        is_approaching_deadline = notice.is_approaching_deadline  # <= 5 days
        is_overdue = notice.is_overdue

        notices_to_prepare.append({
            'type': notice.get_notice_type_display(),
            'type_display': notice.get_notice_type_display(),
            'type_code': notice.notice_type,
            'beneficiary': notice.lot_award.application.applicant.full_name if notice.lot_award else 'N/A',
            'beneficiary_name': notice.lot_award.application.applicant.full_name if notice.lot_award else 'N/A',
            'block': notice.unit.block_number if notice.unit else '—',
            'lot': notice.unit.lot_number if notice.unit else '—',
            'deadline': notice.deadline,
            'days_remaining': notice.days_remaining,
            'is_approaching': is_approaching_deadline,
            'is_overdue': is_overdue,
        })

        if is_approaching_deadline or is_overdue:
            urgent_notices_count += 1

    pending_notices_count = len(notices_to_prepare)

    # ==================== MODULE 2: ELECTRICITY CONNECTIONS (M2) — units.ElectricityConnection ====================
    electricity_connections = (
        ElectricityConnection.objects.exclude(status='completed')
        .select_related('lot_award__application__applicant', 'lot_award__unit')
        .order_by('-updated_at')[:20]
    )
    electricity_tracking = [_serialize_units_electricity_connection(c) for c in electricity_connections]
    electricity_pending_count = (
        ElectricityConnection.objects.exclude(status='completed').count()
    )

    # ==================== MODULE 3: DOCUMENT OVERSIGHT (M3) — Module 1 seven-document checklist ====================
    incomplete_module1_qs = (
        Applicant.objects.filter(_applicant_missing_intake_doc_q())
        .order_by('-updated_at')[:15]
    )
    doc_completeness_alerts = []
    for app in incomplete_module1_qs:
        done = _applicant_intake_docs_done_count(app)
        doc_completeness_alerts.append({
            'applicant_name': app.full_name,
            'reference': app.reference_number,
            'missing_docs': f'{7 - done}/7 intake documents still pending',
        })
    incomplete_docs_count = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()

    # ==================== MODULE 6: UPCOMING REPORTS (Reports for Full Disclosure Portal) ====================
    # Track reports due this month
    reports_to_generate = []
    # Standard monthly reports due: 1st (Compliance Summary), 15th (Mid-month Status), 28th (Monthly Closing)
    today = date.today()

    if today.day < 1:
        reports_to_generate.append({
            'title': 'Monthly Compliance Summary',
            'due_date': today.replace(day=1),
            'status': 'DUE TODAY',
        })
    if today.day < 15:
        reports_to_generate.append({
            'title': 'Mid-Month Status Report',
            'due_date': today.replace(day=15),
            'status': 'UPCOMING',
        })
    reports_to_generate.append({
        'title': 'Monthly Closing Report',
        'due_date': today.replace(day=28),
        'status': 'UPCOMING' if today.day < 28 else 'DUE TODAY',
    })

    # ==================== SYSTEM TOTALS ====================
    total_applicants = Applicant.objects.count()

    # Shared stat card data (for dashboard headers)
    # Applications awaiting signature (any pending signature status)
    awaiting_head_signature = Application.objects.filter(
        status='head_signed'
    ).count()

    # Total housing units
    total_housing_units = HousingUnit.objects.count()

    # Approved this month
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded',
        updated_at__gte=this_month_start
    ).count()

    intake_incomplete_module1 = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()
    pending_cdrrmo_count = CDRRMOCertification.objects.filter(status='pending').count()
    requirements_verified_month = RequirementSubmission.objects.filter(
        status='verified',
        verified_at__gte=this_month_start,
    ).count()
    vacant_units_award = HousingUnit.objects.filter(status='Vacant — available').count()

    context = {
        'page_title': 'Second Member Dashboard',
        'user_position': 'second_member',

        # ========== MODULE 4: COMPLIANCE NOTICES (M4) ==========
        'pending_notices': pending_notices_count,
        'urgent_notices': urgent_notices_count,
        'notices_to_prepare': notices_to_prepare,

        # ========== MODULE 2: ELECTRICITY CONNECTIONS (M2) ==========
        'electricity_pending': electricity_pending_count,
        'electricity_tracking': electricity_tracking,

        # ========== MODULE 3: DOCUMENT OVERSIGHT (M3) ==========
        'incomplete_docs': incomplete_docs_count,
        'doc_completeness_alerts': doc_completeness_alerts[:10],  # Limit to 10

        # ========== MODULE 6: REPORTS (M6) ==========
        'reports_to_generate': reports_to_generate,

        # ========== SYSTEM OVERVIEW ==========
        'total_applicants': total_applicants,
        'awaiting_signature': awaiting_head_signature,  # Shared stat card
        'housing_units': total_housing_units,  # Shared stat card
        'approved_this_month': approved_this_month,  # Shared stat card
        # Second-row stat cards (aligned to Joie’s intake + oversight role)
        'intake_incomplete_module1': intake_incomplete_module1,
        'pending_cdrrmo_count': pending_cdrrmo_count,
        'requirements_verified_month': requirements_verified_month,
        'vacant_units_award': vacant_units_award,
    }

    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_fourth_member(request):
    """
    Dashboard for Fourth Member (Jocel O. Cuaysing)
    Responsibilities: M1 (masterlist, eligibility, queue), M2 (requirements, lot awarding), M3 (docs), M4 (property custodian)
    """
    if request.user.position != 'fourth_member':
        messages.error(request, 'Access denied. This dashboard is for the Fourth Member position only.')
        return redirect('accounts:dashboard')

    total_applicants = Applicant.objects.count()
    awaiting_head_signature = Application.objects.filter(status='head_signed').count()
    total_housing_units = HousingUnit.objects.count()
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded',
        updated_at__gte=this_month_start,
    ).count()

    today = timezone.localdate()
    active_queue_today = QueueEntry.objects.filter(status='active', entered_at__date=today).count()
    active_queue_total = QueueEntry.objects.filter(status='active').count()
    queue_today = active_queue_today if active_queue_today else active_queue_total

    incomplete_requirements = Applicant.objects.filter(_applicant_missing_intake_doc_q()).count()
    pending_cdrrmo_count = CDRRMOCertification.objects.filter(status='pending').count()
    vacant_units = HousingUnit.objects.filter(status='Vacant — available').select_related('site').order_by(
        'site__code', 'block_number', 'lot_number'
    )[:40]
    available_lots = [
        {
            'block': u.block_number,
            'lot': u.lot_number,
            'site': u.site.code,
            'label': str(u),
        }
        for u in vacant_units
    ]
    lots_for_awarding = len(available_lots)

    priority_queue = list(
        QueueEntry.objects.filter(status='active', queue_type='priority')
        .select_related('applicant')
        .order_by('position')[:25]
    )
    # Only `priority` exists in QUEUE_TYPE_CHOICES today; keep empty until walk-in queue is modeled.
    walkin_queue = []

    pending_cdrrmo = list(
        CDRRMOCertification.objects.filter(status='pending')
        .select_related('applicant')
        .order_by('-requested_at')[:20]
    )

    requirements_checklist = []
    for app in (
        Applicant.objects.filter(_applicant_missing_intake_doc_q())
        .order_by('-created_at')[:20]
    ):
        dc = _applicant_intake_docs_done_count(app)
        requirements_checklist.append(
            {
                'full_name': app.full_name,
                'reference_number': app.reference_number,
                'docs_count': dc,
                'completion_percent': int(round((dc / 7) * 100)),
            }
        )

    standby_queue = list(
        Application.objects.filter(status='standby').select_related('applicant').order_by('updated_at')[:40]
    )

    blacklist_count = Blacklist.objects.count()
    repossessed_count = HousingUnit.objects.filter(status='Repossessed').count()
    awaiting_reaward = Application.objects.filter(status='standby').count()

    standby_count = len(standby_queue)
    available_count = len(available_lots)
    ready_to_award = min(standby_count, available_count)

    context = {
        'page_title': 'Fourth Member Dashboard',
        'user_position': 'fourth_member',
        'total_applicants': total_applicants,
        'awaiting_signature': awaiting_head_signature,
        'housing_units': total_housing_units,
        'approved_this_month': approved_this_month,
        'queue_today': queue_today,
        'incomplete_requirements': incomplete_requirements,
        'documents_filed': pending_cdrrmo_count,
        'lots_for_awarding': lots_for_awarding,
        'priority_queue': priority_queue,
        'walkin_queue': walkin_queue,
        'pending_cdrrmo': pending_cdrrmo,
        'requirements_checklist': requirements_checklist,
        'standby_queue': standby_queue,
        'available_lots': available_lots,
        'blacklist_count': blacklist_count,
        'repossessed_count': repossessed_count,
        'awaiting_reaward': awaiting_reaward,
        'ready_to_award': ready_to_award,
    }

    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_fifth_member(request):
    """
    Dashboard for Fifth Member (Laarni C. Hellera)
    Responsibilities: M2 (electricity connection tracking)
    """
    if request.user.position != 'fifth_member':
        messages.error(request, 'Access denied. This dashboard is for the Fifth Member position only.')
        return redirect('accounts:dashboard')

    # Shared stat card data
    total_applicants = Applicant.objects.count()
    awaiting_head_signature = Application.objects.filter(status='head_signed').count()
    total_housing_units = HousingUnit.objects.count()
    this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = Application.objects.filter(
        status='awarded',
        updated_at__gte=this_month_start
    ).count()

    context = {
        'page_title': 'Fifth Member Dashboard',
        'user_position': 'fifth_member',
        'total_applicants': total_applicants,  # Shared stat card
        'awaiting_signature': awaiting_head_signature,  # Shared stat card
        'housing_units': total_housing_units,  # Shared stat card
        'approved_this_month': approved_this_month,  # Shared stat card
        'pending_connections': 0,  # TODO: Electricity connections pending
        'connected_this_month': 0,  # TODO: Connections completed this month
        'awaiting_negros_power': 0,  # TODO: Applications with Negros Power
        'monthly_notices': 0,  # TODO: Notices sent this month
        'electricity_queue': [],  # TODO: Beneficiaries in electricity connection process
        'negros_power_pending': [],  # TODO: Applications pending with Negros Power
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_caretaker(request):
    """
    Dashboard for Caretaker (Arcadio Lobaton)
    Responsibilities: Site monitoring, weekly occupancy reports
    """
    if request.user.position != 'caretaker':
        messages.error(request, 'Access denied. This dashboard is for the Caretaker position only.')
        return redirect('accounts:dashboard')
    
    context = {
        'page_title': 'Caretaker Dashboard',
        'user_position': 'caretaker',
        'occupied_units': 0,  # TODO: Currently occupied units
        'vacant_units': 0,  # TODO: Vacant units
        'weekly_reports_due': 0,  # TODO: Weekly reports due
        'site_issues': 0,  # TODO: Reported site issues
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_field(request):
    """
    Dashboard for Field Personnel (Ronda - Paul Betila, Roberto Dreyfus, Nonoy)
    Responsibilities: Module 1 - Channel B Danger Zone Field Verification
    """
    if request.user.position not in ['ronda', 'field']:
        messages.error(request, 'Access denied. This dashboard is for Field Personnel only.')
        return redirect('accounts:dashboard')

    # ==================== MODULE 1: CHANNEL B FIELD VERIFICATION ====================
    # Only pending danger zone verifications that are income eligible
    # Filter:
    # 1. CDRRMOCertification status='pending' (needs field verification)
    # 2. Applicant claimed danger zone (danger_zone_type is not empty)
    # 3. Applicant is income eligible (monthly_income <= 10,000)
    # 4. Applicant status is eligible or pending_cdrrmo (already cleared eligibility check)
    pending_certifications = CDRRMOCertification.objects.filter(
        status='pending',
        applicant__danger_zone_type__isnull=False,  # Claimed danger zone
        applicant__monthly_income__lte=10000,  # Income eligible
        applicant__status__in=['eligible', 'pending_cdrrmo', 'requirements']  # Passed eligibility
    ).exclude(
        applicant__danger_zone_type=''  # Empty string means not claimed
    ).select_related('applicant', 'applicant__registered_by').order_by('-requested_at')

    pending_verifications = []
    for cert in pending_certifications:
        days_pending = (timezone.now() - cert.requested_at).days

        # Calculate document count (7 required docs)
        doc_count = sum([
            cert.applicant.doc_brgy_residency,
            cert.applicant.doc_brgy_indigency,
            cert.applicant.doc_cedula,
            cert.applicant.doc_police_clearance,
            cert.applicant.doc_no_property,
            cert.applicant.doc_2x2_picture,
            cert.applicant.doc_sketch_location,
        ])

        # Get queue position if exists
        queue_entry = cert.applicant.queue_entries.filter(status='active').first()
        queue_position = queue_entry.position if queue_entry else '—'

        pending_verifications.append({
            'index': pending_certifications.filter(requested_at__gte=cert.requested_at).count(),
            'id': cert.applicant.id,
            'transaction_id': cert.id,
            'reference_number': cert.applicant.reference_number,
            'applicant_name': cert.applicant.full_name,
            'address': cert.applicant.current_address,
            'barangay': cert.applicant.barangay,
            'phone': cert.applicant.phone_number,
            'household_members': cert.applicant.household_member_count,
            'monthly_income': cert.applicant.monthly_income,
            'danger_zone_type': cert.applicant.danger_zone_type,
            'danger_zone_location': cert.applicant.danger_zone_location,
            'channel': 'Channel B — Danger Zone',
            'eligibility': 'Eligible to Proceed',  # All showing in this view are eligible
            'queue_position': queue_position,
            'staff_handled': cert.applicant.registered_by.get_full_name() if cert.applicant.registered_by else '—',
            'staff_position': cert.applicant.registered_by.get_position_display() if cert.applicant.registered_by else '—',
            'doc_count': doc_count,
            'sms_status': '✓ Sent' if cert.applicant.registration_sms_sent else '✗ Not Sent',
            'created_at': cert.requested_at,
            'days_pending': days_pending,
        })

    total_pending = len(pending_verifications)

    # Breakdown by staff who registered them
    staff_workload = {}
    for cert in pending_verifications:
        staff_name = cert['staff_handled']
        if staff_name not in staff_workload:
            staff_workload[staff_name] = 0
        staff_workload[staff_name] += 1

    # Certified vs Not Certified tallies
    certified_count = CDRRMOCertification.objects.filter(
        status='certified'
    ).count()

    not_certified_count = CDRRMOCertification.objects.filter(
        status='not_certified'
    ).count()

    # Aging verifications (pending > 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    aging_certifications = CDRRMOCertification.objects.filter(
        status='pending',
        requested_at__lt=seven_days_ago
    ).select_related('applicant').order_by('-requested_at')

    aging_verifications = []
    for cert in aging_certifications:
        aging_verifications.append({
            'applicant': cert.applicant,
            'days_pending': (timezone.now() - cert.requested_at).days,
        })

    aging_count = len(aging_verifications)

    # Team workload (assuming 3 field team members)
    FIELD_TEAM_SIZE = 3
    avg_per_member = int(total_pending / FIELD_TEAM_SIZE) if total_pending > 0 else 0

    # Completed today (verifications completed today)
    today = timezone.now().date()
    completed_today = CDRRMOCertification.objects.filter(
        status__in=['certified', 'not_certified'],
        certified_at__date=today
    ).count()

    team_workload = {
        'pending': total_pending,
        'avg_per_member': avg_per_member,
        'completed_today': completed_today,
    }

    # Success rate (verified as danger zone / total processed)
    total_processed = certified_count + not_certified_count
    if total_processed > 0:
        verified_percentage = int((certified_count / total_processed) * 100)
    else:
        verified_percentage = 0

    context = {
        'page_title': 'Field Verification Dashboard',
        'user_position': request.user.position,

        # ========== MODULE 1: VERIFICATION METRICS ==========
        'total_pending': total_pending,
        'certified_count': certified_count,
        'not_certified_count': not_certified_count,

        # ========== TEAM WORKLOAD ==========
        'team_workload': team_workload,
        'staff_workload': staff_workload,

        # ========== AGING VERIFICATIONS ==========
        'aging_verifications': aging_verifications,
        'aging_count': aging_count,

        # ========== PENDING VERIFICATIONS LIST ==========
        'pending_verifications': pending_verifications,

        # ========== VERIFICATION SUMMARY ==========
        'verified_percentage': verified_percentage,
    }
    return render(request, 'accounts/field/dashboard.html', context)


# Legacy view for backward compatibility - now just redirects
@login_required
def dashboard_view(request):
    """Legacy dashboard view - redirects to position-specific dashboard."""
    return dashboard_redirect(request)


@login_required
def applicants_list(request):
    """
    Module 1: ISF Recording Management - Applicant Intake
    Accessible to: Second Member (Joie), Fourth Member (Jocel)
    """
    allowed_positions = ['second_member', 'fourth_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. This module is for Second and Fourth Members only.')
        return redirect('accounts:dashboard')
    
    # Mock data - matching the React mockApplicants structure
    mock_applicants = [
        {
            'id': 1,
            'fullName': 'Dela Cruz, Maria Santos',
            'referenceNumber': 'THA-2024-00123',
            'dateRegistered': '2024-01-15',
            'channel': 'A',
            'barangay': 'Poblacion',
            'monthlyIncome': 8500,
            'householdSize': 5,
            'yearsResiding': 12,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Priority',
            'queuePosition': 3,
            'applicationStage': 'Requirements Submission',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': False,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': False
            },
            'lotAssignment': None,
            'electricityStatus': None
        },
        {
            'id': 2,
            'fullName': 'Santos, Juan Pedro',
            'referenceNumber': 'THA-2024-00045',
            'dateRegistered': '2023-11-20',
            'channel': 'B',
            'barangay': 'Cabatangan',
            'monthlyIncome': 7200,
            'householdSize': 4,
            'yearsResiding': 8,
            'eligibilityStatus': 'Pending CDRRMO',
            'queueType': 'None',
            'queuePosition': None,
            'applicationStage': 'Awaiting Certification',
            'cdrrmoStatus': 'Pending',
            'dangerZoneType': 'Riverside',
            'isCdrrmoFlagged': True,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': None,
            'electricityStatus': None
        },
        {
            'id': 3,
            'fullName': 'Reyes, Ana Marie',
            'referenceNumber': 'THA-2024-00087',
            'dateRegistered': '2024-02-01',
            'channel': 'C',
            'barangay': 'Tabunoc',
            'monthlyIncome': 9200,
            'householdSize': 3,
            'yearsResiding': 5,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Walk-in',
            'queuePosition': 12,
            'applicationStage': 'Queue',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': None,
            'electricityStatus': None
        },
        {
            'id': 4,
            'fullName': 'Garcia, Roberto Luis',
            'referenceNumber': 'THA-2024-00198',
            'dateRegistered': '2024-01-05',
            'channel': 'A',
            'barangay': 'Dumlog',
            'monthlyIncome': 15000,
            'householdSize': 6,
            'yearsResiding': 15,
            'eligibilityStatus': 'Disqualified',
            'queueType': 'None',
            'queuePosition': None,
            'applicationStage': 'Eligibility Check',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': 'Monthly income exceeds ₱10,000 limit',
            'documents': {
                'barangayCertResidency': False,
                'barangayCertIndigency': False,
                'cedula': False,
                'policeClearance': False,
                'certNoProperty': False,
                'picture2x2': False,
                'sketchHouseLocation': False
            },
            'lotAssignment': None,
            'electricityStatus': None
        },
        {
            'id': 5,
            'fullName': 'Mendoza, Elena Cruz',
            'referenceNumber': 'THA-2023-00234',
            'dateRegistered': '2023-09-12',
            'channel': 'A',
            'barangay': 'Poblacion',
            'monthlyIncome': 6800,
            'householdSize': 4,
            'yearsResiding': 20,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Priority',
            'queuePosition': 1,
            'applicationStage': 'Lot Awarding',
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': {
                'block': 'A',
                'lot': '5',
                'site': 'GK Cabatangan',
                'dateAwarded': '2024-02-15'
            },
            'electricityStatus': 'Application Submitted'
        },
        {
            'id': 6,
            'fullName': 'Torres, Miguel Angel',
            'referenceNumber': 'THA-2024-00067',
            'dateRegistered': '2024-01-22',
            'channel': 'B',
            'barangay': 'Biasong',
            'monthlyIncome': 7500,
            'householdSize': 7,
            'yearsResiding': 10,
            'eligibilityStatus': 'Eligible',
            'queueType': 'Priority',
            'queuePosition': 5,
            'applicationStage': 'Signatory Routing',
            'cdrrmoStatus': 'Certified',
            'dangerZoneType': 'Flood-prone area',
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': True,
            'signatoryRoutingDelayedAt': 'OIC Signature',
            'disqualificationReason': None,
            'documents': {
                'barangayCertResidency': True,
                'barangayCertIndigency': True,
                'cedula': True,
                'policeClearance': True,
                'certNoProperty': True,
                'picture2x2': True,
                'sketchHouseLocation': True
            },
            'lotAssignment': None,
            'electricityStatus': None
        }
    ]
    
    # Barangays list
    barangays = [
        'Biasong', 'Bulawan', 'Cabatangan', 'Cadulawan', 'Camp IV', 'Cansojong',
        'Dumlog', 'Jaclupan', 'Lagtang', 'Lawaan I', 'Lawaan II', 'Lawaan III',
        'Linao', 'Maghaway', 'Manipis', 'Mohon', 'Poblacion', 'Pooc', 'San Isidro',
        'San Roque', 'Tabunoc', 'Tanke', 'Tapul', 'Tigbao', 'Talisay City',
        'Zone 1', 'Zone 2'
    ]
    
    # Calculate stats
    total_applicants = len(mock_applicants)
    priority_count = len([a for a in mock_applicants if a['queueType'] == 'Priority'])
    walkin_count = len([a for a in mock_applicants if a['queueType'] == 'Walk-in'])
    pending_cdrrmo = len([a for a in mock_applicants if a.get('cdrrmoStatus') == 'Pending'])
    
    context = {
        'page_title': 'ISF Recording Management',
        'user_position': request.user.position,
        'applicants': mock_applicants,
        'applicants_json': json.dumps(mock_applicants),
        'barangays': barangays,
        'stats': {
            'total': total_applicants,
            'priority': priority_count,
            'walkin': walkin_count,
            'pending_cdrrmo': pending_cdrrmo
        }
    }
    
    return render(request, 'accounts/applicants.html', context)


# ==================== HEAD-SPECIFIC VIEWS (ARTHUR MARAMBA) ====================

@login_required
def head_applicants_overview(request):
    """
    HEAD-specific: Overview of applicant intake with summary stats AND full applicants table.
    URL: /head/applicants/
    """
    # Verify position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This view is for the Head position only.')
        return redirect('accounts:dashboard')

    # Total applicants
    total_applicants = Applicant.objects.count()

    # Channel breakdown
    channel_a = Applicant.objects.filter(channel='A').count()
    channel_b = Applicant.objects.filter(channel='B').count()
    channel_c = Applicant.objects.filter(channel='C').count()

    # Eligibility breakdown
    eligible_count = Applicant.objects.filter(status='eligible').count()
    disqualified_count = Applicant.objects.filter(status='disqualified').count()
    pending_count = Applicant.objects.filter(status='under_review').count()

    # Calculate pass rate
    if total_applicants > 0:
        eligibility_pass_rate = int((eligible_count / total_applicants) * 100)
    else:
        eligibility_pass_rate = 0

    # Queue breakdown
    priority_queue_count = QueueEntry.objects.filter(queue_type='priority', status='active').count()
    walkin_queue_count = QueueEntry.objects.filter(queue_type='walkin', status='active').count()

    # Critical alerts
    overdue_threshold = timezone.now() - timedelta(days=14)
    overdue_cdrrmo_qs = CDRRMOCertification.objects.filter(
        status='pending',
        requested_at__lt=overdue_threshold
    ).select_related('applicant').order_by('requested_at')
    overdue_cdrrmo_count = overdue_cdrrmo_qs.count()

    # Build overdue CDRRMO details list
    overdue_cdrrmo_details = []
    for cert in overdue_cdrrmo_qs[:10]:  # Limit to top 10
        days_overdue = (timezone.now() - cert.requested_at).days
        overdue_cdrrmo_details.append({
            'applicant_name': cert.applicant.full_name,
            'days_overdue': days_overdue,
            'requested_at': cert.requested_at
        })

    # Blacklist count
    blacklist_count = Blacklist.objects.count()

    # SMS failures (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    sms_failed_recent = SMSLog.objects.filter(status='failed', sent_at__gte=seven_days_ago).count()

    # Get full ISF submissions list (like 2nd member intake view) - showing transaction history
    from intake.models import ISFRecord

    isf_records = ISFRecord.objects.select_related(
        'submitted_by_staff',
        'eligibility_checked_by'
    ).order_by('-created_at')

    # Pre-fetch all converted applicants for reference matching
    all_applicants = {app.reference_number: app for app in Applicant.objects.select_related(
        'registered_by',
        'eligibility_checked_by'
    )}

    applicants_data = []
    for record in isf_records:
        # Try to find the corresponding applicant
        applicant = all_applicants.get(record.reference_number)
        reference_number = applicant.reference_number if applicant else record.reference_number
        full_name = applicant.full_name if applicant else record.full_name

        # Get queue info from applicant
        queue_type = '—'
        if applicant:
            queue_entry = applicant.queue_entries.filter(status='active').first()
            queue_type = queue_entry.get_queue_type_display() if queue_entry else '—'

        # Get documentation progress
        docs_progress = '0/7'
        if applicant:
            verified_requirements = applicant.requirement_submissions.filter(status='verified').count()
            total_requirements = applicant.requirement_submissions.count()
            docs_progress = f"{verified_requirements}/{total_requirements}" if total_requirements > 0 else "0/7"
        else:
            # For ISF records, count completed doc fields
            doc_count = sum([
                record.doc_brgy_residency,
                record.doc_brgy_indigency,
                record.doc_cedula,
                record.doc_police_clearance,
                record.doc_no_property,
                record.doc_2x2_picture,
                record.doc_sketch_location
            ])
            docs_progress = f"{doc_count}/7"

        # Get staff who handled it - prioritize ISFRecord's eligibility_checked_by, then Applicant's
        if record.eligibility_checked_by:
            staff_user = record.eligibility_checked_by
        elif applicant:
            staff_user = applicant.eligibility_checked_by or applicant.registered_by
        else:
            staff_user = None

        staff_name = staff_user.get_full_name() if staff_user else '—'
        staff_position = staff_user.position if staff_user else '—'
        staff_initials = f"{staff_user.first_name[0]}{staff_user.last_name[0]}".upper() if staff_user else '—'

        # SMS status
        sms_sent = record.registration_sms_sent or record.eligibility_sms_sent

        # Channel from applicant if exists, otherwise default to Landowner
        channel_display = applicant.get_channel_display() if applicant and applicant.channel else 'Channel A — Landowner'

        applicants_data.append({
            'id': str(record.id),
            'transaction_id': str(record.id),
            'reference_number': reference_number,
            'full_name': full_name,
            'channel': channel_display,
            'eligibility': applicant.get_status_display() if applicant else record.get_status_display(),
            'queue_type': queue_type,
            'created_at': record.created_at,
            'docs_progress': docs_progress,
            'barangay': applicant.barangay.name if applicant and applicant.barangay else record.barangay or '—',
            'staff_name': staff_name,
            'staff_position': staff_position,
            'staff_initials': staff_initials,
            'sms_sent': sms_sent
        })

    context = {
        'page_title': 'Applicant Intake Overview',
        'user_position': request.user.position,
        'total_applicants': total_applicants,
        'channel_breakdown': {
            'a': channel_a,
            'b': channel_b,
            'c': channel_c
        },
        'eligibility_breakdown': {
            'eligible': eligible_count,
            'disqualified': disqualified_count,
            'pending': pending_count
        },
        'eligibility_pass_rate': eligibility_pass_rate,
        'queue_breakdown': {
            'priority': priority_queue_count,
            'walkin': walkin_queue_count
        },
        'critical_alerts': {
            'overdue_cdrrmo': overdue_cdrrmo_count,
            'blacklist': blacklist_count,
            'sms_failed': sms_failed_recent
        },
        'overdue_cdrrmo_details': overdue_cdrrmo_details,
        'applicants': applicants_data
    }

    return render(request, 'accounts/head/applicants_overview.html', context)


@login_required
def head_pending_signature(request):
    """
    HEAD-specific: Applications awaiting HEAD's final signature.
    URL: /head/applications/pending/
    """
    # Verify position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This view is for the Head position only.')
        return redirect('accounts:dashboard')

    # Get applications awaiting head signature
    # Status should be 'head_signed' (awaiting final approval)
    pending_applications = Application.objects.filter(
        status='head_signed'
    ).select_related('applicant', 'form_generated_by').prefetch_related('routing_steps').order_by('created_at')

    # Build detailed list with days pending
    pending_apps_list = []
    for app in pending_applications:
        # Get the last routing step to determine when forwarded to head
        last_routing = app.routing_steps.filter(
            step__in=['forwarded_head', 'signed_oic']
        ).order_by('-action_at').first()

        if last_routing:
            days_pending = (timezone.now() - last_routing.action_at).days
        else:
            days_pending = (timezone.now() - app.created_at).days

        pending_apps_list.append({
            'application_number': app.application_number,
            'applicant_name': app.applicant.full_name,
            'status': app.get_status_display(),
            'received_date': app.created_at,
            'days_pending': days_pending,
            'received_by': app.form_generated_by.get_full_name() if app.form_generated_by else 'N/A',
            'application_id': str(app.id)
        })

    # Sort by days_pending descending
    pending_apps_list.sort(key=lambda x: x['days_pending'], reverse=True)

    # Count statistics
    total_pending = len(pending_apps_list)
    urgent_count = len([app for app in pending_apps_list if app['days_pending'] >= 7])

    context = {
        'page_title': 'Applications Pending Head Signature',
        'user_position': request.user.position,
        'pending_applications': pending_apps_list,
        'total_pending': total_pending,
        'urgent_count': urgent_count
    }

    return render(request, 'accounts/head/pending_signature.html', context)


@login_required
def head_analytics_dashboard(request):
    """
    HEAD-specific: System-wide performance metrics and analytics.
    URL: /head/analytics/
    """
    # Verify position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This view is for the Head position only.')
        return redirect('accounts:dashboard')

    from django.db.models import Count, Q

    # Aggregate counts
    total_applications = Application.objects.count()
    total_awarded = Application.objects.filter(status='awarded').count()
    total_rejected = Applicant.objects.filter(status='disqualified').count()

    # Calculate approval and rejection rates
    if total_applications > 0:
        approval_rate = int((total_awarded / total_applications) * 100) if total_awarded else 0
        rejection_rate = int((total_rejected / total_applications) * 100) if total_rejected else 0
    else:
        approval_rate = 0
        rejection_rate = 0

    # Average processing days
    awarded_apps = Application.objects.filter(status='awarded').exclude(fully_approved_at__isnull=True)
    if awarded_apps.exists():
        total_days = 0
        count = 0
        for app in awarded_apps:
            if app.created_at and app.fully_approved_at:
                days = (app.fully_approved_at - app.created_at).days
                total_days += days
                count += 1
        average_processing_days = int(total_days / count) if count > 0 else 0
    else:
        average_processing_days = 0

    # Monthly trends (last 6 months)
    monthly_trends = []
    now = timezone.now()
    for i in range(5, -1, -1):  # Last 6 months
        month_date = (now - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (month_date + timedelta(days=32)).replace(day=1)

        received_count = Application.objects.filter(
            created_at__gte=month_date,
            created_at__lt=next_month
        ).count()

        approved_count = Application.objects.filter(
            status='awarded',
            created_at__gte=month_date,
            created_at__lt=next_month
        ).count()

        rejected_count = Applicant.objects.filter(
            status='disqualified',
            created_at__gte=month_date,
            created_at__lt=next_month
        ).count()

        monthly_trends.append({
            'month': month_date.strftime('%b %Y'),
            'received': received_count,
            'approved': approved_count,
            'rejected': rejected_count
        })

    # Processing pipeline breakdown
    in_intake = Applicant.objects.filter(status='under_review').count()
    pending_eligibility = Applicant.objects.filter(status='pending_eligibility').count()
    in_approval = Application.objects.filter(status__in=['routing', 'oic_signed', 'head_signed']).count()
    awarded = Application.objects.filter(status='awarded').count()
    rejected = Applicant.objects.filter(status='disqualified').count()

    pipeline_breakdown = {
        'intake': in_intake,
        'eligibility': pending_eligibility,
        'approval': in_approval,
        'awarded': awarded,
        'rejected': rejected
    }

    # Services completion rate
    notarial_completed = Application.objects.filter(notarial_completed=True).count()
    engineering_completed = Application.objects.filter(engineering_completed=True).count()
    total_services_needed = total_applications * 2  # Each applicant needs both services

    if total_services_needed > 0:
        completed_services = notarial_completed + engineering_completed
        services_completion_rate = int((completed_services / total_services_needed) * 100)
    else:
        services_completion_rate = 0

    context = {
        'page_title': 'System Analytics Dashboard',
        'user_position': request.user.position,
        'total_applications': total_applications,
        'total_awarded': total_awarded,
        'total_rejected': total_rejected,
        'approval_rate': approval_rate,
        'rejection_rate': rejection_rate,
        'average_processing_days': average_processing_days,
        'monthly_trends': monthly_trends,
        'pipeline_breakdown': pipeline_breakdown,
        'services_completion_rate': services_completion_rate
    }

    return render(request, 'accounts/head/analytics_dashboard.html', context)


@login_required
def head_monthly_reports(request):
    """
    HEAD-specific: Monthly compliance and performance reports.
    URL: /head/reports/?month=YYYY-MM
    """
    # Verify position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This view is for the Head position only.')
        return redirect('accounts:dashboard')

    # Parse month from query params (default to current month)
    month_param = request.GET.get('month', timezone.now().strftime('%Y-%m'))
    try:
        report_month = timezone.now().strptime(month_param, '%Y-%m')
        month_display = report_month.strftime('%B %Y')
    except (ValueError, AttributeError):
        report_month = timezone.now().replace(day=1)
        month_display = report_month.strftime('%B %Y')
        month_param = report_month.strftime('%Y-%m')

    # Define month boundaries
    month_start = report_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    # Applications for month
    applications_received = Application.objects.filter(
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    applications_approved = Application.objects.filter(
        status='awarded',
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    applications_rejected = Applicant.objects.filter(
        status='disqualified',
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    applications_pending = Application.objects.exclude(status='awarded').filter(
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    # Housing units for month
    total_units = HousingUnit.objects.count()
    occupied_units = HousingUnit.objects.filter(occupancy_status='occupied').count()
    vacant_units = HousingUnit.objects.filter(occupancy_status='vacant').count()
    under_notice_units = HousingUnit.objects.filter(occupancy_status__in=['30_day_notice', 'final_notice']).count()

    # Cases for month
    cases_open = Case.objects.filter(
        status='open',
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    cases_investigation = Case.objects.filter(
        status='investigation',
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    cases_referred = Case.objects.filter(
        status='referred',
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    cases_resolved = Case.objects.filter(
        status='resolved',
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    # Queue status
    priority_queue = QueueEntry.objects.filter(queue_type='priority', status='active').count()
    walkin_queue = QueueEntry.objects.filter(queue_type='walkin', status='active').count()

    # Compliance notices issued
    compliance_notices = ComplianceNotice.objects.filter(
        issued_at__gte=month_start,
        issued_at__lt=next_month
    ).count()

    # Electricity connections
    electricity_requested = ElectricityConnection.objects.filter(
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    electricity_approved = ElectricityConnection.objects.filter(
        status='approved',
        created_at__gte=month_start,
        created_at__lt=next_month
    ).count()

    # Get available months (last 12 months)
    available_months = []
    now = timezone.now()
    for i in range(11, -1, -1):
        month_date = (now - timedelta(days=30*i)).replace(day=1)
        available_months.append({
            'value': month_date.strftime('%Y-%m'),
            'label': month_date.strftime('%B %Y')
        })

    context = {
        'page_title': 'Monthly Reports',
        'user_position': request.user.position,
        'month_display': month_display,
        'month_param': month_param,
        'applications': {
            'received': applications_received,
            'approved': applications_approved,
            'rejected': applications_rejected,
            'pending': applications_pending
        },
        'housing_units': {
            'total': total_units,
            'occupied': occupied_units,
            'vacant': vacant_units,
            'under_notice': under_notice_units
        },
        'cases': {
            'open': cases_open,
            'investigation': cases_investigation,
            'referred': cases_referred,
            'resolved': cases_resolved
        },
        'queue': {
            'priority': priority_queue,
            'walkin': walkin_queue
        },
        'compliance_notices': compliance_notices,
        'electricity': {
            'requested': electricity_requested,
            'approved': electricity_approved
        },
        'available_months': available_months
    }

    return render(request, 'accounts/head/monthly_reports.html', context)


# ==================== OIC-SPECIFIC VIEWS ====================

@login_required
def oic_applicants_overview(request):
    """
    OIC-specific: Overview of applicant intake with summary stats AND full applicants table.
    URL: /oic/applicants/
    OIC has read-only access to all applicants for oversight purposes.
    """
    # Verify position
    if request.user.position != 'oic':
        messages.error(request, 'Access denied. This view is for the OIC position only.')
        return redirect('accounts:dashboard')

    # Total applicants
    total_applicants = Applicant.objects.count()

    # Channel breakdown
    channel_a = Applicant.objects.filter(channel='A').count()
    channel_b = Applicant.objects.filter(channel='B').count()
    channel_c = Applicant.objects.filter(channel='C').count()

    # Eligibility breakdown
    eligible_count = Applicant.objects.filter(status='eligible').count()
    disqualified_count = Applicant.objects.filter(status='disqualified').count()
    pending_count = Applicant.objects.filter(status='under_review').count()

    # Calculate pass rate
    if total_applicants > 0:
        eligibility_pass_rate = int((eligible_count / total_applicants) * 100)
    else:
        eligibility_pass_rate = 0

    # Queue breakdown
    priority_queue_count = QueueEntry.objects.filter(queue_type='priority', status='active').count()
    walkin_queue_count = QueueEntry.objects.filter(queue_type='walkin', status='active').count()

    # Critical alerts
    overdue_threshold = timezone.now() - timedelta(days=14)
    overdue_cdrrmo_qs = CDRRMOCertification.objects.filter(
        status='pending',
        requested_at__lt=overdue_threshold
    ).select_related('applicant').order_by('requested_at')
    overdue_cdrrmo_count = overdue_cdrrmo_qs.count()

    # Build overdue CDRRMO details list
    overdue_cdrrmo_details = []
    for cert in overdue_cdrrmo_qs[:10]:  # Limit to top 10
        days_overdue = (timezone.now() - cert.requested_at).days
        overdue_cdrrmo_details.append({
            'applicant_name': cert.applicant.full_name,
            'days_overdue': days_overdue,
            'requested_at': cert.requested_at
        })

    # Blacklist count
    blacklist_count = Blacklist.objects.count()

    # SMS failures (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    sms_failed_recent = SMSLog.objects.filter(status='failed', sent_at__gte=seven_days_ago).count()

    # Get full ISF submissions list
    from intake.models import ISFRecord

    isf_records = ISFRecord.objects.select_related(
        'submitted_by_staff',
        'eligibility_checked_by'
    ).order_by('-created_at')

    # Pre-fetch all converted applicants for reference matching
    all_applicants = {app.reference_number: app for app in Applicant.objects.select_related(
        'registered_by',
        'eligibility_checked_by'
    )}

    applicants_data = []
    for record in isf_records:
        # Try to find the corresponding applicant
        applicant = all_applicants.get(record.reference_number)
        reference_number = applicant.reference_number if applicant else record.reference_number
        full_name = applicant.full_name if applicant else record.full_name

        # Get queue info from applicant
        queue_type = '—'
        if applicant:
            queue_entry = applicant.queue_entries.filter(status='active').first()
            queue_type = queue_entry.get_queue_type_display() if queue_entry else '—'

        # Get documentation progress
        docs_progress = '0/7'
        if applicant:
            verified_requirements = applicant.requirement_submissions.filter(status='verified').count()
            total_requirements = applicant.requirement_submissions.count()
            docs_progress = f"{verified_requirements}/{total_requirements}" if total_requirements > 0 else "0/7"
        else:
            # For ISF records, count completed doc fields
            doc_count = sum([
                record.doc_brgy_residency,
                record.doc_brgy_indigency,
                record.doc_cedula,
                record.doc_police_clearance,
                record.doc_no_property,
                record.doc_2x2_picture,
                record.doc_sketch_location
            ])
            docs_progress = f"{doc_count}/7"

        # Get staff who handled it
        if record.eligibility_checked_by:
            staff_user = record.eligibility_checked_by
        elif applicant:
            staff_user = applicant.eligibility_checked_by or applicant.registered_by
        else:
            staff_user = None

        staff_name = staff_user.get_full_name() if staff_user else '—'
        staff_position = staff_user.position if staff_user else '—'
        staff_initials = f"{staff_user.first_name[0]}{staff_user.last_name[0]}".upper() if staff_user else '—'

        # SMS status
        sms_sent = record.registration_sms_sent or record.eligibility_sms_sent

        # Channel from applicant if exists, otherwise default to Landowner
        channel_display = applicant.get_channel_display() if applicant and applicant.channel else 'Channel A — Landowner'

        applicants_data.append({
            'id': str(record.id),
            'transaction_id': str(record.id),
            'reference_number': reference_number,
            'full_name': full_name,
            'channel': channel_display,
            'eligibility': applicant.get_status_display() if applicant else record.get_status_display(),
            'queue_type': queue_type,
            'created_at': record.created_at,
            'docs_progress': docs_progress,
            'barangay': applicant.barangay.name if applicant and applicant.barangay else record.barangay or '—',
            'staff_name': staff_name,
            'staff_position': staff_position,
            'staff_initials': staff_initials,
            'sms_sent': sms_sent
        })

    context = {
        'page_title': 'Applicant Intake Overview',
        'user_position': request.user.position,
        'total_applicants': total_applicants,
        'channel_breakdown': {
            'a': channel_a,
            'b': channel_b,
            'c': channel_c
        },
        'eligibility_breakdown': {
            'eligible': eligible_count,
            'disqualified': disqualified_count,
            'pending': pending_count
        },
        'eligibility_pass_rate': eligibility_pass_rate,
        'queue_breakdown': {
            'priority': priority_queue_count,
            'walkin': walkin_queue_count
        },
        'critical_alerts': {
            'overdue_cdrrmo': overdue_cdrrmo_count,
            'blacklist': blacklist_count,
            'sms_failed': sms_failed_recent
        },
        'overdue_cdrrmo_details': overdue_cdrrmo_details,
        'applicants': applicants_data
    }

    return render(request, 'accounts/oic/applicants_overview.html', context)


@login_required
def oic_pending_signature(request):
    """
    OIC-specific: Applications awaiting OIC's signature.
    URL: /oic/applications/pending/
    """
    # Verify position
    if request.user.position != 'oic':
        messages.error(request, 'Access denied. This view is for the OIC position only.')
        return redirect('accounts:dashboard')

    # Get applications awaiting OIC signature
    # Status should be 'routing' (awaiting OIC step) or 'oic_signed' (awaiting final step from head)
    pending_applications = Application.objects.filter(
        status='routing'
    ).select_related('applicant', 'form_generated_by').prefetch_related('routing_steps').order_by('created_at')

    # Build detailed list with days pending
    pending_apps_list = []
    for app in pending_applications:
        # Get the last routing step to determine when forwarded to OIC
        last_routing = app.routing_steps.filter(
            step='forwarded_oic'
        ).order_by('-action_at').first()

        if last_routing:
            days_pending = (timezone.now() - last_routing.action_at).days
        else:
            days_pending = (timezone.now() - app.created_at).days

        pending_apps_list.append({
            'application_number': app.application_number,
            'applicant_name': app.applicant.full_name,
            'status': app.get_status_display(),
            'received_date': app.created_at,
            'days_pending': days_pending,
            'received_by': app.form_generated_by.get_full_name() if app.form_generated_by else 'N/A',
            'application_id': str(app.id)
        })

    # Sort by days_pending descending
    pending_apps_list.sort(key=lambda x: x['days_pending'], reverse=True)

    # Count statistics
    total_pending = len(pending_apps_list)
    urgent_count = len([app for app in pending_apps_list if app['days_pending'] >= 7])

    context = {
        'page_title': 'Applications Pending OIC Signature',
        'user_position': request.user.position,
        'pending_applications': pending_apps_list,
        'total_pending': total_pending,
        'urgent_count': urgent_count
    }

    return render(request, 'accounts/oic/pending_signature.html', context)



