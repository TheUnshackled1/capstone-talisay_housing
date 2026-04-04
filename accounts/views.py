from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm


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
    Responsibilities: M2 (final signatory), M6 (receives reports)
    """
    # Verify user has correct position
    if request.user.position != 'head':
        messages.error(request, 'Access denied. This dashboard is for the Head position only.')
        return redirect('accounts:dashboard')
    
    context = {
        'page_title': 'Head Dashboard',
        'user_position': 'head',
        'total_applicants': 0,  # TODO: Query from intake module
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
    Responsibilities: M2 (OIC signatory), M4 (compliance), M5 (escalated complaints)
    """
    if request.user.position != 'oic':
        messages.error(request, 'Access denied. This dashboard is for the OIC position only.')
        return redirect('accounts:dashboard')
    
    context = {
        'page_title': 'OIC Dashboard',
        'user_position': 'oic',
        'total_applicants': 0,  # TODO: Total in system
        'awaiting_signature': 0,  # TODO: Applications pending OIC signature
        'compliance_cases': 0,  # TODO: Active compliance cases
        'escalated_complaints': 0,  # TODO: Complaints escalated to OIC
        'pending_oic_approvals': [],  # TODO: Applications at OIC step
        'pending_compliance_decisions': [],  # TODO: Compliance cases needing decision
        'escalated_cases': [],  # TODO: Complaint cases escalated to OIC
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
        'total_applicants': 0,  # TODO: Total applicants
        'pending_notices': 0,  # TODO: Compliance notices to prepare
        'electricity_pending': 0,  # TODO: Electricity connections pending
        'incomplete_docs': 0,  # TODO: Profiles with incomplete documents
        'notices_to_prepare': [],  # TODO: List of notices to prepare
        'electricity_tracking': [],  # TODO: Electricity connection tracking items
        'doc_completeness_alerts': [],  # TODO: Profiles needing document attention
        'reports_to_generate': [],  # TODO: Reports due for Full Disclosure Portal
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
