from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .forms import LoginForm
from intake.models import Applicant, QueueEntry, CDRRMOCertification, SMSLog, Blacklist
from cases.models import Case
from applications.models import Application, SignatoryRouting, RequirementSubmission
from units.models import ComplianceNotice, HousingUnit, ElectricityConnection
import json


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
        'third_member': 'Third Member',
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
        'third_member': 'accounts:dashboard_third_member',
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
    occupied_units = HousingUnit.objects.filter(occupancy_status='occupied').count()
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
        ('received', 'Received by Jay', 'third_member', None),  # First step, no previous
        ('forwarded_oic', 'Forwarded to Victor', 'oic', 'received'),  # Previous step: received
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
            'type_code': notice.notice_type,
            'beneficiary': notice.lot_award.application.applicant.full_name if notice.lot_award else 'N/A',
            'block': notice.unit.block if notice.unit else 'N/A',
            'lot': notice.unit.lot if notice.unit else 'N/A',
            'deadline': notice.deadline,
            'days_remaining': notice.days_remaining,
            'is_approaching': is_approaching_deadline,
            'is_overdue': is_overdue,
        })

        if is_approaching_deadline or is_overdue:
            urgent_notices_count += 1

    pending_notices_count = len(notices_to_prepare)

    # ==================== MODULE 2: ELECTRICITY CONNECTIONS (M2) ====================
    # Electricity connection tracking
    electricity_connections = ElectricityConnection.objects.filter(
        status__in=['pending', 'initiated', 'in_progress', 'approved', 'completed']
    ).select_related('lot_award__application__applicant', 'lot_award__unit').order_by('-updated_at')

    electricity_tracking = []
    for conn in electricity_connections:
        # Calculate progress: pending=25%, in_progress=75%, completed=100%
        progress_map = {
            'pending': 25,
            'in_progress': 75,
            'completed': 100,
        }
        progress = progress_map.get(conn.status, 0)

        electricity_tracking.append({
            'beneficiary': conn.lot_award.application.applicant.full_name,
            'block': conn.lot_award.unit.block,
            'lot': conn.lot_award.unit.lot,
            'status': conn.status,
            'status_display': conn.get_status_display(),
            'progress': progress,
            'last_updated': conn.updated_at,
        })

    electricity_pending_count = len(electricity_tracking)

    # ==================== MODULE 3: DOCUMENT OVERSIGHT (M3) ====================
    # Track incomplete requirement submissions
    incomplete_requirements = RequirementSubmission.objects.filter(
        status='incomplete'
    ).select_related('applicant').order_by('submitted_at')

    doc_completeness_alerts = []
    for req in incomplete_requirements:
        missing_docs = []
        # Check which requirements are missing
        applicant_reqs = RequirementSubmission.objects.filter(
            applicant=req.applicant
        )
        doc_completeness_alerts.append({
            'applicant_name': req.applicant.full_name,
            'reference': req.applicant.id,  # Use applicant ID as reference
            'missing_docs': f"{applicant_reqs.count()} requirements pending",
        })

    incomplete_docs_count = len(doc_completeness_alerts[:10])  # Limit to 10

    # ==================== MODULE 6: UPCOMING REPORTS (Reports for Full Disclosure Portal) ====================
    # Track reports due this month
    reports_to_generate = []
    # Standard monthly reports due: 1st (Compliance Summary), 15th (Mid-month Status), 28th (Monthly Closing)
    from datetime import date
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
    }

    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_third_member(request):
    """
    Dashboard for Third Member (Roland Jay S. Olvido)
    Responsibilities: M1 (census, field verification), M2 (signatory routing), M4 (site inspection), M5 (violation investigation)
    """
    if request.user.position != 'third_member':
        messages.error(request, 'Access denied. This dashboard is for the Third Member position only.')
        return redirect('accounts:dashboard')
    
    context = {
        'page_title': 'Third Member Dashboard',
        'user_position': 'third_member',
        'census_records': 0,  # TODO: Total census records
        'pending_verification': 0,  # TODO: Applicants awaiting field verification
        'site_inspections': 0,  # TODO: Inspections scheduled/due
        'open_investigations': 0,  # TODO: Active violation investigations
        'routing_queue': [],  # TODO: Documents to route OIC→Head
        'verification_queue': [],  # TODO: Applicants needing field verification
        'inspection_schedule': [],  # TODO: Site inspections due
        'active_investigations': [],  # TODO: Violation cases under investigation
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
    
    context = {
        'page_title': 'Fourth Member Dashboard',
        'user_position': 'fourth_member',
        'queue_today': 0,  # TODO: Applicants in queue today
        'incomplete_requirements': 0,  # TODO: Applicants with incomplete requirements
        'documents_filed': 0,  # TODO: Documents filed this month
        'lots_for_awarding': 0,  # TODO: Vacant units available for awarding
        'priority_queue': [],  # TODO: Priority queue applicants
        'walkin_queue': [],  # TODO: Walk-in queue applicants
        'pending_cdrrmo': [],  # TODO: Applicants pending CDRRMO certification
        'requirements_checklist': [],  # TODO: Applicants with partial requirements
        'standby_queue': [],  # TODO: Fully approved applicants on standby
        'available_lots': [],  # TODO: Vacant lots ready for awarding
        'blacklist_count': 0,  # TODO: Total blacklisted beneficiaries
        'repossessed_count': 0,  # TODO: Repossessed units count
        'awaiting_reaward': 0,  # TODO: Units awaiting re-award after repossession
    }
    
    # Calculate ready_to_award (min of available lots and standby queue)
    standby_count = len(context['standby_queue']) if context['standby_queue'] else 0
    available_count = len(context['available_lots']) if context['available_lots'] else 0
    context['ready_to_award'] = min(standby_count, available_count)
    
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
    
    context = {
        'page_title': 'Fifth Member Dashboard',
        'user_position': 'fifth_member',
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
@login_required
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
    # Pending danger zone verifications
    pending_certifications = CDRRMOCertification.objects.filter(
        status='pending'
    ).select_related('applicant').order_by('-requested_at')

    pending_verifications = []
    for cert in pending_certifications:
        days_pending = (timezone.now() - cert.requested_at).days
        pending_verifications.append({
            'applicant': cert.applicant,
            'applicant_name': cert.applicant.full_name,
            'address': cert.applicant.address,
            'barangay': cert.applicant.barangay,
            'phone': cert.applicant.phone_number,
            'household_members': cert.applicant.household_members,
            'monthly_income': cert.applicant.monthly_income,
            'created_at': cert.requested_at,
            'days_pending': days_pending,
        })

    total_pending = len(pending_verifications)

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
        updated_at__date=today
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
