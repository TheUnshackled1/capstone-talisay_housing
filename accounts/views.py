from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .forms import LoginForm
from intake.models import Applicant, QueueEntry, CDRRMOCertification, SMSLog, Blacklist
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
    """
    # Verify user has correct position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This dashboard is for the Head position only.')
        return redirect('accounts:dashboard')

    # MODULE 1: Intake and eligibility metrics
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

    context = {
        'page_title': 'Head Dashboard',
        'user_position': 'head',

        # MODULE 1 Metrics
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

        # Legacy M2+ placeholders
        'awaiting_signature': 0,  # TODO: Applications pending head signature (M2)
        'housing_units': 0,  # TODO: Total units at GK Cabatangan
        'monthly_reports': 0,  # TODO: Reports generated this month (M6)
        'pending_approvals': [],  # TODO: Applications awaiting final signature
        'recent_reports': [],  # TODO: Recently generated analytics reports
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
        'escalated_complaints': 0,  # TODO: Complaints escalated to OIC (M5)
        'escalated_cases': [],  # M5 (TODO)
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
    
    context = {
        'page_title': 'Second Member Dashboard',
        'user_position': 'second_member',
        # Original second member stats
        'total_applicants': 0,  # TODO: Total applicants
        'pending_notices': 0,  # TODO: Compliance notices to prepare
        'electricity_pending': 0,  # TODO: Electricity connections pending
        'incomplete_docs': 0,  # TODO: Profiles with incomplete documents
        # Added fourth member stats
        'queue_today': 0,  # TODO: Applicants in queue today
        'incomplete_requirements': 0,  # TODO: Applicants with incomplete requirements
        'documents_filed': 0,  # TODO: Documents filed this month
        'lots_for_awarding': 0,  # TODO: Vacant units available for awarding
        # Widget data
        'notices_to_prepare': [],  # TODO: List of notices to prepare
        'electricity_tracking': [],  # TODO: Electricity connection tracking items
        'doc_completeness_alerts': [],  # TODO: Profiles needing document attention
        'reports_to_generate': [],  # TODO: Reports due for Full Disclosure Portal
        # Added fourth member widget data
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
def dashboard_field(request):
    """
    Dashboard for Field Personnel (Ronda - Paul Betila, Roberto Dreyfus, Nonoy)
    Responsibilities: Census, field verification, site inspection, complaint logging
    """
    if request.user.position not in ['ronda', 'field']:
        messages.error(request, 'Access denied. This dashboard is for Field Personnel only.')
        return redirect('accounts:dashboard')
    
    context = {
        'page_title': 'Field Personnel Dashboard',
        'user_position': request.user.position,
        'registered_applicants': 0,  # TODO: Total registered
        'pending_applications': 0,  # TODO: Applications pending
        'housing_units': 0,  # TODO: Total units
        'open_cases': 0,  # TODO: Open complaint cases
    }
    return render(request, 'accounts/dashboard.html', context)


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
