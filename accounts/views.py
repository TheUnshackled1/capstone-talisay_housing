from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm
from intake.models import Applicant, QueueEntry, CDRRMOCertification, Blacklist
from django.utils import timezone
from django.db.models import Q
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
    Responsibilities: M1 (executive summary), M2 (final signatory), M6 (receives reports)
    """
    # Verify user has correct position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This dashboard is for the Head position only.')
        return redirect('accounts:dashboard')

    # ===== MODULE 1 QUERIES (EXECUTIVE SUMMARY) =====

    # QUERY: Total applicants and channel breakdown
    total_applicants = Applicant.objects.count()
    channel_a = Applicant.objects.filter(channel='landowner').count()
    channel_b = Applicant.objects.filter(channel='danger_zone').count()
    channel_c = Applicant.objects.filter(channel='walk_in').count()

    # QUERY: Eligibility pass rate
    eligible_count = Applicant.objects.filter(status='eligible').count()
    disqualified_count = Applicant.objects.filter(status='disqualified').count()
    eligibility_pass_rate = 0
    if total_applicants > 0:
        eligibility_pass_rate = (eligible_count / total_applicants) * 100

    # QUERY: Queue status breakdown
    priority_count = QueueEntry.objects.filter(queue_type='priority', status='active').count()
    walkin_count = QueueEntry.objects.filter(queue_type='walk_in', status='active').count()

    # QUERY: Critical alerts
    from intake.models import SMSLog
    from datetime import timedelta

    # CDRRMO overdue (>14 days pending)
    cutoff_date = timezone.now() - timedelta(days=14)
    overdue_cdrrmo = CDRRMOCertification.objects.filter(
        status='pending',
        requested_at__lt=cutoff_date
    ).count()

    # Recent blacklist additions
    blacklist_count = Blacklist.objects.count()
    recent_blacklist_count = Blacklist.objects.filter(
        blacklisted_at__gte=timezone.now() - timedelta(days=30)
    ).count()

    # SMS failures in last 7 days
    sms_failed_recent = SMSLog.objects.filter(
        status='failed',
        sent_at__gte=timezone.now() - timedelta(days=7)
    ).count()

    context = {
        'page_title': 'Head Dashboard',
        'user_position': 'head',

        # ===== MODULE 1: EXECUTIVE SUMMARY =====
        'total_applicants': total_applicants,

        # Channel breakdown
        'channel_a': channel_a,
        'channel_b': channel_b,
        'channel_c': channel_c,

        # Eligibility metrics
        'eligible_count': eligible_count,
        'disqualified_count': disqualified_count,
        'eligibility_pass_rate': round(eligibility_pass_rate, 2),

        # Queue metrics
        'priority_queue_count': priority_count,
        'walkin_queue_count': walkin_count,
        'total_in_queue': priority_count + walkin_count,

        # ===== CRITICAL ALERTS =====
        'overdue_cdrrmo': overdue_cdrrmo,
        'blacklist_count': blacklist_count,
        'recent_blacklist': recent_blacklist_count,
        'sms_failed_recent': sms_failed_recent,

        # ===== MODULE 2+ (FUTURE) =====
        'awaiting_signature': 0,  # TODO: Applications pending head signature
        'housing_units': 0,  # TODO: Total units at GK Cabatangan
        'monthly_reports': 0,  # TODO: Reports generated this month
        'pending_approvals': [],  # TODO: Applications awaiting final signature
        'recent_reports': [],  # TODO: Recently generated analytics reports
    }

    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_oic(request):
    """
    Dashboard for OIC-THA (Victor Fregil)
    Responsibilities: M1 (system oversight), M2 (OIC signatory), M4 (compliance), M5 (escalated complaints)
    """
    if request.user.position != 'oic':
        messages.error(request, 'Access denied. This dashboard is for the OIC position only.')
        return redirect('accounts:dashboard')

    # ===== MODULE 1 QUERIES (SYSTEM OVERSIGHT) =====

    # QUERY: Total applicants in system (all channels A/B/C)
    total_applicants = Applicant.objects.count()

    # QUERY: All active queue entries (priority + walk-in)
    active_queue = QueueEntry.objects.filter(status='active').select_related('applicant')
    priority_count = active_queue.filter(queue_type='priority').count()
    walkin_count = active_queue.filter(queue_type='walk_in').count()

    # QUERY: SMS Delivery Status
    from intake.models import SMSLog
    sms_total = SMSLog.objects.count()
    sms_sent = SMSLog.objects.filter(status='sent').count()
    sms_failed = SMSLog.objects.filter(status='failed').count()
    sms_pending = SMSLog.objects.filter(status='pending').count()

    # Calculate SMS success rate
    sms_success_rate = 0
    if sms_total > 0:
        sms_success_rate = (sms_sent / sms_total) * 100

    # QUERY: Recent failed SMS (last 10)
    failed_sms = SMSLog.objects.filter(status='failed').order_by('-sent_at')[:10]

    # QUERY: Pending CDRRMO certifications (danger zone)
    pending_cdrrmo = CDRRMOCertification.objects.filter(status='pending').count()

    # QUERY: Overdue CDRRMO (>14 days pending)
    from django.utils import timezone
    from datetime import timedelta
    cutoff_date = timezone.now() - timedelta(days=14)
    overdue_cdrrmo = CDRRMOCertification.objects.filter(
        status='pending',
        requested_at__lt=cutoff_date
    ).count()

    # QUERY: Blacklist count (critical alert)
    blacklist_count = Blacklist.objects.count()

    # QUERY: Recent blacklist additions (last 5)
    recent_blacklist = Blacklist.objects.order_by('-blacklisted_at')[:5]

    context = {
        'page_title': 'OIC Dashboard',
        'user_position': 'oic',

        # ===== MODULE 1: SYSTEM OVERVIEW =====
        'total_applicants': total_applicants,
        'priority_queue_count': priority_count,
        'walkin_queue_count': walkin_count,
        'total_in_queue': priority_count + walkin_count,

        # ===== SMS DELIVERY STATUS =====
        'sms_total': sms_total,
        'sms_sent': sms_sent,
        'sms_failed': sms_failed,
        'sms_pending': sms_pending,
        'sms_success_rate': round(sms_success_rate, 2),

        # ===== CRITICAL ALERTS =====
        'pending_cdrrmo': pending_cdrrmo,
        'overdue_cdrrmo': overdue_cdrrmo,
        'blacklist_count': blacklist_count,
        'recent_blacklist': recent_blacklist,
        'failed_sms': failed_sms,

        # ===== MODULE 2+ (FUTURE) =====
        'awaiting_signature': 0,  # TODO: Applications pending OIC signature (Module 2)
        'compliance_cases': 0,  # TODO: Active compliance cases (Module 4)
        'escalated_complaints': 0,  # TODO: Escalated complaints (Module 5)
        'pending_oic_approvals': [],  # TODO: Applications at OIC step
        'pending_compliance_decisions': [],  # TODO: Compliance cases
        'escalated_cases': [],  # TODO: Escalated cases
    }

    return render(request, 'accounts/dashboard.html', context)


@login_required
def dashboard_second_member(request):
    """
    Dashboard for Second Member (Lourynie Joie V. Tingson)
    Responsibilities: M2 (notices, electricity), M3 (docs), M4 (compliance), M6 (reports)
    Also supervises Module 1 intake with Fourth Member
    """
    if request.user.position != 'second_member':
        messages.error(request, 'Access denied. This dashboard is for the Second Member position only.')
        return redirect('accounts:dashboard')

    # ===== MODULE 1 QUERIES (SHARED WITH FOURTH MEMBER) =====

    # QUERY: Total applicants in system
    total_applicants = Applicant.objects.count()

    # QUERY: Priority Queue (active, ordered by position)
    priority_queue = QueueEntry.objects.filter(
        queue_type='priority',
        status='active'
    ).select_related('applicant').order_by('position')

    # QUERY: Walk-in Queue (active, ordered by position)
    walkin_queue = QueueEntry.objects.filter(
        queue_type='walk_in',
        status='active'
    ).select_related('applicant').order_by('position')

    # QUERY: Pending CDRRMO (danger zone applicants awaiting certification)
    pending_cdrrmo = CDRRMOCertification.objects.filter(
        status='pending'
    ).select_related('applicant')

    # QUERY: Applicants with incomplete documents
    incomplete_requirements = Applicant.objects.filter(
        status__in=['eligible', 'requirements']
    ).select_related('barangay')

    # Count incomplete docs per applicant
    incomplete_count = 0
    incomplete_docs_list = []
    for app in incomplete_requirements:
        docs_complete = all([
            app.doc_brgy_residency,
            app.doc_brgy_indigency,
            app.doc_cedula,
            app.doc_police_clearance,
            app.doc_no_property,
            app.doc_2x2_picture,
            app.doc_sketch_location
        ])
        if not docs_complete:
            incomplete_count += 1
            incomplete_docs_list.append(app)

    # QUERY: Blacklist count
    blacklist_count = Blacklist.objects.count()

    # QUERY: Standby queue (fully approved, awaiting lot assignment)
    standby_queue = Applicant.objects.filter(
        status='standby'
    ).select_related('barangay')

    # ===== MODULE 2+ QUERIES (M2: NOTICES, ELECTRICITY, etc.) =====
    # TODO: Add electricity connection tracking queries when electricity model is created

    context = {
        'page_title': 'Second Member Dashboard',
        'user_position': 'second_member',

        # ===== TOTALS & COUNTS =====
        'total_applicants': total_applicants,
        'queue_today': priority_queue.count() + walkin_queue.count(),
        'incomplete_requirements': incomplete_count,
        'incomplete_docs': incomplete_count,  # Same as incomplete_requirements for Module 1
        'pending_notices': 0,  # TODO: Compliance notices (future)
        'electricity_pending': 0,  # TODO: Electricity connections (future)
        'documents_filed': 0,  # TODO: Documents filed this month (future)
        'lots_for_awarding': 0,  # TODO: Vacant units (future)

        # ===== QUEUE DATA =====
        'priority_queue': priority_queue[:5],  # Top 5 for display
        'walkin_queue': walkin_queue[:5],  # Top 5 for display
        'pending_cdrrmo': pending_cdrrmo,
        'requirements_checklist': incomplete_docs_list[:10],  # Top 10 with incomplete docs
        'standby_queue': standby_queue,
        'available_lots': [],  # TODO: Housing units (future)
        'blacklist_count': blacklist_count,
        'repossessed_count': 0,  # TODO: Applications module
        'awaiting_reaward': 0,  # TODO: Applications module

        # ===== FUTURE WIDGETS (M2, M3, M4, M6) =====
        'notices_to_prepare': [],  # TODO: Compliance notices list
        'electricity_tracking': [],  # TODO: Electricity connection tracking
        'doc_completeness_alerts': incomplete_docs_list[:5],  # Reuse incomplete docs for now
        'reports_to_generate': [],  # TODO: Full Disclosure Portal reports
    }

    # Calculate ready_to_award (min of available lots and standby queue)
    standby_count = standby_queue.count()
    available_count = len(context['available_lots'])
    context['ready_to_award'] = min(standby_count, available_count) if available_count > 0 else 0

    # Add total counts for display
    context['priority_queue_total'] = priority_queue.count()
    context['walkin_queue_total'] = walkin_queue.count()
    context['pending_cdrrmo_total'] = pending_cdrrmo.count()

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

    # QUERY: Priority Queue (active, ordered by position)
    priority_queue = QueueEntry.objects.filter(
        queue_type='priority',
        status='active'
    ).select_related('applicant').order_by('position')

    # QUERY: Walk-in Queue (active, ordered by position)
    walkin_queue = QueueEntry.objects.filter(
        queue_type='walk_in',
        status='active'
    ).select_related('applicant').order_by('position')

    # QUERY: Pending CDRRMO (danger zone applicants awaiting certification)
    pending_cdrrmo = CDRRMOCertification.objects.filter(
        status='pending'
    ).select_related('applicant')

    # QUERY: Applicants with incomplete requirements
    # (status is 'requirements' or eligible but missing documents)
    incomplete_requirements = Applicant.objects.filter(
        status__in=['eligible', 'requirements']
    ).select_related('barangay')

    # Count incomplete docs per applicant
    incomplete_count = 0
    incomplete_docs_list = []
    for app in incomplete_requirements:
        docs_complete = all([
            app.doc_brgy_residency,
            app.doc_brgy_indigency,
            app.doc_cedula,
            app.doc_police_clearance,
            app.doc_no_property,
            app.doc_2x2_picture,
            app.doc_sketch_location
        ])
        if not docs_complete:
            incomplete_count += 1
            # Calculate document completion percentage and count
            docs_submitted = sum([
                app.doc_brgy_residency,
                app.doc_brgy_indigency,
                app.doc_cedula,
                app.doc_police_clearance,
                app.doc_no_property,
                app.doc_2x2_picture,
                app.doc_sketch_location
            ])
            app.completion_percent = int((docs_submitted / 7) * 100)
            app.docs_count = docs_submitted
            incomplete_docs_list.append(app)

    # QUERY: Blacklist count
    blacklist_count = Blacklist.objects.count()

    # QUERY: Standby queue (fully approved, awaiting lot assignment)
    standby_queue = Applicant.objects.filter(
        status='standby'
    ).select_related('barangay')

    context = {
        'page_title': 'Fourth Member Dashboard',
        'user_position': 'fourth_member',
        'queue_today': priority_queue.count() + walkin_queue.count(),
        'incomplete_requirements': incomplete_count,
        'documents_filed': 0,  # TODO: Query from document upload model (future)
        'lots_for_awarding': 0,  # TODO: Query from housing units model (future)
        'priority_queue': priority_queue[:5],  # Top 5 for display
        'walkin_queue': walkin_queue[:5],  # Top 5 for display
        'pending_cdrrmo': pending_cdrrmo,
        'requirements_checklist': incomplete_docs_list[:10],  # Top 10 incomplete
        'standby_queue': standby_queue,
        'available_lots': [],  # TODO: Query from housing units model (future)
        'blacklist_count': blacklist_count,
        'repossessed_count': 0,  # TODO: Query from applications module
        'awaiting_reaward': 0,  # TODO: Query from applications module
    }

    # Calculate ready_to_award (min of available lots and standby queue)
    standby_count = standby_queue.count()
    available_count = len(context['available_lots'])
    context['ready_to_award'] = min(standby_count, available_count) if available_count > 0 else 0

    # Add total counts for display
    context['priority_queue_total'] = priority_queue.count()
    context['walkin_queue_total'] = walkin_queue.count()
    context['pending_cdrrmo_total'] = pending_cdrrmo.count()

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
