from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm


def login_view(request):
    """Staff login page."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
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
                next_url = request.GET.get('next', 'dashboard')
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
def dashboard_view(request):
    """
    Main staff dashboard with role-specific data.
    Each staff member sees widgets and data relevant to their responsibilities.
    """
    user = request.user
    position = user.position
    
    # Base context for all users
    context = {
        'page_title': 'Dashboard',
        'user_position': position,
    }
    
    # Role-specific dashboard data
    if position == 'head':
        # Arthur Maramba - Head
        # M2 (final signatory), M6 (receives reports)
        context.update({
            'total_applicants': 0,  # TODO: Query from intake module
            'awaiting_signature': 0,  # TODO: Applications pending head signature
            'housing_units': 0,  # TODO: Total units at GK Cabatangan
            'monthly_reports': 0,  # TODO: Reports generated this month
            'pending_approvals': [],  # TODO: Applications awaiting final signature
            'recent_reports': [],  # TODO: Recently generated analytics reports
        })
    
    elif position == 'oic':
        # Victor Fregil - OIC
        # M2 (OIC signatory step), M4 (compliance decisions), M5 (escalated complaint decisions)
        context.update({
            'total_applicants': 0,  # TODO: Total in system
            'awaiting_signature': 0,  # TODO: Applications pending OIC signature
            'compliance_cases': 0,  # TODO: Active compliance cases
            'escalated_complaints': 0,  # TODO: Complaints escalated to OIC
            'pending_oic_approvals': [],  # TODO: Applications at OIC step
            'pending_compliance_decisions': [],  # TODO: Compliance cases needing decision
            'escalated_cases': [],  # TODO: Complaint cases escalated to OIC
        })
    
    elif position == 'second_member':
        # Lourynie Joie V. Tingson - Second Member
        # M2 (notices, electricity), M3 (docs oversight), M4 (compliance notices), M6 (reports)
        context.update({
            'total_applicants': 0,  # TODO: Total applicants
            'pending_notices': 0,  # TODO: Compliance notices to prepare
            'electricity_pending': 0,  # TODO: Electricity connections pending
            'incomplete_docs': 0,  # TODO: Profiles with incomplete documents
            'notices_to_prepare': [],  # TODO: List of notices to prepare
            'electricity_tracking': [],  # TODO: Electricity connection tracking items
            'doc_completeness_alerts': [],  # TODO: Profiles needing document attention
            'reports_to_generate': [],  # TODO: Reports due for Full Disclosure Portal
        })
    
    elif position == 'third_member':
        # Roland Jay S. Olvido - Third Member
        # M1 (census, field verification), M2 (signatory routing), M4 (site inspection), M5 (violation investigation)
        context.update({
            'census_records': 0,  # TODO: Total census records
            'pending_verification': 0,  # TODO: Applicants awaiting field verification
            'site_inspections': 0,  # TODO: Inspections scheduled/due
            'open_investigations': 0,  # TODO: Active violation investigations
            'routing_queue': [],  # TODO: Documents to route OIC→Head
            'verification_queue': [],  # TODO: Applicants needing field verification
            'inspection_schedule': [],  # TODO: Site inspections due
            'active_investigations': [],  # TODO: Violation cases under investigation
        })
    
    elif position == 'fourth_member':
        # Jocel O. Cuaysing - Fourth Member
        # M1 (masterlist, eligibility, queue), M2 (requirements, lot awarding), M3 (docs), M4 (property custodian)
        context.update({
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
        })
    
    elif position == 'fifth_member':
        # Laarni C. Hellera - Fifth Member
        # M2 (electricity connection tracking with Joie)
        context.update({
            'pending_connections': 0,  # TODO: Electricity connections pending
            'connected_this_month': 0,  # TODO: Connections completed this month
            'awaiting_negros_power': 0,  # TODO: Applications with Negros Power
            'monthly_notices': 0,  # TODO: Notices sent this month
            'electricity_queue': [],  # TODO: Beneficiaries in electricity connection process
            'negros_power_pending': [],  # TODO: Applications pending with Negros Power
        })
    
    else:
        # Default for field staff/other roles
        context.update({
            'registered_applicants': 0,  # TODO: Total registered
            'pending_applications': 0,  # TODO: Applications pending
            'housing_units': 0,  # TODO: Total units
            'open_cases': 0,  # TODO: Open complaint cases
        })
    
    return render(request, 'accounts/dashboard.html', context)
