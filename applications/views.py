from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Prefetch, Max
from django.utils import timezone
from functools import wraps
from intake.models import Applicant, QueueEntry
from intake.utils import send_sms, check_blacklist
from .models import (
    Application, Requirement, RequirementSubmission,
    SignatoryRouting, FacilitatedService, ElectricityConnection, LotAwarding
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
# ACCESS CONTROL HELPERS
# =============================================================================

def get_module2_permissions(user):
    """
    Return permissions dict based on user position.
    
    Module 2 Staff Roles:
    - Jocel (4th Member): Verify documents, generate forms, record lot awarding
    - Jay (3rd Member): Receive documents, forward to OIC/Head
    - Joie (2nd Member): Supervisor, electricity tracking
    - Laarni (5th Member): Electricity tracking
    - Victor (OIC): Sign applications
    - Arthur (Head): Final signature
    """
    position = user.position
    
    permissions = {
        'can_view': False,
        'can_verify_documents': False,
        'can_generate_form': False,
        'can_receive_routing': False,
        'can_forward_routing': False,
        'can_sign_oic': False,
        'can_sign_head': False,
        'can_award_lot': False,
        'can_manage_electricity': False,
        'role_description': '',
    }
    
    if position == 'fourth_member':
        # Jocel - Primary processor
        permissions.update({
            'can_view': True,
            'can_verify_documents': True,
            'can_generate_form': True,
            'can_award_lot': True,
            'role_description': 'Document Verification & Lot Awarding',
        })
    elif position == 'second_member':
        # Joie - Supervisor + Electricity
        permissions.update({
            'can_view': True,
            'can_verify_documents': True,  # Supervisor can also verify
            'can_generate_form': True,
            'can_manage_electricity': True,
            'role_description': 'Supervisor & Electricity Tracking',
        })
    elif position == 'fifth_member':
        # Laarni - Electricity only
        permissions.update({
            'can_view': True,
            'can_manage_electricity': True,
            'role_description': 'Electricity Tracking',
        })
    elif position == 'oic':
        # Victor - OIC signature
        permissions.update({
            'can_view': True,
            'can_sign_oic': True,
            'role_description': 'OIC Signatory',
        })
    elif position == 'head':
        # Arthur - Head/Final signature
        permissions.update({
            'can_view': True,
            'can_sign_head': True,
            'role_description': 'Head/Final Signatory',
        })
    
    return permissions


def _active_intake_queue_label(applicant):
    """Human-readable label from Module 1 QueueEntry (D2 eligibility & queue)."""
    entries = getattr(applicant, 'active_queue_entries', None) or []
    if not entries:
        return '—'
    qe = entries[0]
    if qe.queue_type == 'priority':
        return f'Priority #{qe.position}'
    return f'Queue #{qe.position}'


# =============================================================================
# MAIN APPLICATIONS LIST VIEW
# =============================================================================

@login_required
@verify_position
def applications_list(request, position):
    """
    Module 2 - Housing Application & Evaluation
    Shows eligible applicants with document checklist progress, signatory routing, etc.

    URL: /applications/<position>/list/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Full access: verify docs, generate forms, award lots
    ✅ Jay (3rd Member) - View + routing actions
    ✅ Joie (2nd Member) - Supervisor: verify docs, electricity tracking
    ✅ Laarni (5th Member) - Electricity tracking only
    ✅ Victor (OIC) - View + OIC signature
    ✅ Arthur (Head) - View + Head signature
    """
    # Check access
    allowed_positions = ['fourth_member', 'second_member', 'fifth_member', 'oic', 'head']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. Module 2 is for authorized staff only.')
        return redirect('accounts:dashboard')
    
    # Get user permissions
    permissions = get_module2_permissions(request.user)
    
    # Get all eligible applicants (status='eligible' or beyond in the workflow)
    applicants = Applicant.objects.filter(
        status__in=['eligible', 'requirements', 'application', 'standby', 'awarded']
    ).select_related('application').prefetch_related(
        'requirement_submissions',
        'requirement_submissions__requirement',
        Prefetch(
            'application__routing_steps',
            queryset=SignatoryRouting.objects.order_by('action_at'),
        ),
        Prefetch(
            'queue_entries',
            queryset=QueueEntry.objects.filter(status='active').order_by('position'),
            to_attr='active_queue_entries',
        ),
    ).order_by('-created_at')
    
    # Get all requirements for the checklist
    requirements = Requirement.objects.filter(is_active=True).order_by('group', 'order')
    group_a_requirements = requirements.filter(group='A')
    group_b_requirements = requirements.filter(group='B')
    
    # Stage counts for summary cards
    stage_counts = {
        'eligibility': applicants.filter(
            Q(application__isnull=True) | Q(application__status='draft')
        ).filter(
            requirement_submissions__status='verified'
        ).distinct().count(),
        'document_gathering': applicants.filter(
            application__isnull=True
        ).count(),
        'form_released': applicants.filter(
            application__status__in=['draft', 'completed']
        ).count(),
        'signatory_routing': applicants.filter(
            application__status='routing'
        ).count(),
        'fully_approved': applicants.filter(
            application__status__in=['oic_signed', 'head_signed', 'standby']
        ).count(),
        'lot_awarded': applicants.filter(
            application__status='awarded'
        ).count(),
    }
    
    # Check for routing delays (>3 days)
    delayed_routings = SignatoryRouting.objects.filter(
        action_at__lt=timezone.now() - timezone.timedelta(days=3)
    ).exclude(
        application__routing_steps__step='signed_head'
    ).select_related('application', 'application__applicant')
    
    # Prepare applicant data with document counts
    applicants_data = []
    for applicant in applicants:
        # Count verified Group A documents
        group_a_verified = applicant.requirement_submissions.filter(
            requirement__group='A',
            status='verified'
        ).count()
        
        # Check if form can be generated (all 7 Group A verified)
        can_generate_form = group_a_verified >= 7
        
        # Get application status if exists
        application = getattr(applicant, 'application', None)
        application_status = application.status if application else None
        
        # Determine current stage
        if application and application.status == 'awarded':
            current_stage = 'Lot Awarded'
        elif application and application.status in ['head_signed', 'standby']:
            current_stage = 'Fully Approved'
        elif application and application.status in ['routing', 'oic_signed']:
            current_stage = 'Signatory Routing'
        elif application and application.status in ['draft', 'completed']:
            current_stage = 'Form Released'
        elif group_a_verified > 0:
            current_stage = 'Document Gathering'
        else:
            current_stage = 'Eligibility'
        
        # Get routing status
        routing_status = 'Not Started'
        latest_routing_step = None
        if application:
            latest_routing = application.routing_steps.last()
            if latest_routing:
                latest_routing_step = latest_routing.step
                if latest_routing.step == 'signed_head':
                    routing_status = 'Completed'
                else:
                    routing_status = 'In Progress'
        
        # Check for routing delay
        is_delayed = False
        delayed_at = None
        if application:
            for step in application.routing_steps.all():
                if step.is_delayed:
                    is_delayed = True
                    delayed_at = step.get_step_display()
                    break
        
        # Determine what actions this user can take on this applicant
        user_actions = []
        if permissions['can_verify_documents'] and not application:
            user_actions.append('verify_docs')
        if permissions['can_generate_form'] and can_generate_form and not application:
            user_actions.append('generate_form')
        if permissions['can_receive_routing'] and application and application.status == 'completed':
            user_actions.append('receive_routing')
        if permissions['can_forward_routing'] and application and latest_routing_step == 'received':
            user_actions.append('forward_to_oic')
        if permissions['can_sign_oic'] and application and latest_routing_step == 'forwarded_oic':
            user_actions.append('sign_oic')
        if permissions['can_forward_routing'] and application and latest_routing_step == 'signed_oic':
            user_actions.append('forward_to_head')
        if permissions['can_sign_head'] and application and latest_routing_step == 'forwarded_head':
            user_actions.append('sign_head')
        if permissions['can_award_lot'] and application and application.status in ['head_signed', 'standby']:
            user_actions.append('award_lot')
        if permissions['can_manage_electricity'] and application and application.status == 'awarded':
            user_actions.append('manage_electricity')

        # --- Module 2 workflow: 2.1 Blacklist (D1 applicant profile) ---
        is_bl, bl_entry = check_blacklist(applicant.full_name, applicant.phone_number or None)
        blacklist_blocked = bool(is_bl)
        blacklist_detail = ''
        if blacklist_blocked and bl_entry:
            blacklist_detail = f'{bl_entry.get_reason_display()}'
            if bl_entry.notes:
                blacklist_detail += f' — {bl_entry.notes[:200]}'
        if blacklist_blocked:
            user_actions = [a for a in user_actions if a not in ('verify_docs', 'generate_form')]

        applicants_data.append({
            'applicant': applicant,
            'application': application,
            'group_a_verified': group_a_verified,
            'can_generate_form': can_generate_form and application is None and not blacklist_blocked,
            'form_generated': application is not None,
            'current_stage': current_stage,
            'routing_status': routing_status,
            'latest_routing_step': latest_routing_step,
            'is_delayed': is_delayed,
            'delayed_at': delayed_at,
            'user_actions': user_actions,
            'blacklist_blocked': blacklist_blocked,
            'blacklist_detail': blacklist_detail,
            'm1_income_eligible': applicant.is_income_eligible,
            'm1_declares_no_property': not applicant.has_property_in_talisay,
            'household_size': applicant.household_size,
            'intake_queue_label': _active_intake_queue_label(applicant),
        })
    
    # Filter by stage if requested
    filter_stage = request.GET.get('stage', 'all')
    if filter_stage != 'all':
        stage_map = {
            'eligibility': 'Eligibility',
            'document_gathering': 'Document Gathering',
            'form_released': 'Form Released',
            'signatory_routing': 'Signatory Routing',
            'fully_approved': 'Fully Approved',
            'lot_awarded': 'Lot Awarded',
        }
        target_stage = stage_map.get(filter_stage)
        if target_stage:
            applicants_data = [a for a in applicants_data if a['current_stage'] == target_stage]
    
    # Search filter
    search = request.GET.get('search', '')
    if search:
        applicants_data = [
            a for a in applicants_data
            if search.lower() in a['applicant'].full_name.lower() or
               search.lower() in a['applicant'].reference_number.lower()
        ]
    
    context = {
        'applicants_data': applicants_data,
        'stage_counts': stage_counts,
        'requirements': requirements,
        'group_a_requirements': group_a_requirements,
        'group_b_requirements': group_b_requirements,
        'delayed_routings': delayed_routings,
        'filter_stage': filter_stage,
        'search': search,
        'total_eligible': applicants.count(),
        'permissions': permissions,
        'user_position': request.user.position,
    }
    
    return render(request, 'applications/applications_list.html', context)


# =============================================================================
# APPLICATION DETAIL (AJAX)
# =============================================================================

@login_required
@verify_position
def application_detail(request, position, application_id):
    """
    Get applicant/application detail for modal (AJAX).

    URL: /applications/<position>/detail/<application_id>/

    Accepts either an Applicant ID or Application ID and returns
    the relevant information for the modal display.
    """
    # Try to find as Applicant first (for pre-application stage)
    applicant = None
    application = None
    
    try:
        applicant = Applicant.objects.prefetch_related(
            'requirement_submissions',
            'requirement_submissions__requirement',
            Prefetch(
                'queue_entries',
                queryset=QueueEntry.objects.filter(status='active').order_by('position'),
                to_attr='active_queue_entries',
            ),
        ).get(id=application_id)
        # Check if this applicant has an application
        application = getattr(applicant, 'application', None)
    except Applicant.DoesNotExist:
        # Try as Application ID
        application = get_object_or_404(
            Application.objects.select_related('applicant').prefetch_related(
                'routing_steps',
                'applicant__requirement_submissions',
                'applicant__requirement_submissions__requirement',
                Prefetch(
                    'applicant__queue_entries',
                    queryset=QueueEntry.objects.filter(status='active').order_by('position'),
                    to_attr='active_queue_entries',
                ),
            ),
            id=application_id
        )
        applicant = application.applicant
    
    # Get user permissions
    permissions = get_module2_permissions(request.user)
    
    # Build response data
    is_bl, bl_entry = check_blacklist(applicant.full_name, applicant.phone_number or None)
    bl_detail = ''
    if is_bl and bl_entry:
        bl_detail = bl_entry.get_reason_display()
        if bl_entry.notes:
            bl_detail += f' — {bl_entry.notes[:200]}'

    data = {
        'applicant_id': str(applicant.id),
        'applicant_name': applicant.full_name,
        'applicant_phone': applicant.phone_number,
        'reference_number': applicant.reference_number,
        'requirements': [],
        'routing_steps': [],
        'latest_step': None,
        'has_application': application is not None,
        'permissions': permissions,
        'blacklist_blocked': is_bl,
        'blacklist_detail': bl_detail,
        'm1_income_eligible': applicant.is_income_eligible,
        'm1_declares_no_property': not applicant.has_property_in_talisay,
        'household_size': applicant.household_size,
        'intake_queue_label': _active_intake_queue_label(applicant),
    }
    
    if application:
        data.update({
            'id': str(application.id),
            'application_number': application.application_number,
            'status': application.status,
            'status_display': application.get_status_display(),
        })
        
        # Add routing steps
        latest_step = None
        for step in application.routing_steps.all().order_by('action_at'):
            latest_step = step.step
            data['routing_steps'].append({
                'step': step.step,
                'step_display': step.get_step_display(),
                'action_at': step.action_at.strftime('%Y-%m-%d %H:%M'),
                'action_by': step.action_by.get_full_name() if step.action_by else 'System',
                'is_delayed': step.is_delayed,
                'days_since': step.days_since_action,
            })
        data['latest_step'] = latest_step
    
    # Add requirements status
    for submission in applicant.requirement_submissions.all():
        data['requirements'].append({
            'code': submission.requirement.code,
            'name': submission.requirement.name,
            'group': submission.requirement.group,
            'status': submission.status,
            'verified': submission.status == 'verified',
        })
    
    return JsonResponse(data)


# =============================================================================
# DOCUMENT VERIFICATION (Jocel, Joie)
# =============================================================================

@login_required
@verify_position
@require_POST
def update_requirement(request, position):
    """
    Update requirement submission status (AJAX).

    URL: /applications/<position>/requirement/update/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary document verifier
    ✅ Joie (2nd Member) - Supervisor backup
    """
    # Check permission
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False, 
            'error': 'Permission denied. Only Jocel or Joie can verify documents.'
        }, status=403)
    
    applicant_id = request.POST.get('applicant_id')
    requirement_code = request.POST.get('requirement_code')
    status = request.POST.get('status')
    
    try:
        applicant = Applicant.objects.get(id=applicant_id)
        is_bl, bl_entry = check_blacklist(applicant.full_name, applicant.phone_number or None)
        if is_bl:
            reason = bl_entry.get_reason_display() if bl_entry else 'Blacklist match'
            return JsonResponse(
                {
                    'success': False,
                    'error': (
                        f'Blacklist (process 2.1): applicant matches master blacklist ({reason}). '
                        'Disqualify in Module 1 and record remarks before verifying requirements.'
                    ),
                },
                status=400,
            )

        requirement = Requirement.objects.get(code=requirement_code)
        
        submission, created = RequirementSubmission.objects.get_or_create(
            applicant=applicant,
            requirement=requirement,
            defaults={'status': status}
        )
        
        if not created:
            submission.status = status
            if status == 'verified':
                submission.verified_at = timezone.now()
                submission.verified_by = request.user
            elif status == 'submitted':
                submission.submitted_at = timezone.now()
            submission.save()
        
        # Check if all 7 Group A documents are now verified
        group_a_verified = applicant.requirement_submissions.filter(
            requirement__group='A',
            status='verified'
        ).count()
        
        # Send SMS when all 7 verified
        if group_a_verified >= 7 and applicant.phone_number:
            # Check if we already sent this notification
            existing_app = hasattr(applicant, 'application')
            if not existing_app:
                message = (
                    f"All 7 requirements verified! Please visit Talisay Housing Authority "
                    f"to sign your application form. Reference: {applicant.reference_number}"
                )
                send_sms(applicant.phone_number, message, 'documents_complete', applicant=applicant)
        
        return JsonResponse({
            'success': True,
            'group_a_verified': group_a_verified,
            'all_verified': group_a_verified >= 7,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# FORM GENERATION (Jocel, Joie)
# =============================================================================

@login_required
@verify_position
def generate_form(request, position, applicant_id):
    """
    Generate application form for applicant.

    URL: /applications/<position>/form/generate/<applicant_id>/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary
    ✅ Joie (2nd Member) - Supervisor backup
    """
    # Check permission
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Jocel or Joie can generate forms.'
        }, status=403)
    
    applicant = get_object_or_404(Applicant, id=applicant_id)

    is_bl, bl_entry = check_blacklist(applicant.full_name, applicant.phone_number or None)
    if is_bl:
        reason = bl_entry.get_reason_display() if bl_entry else 'Blacklist match'
        return JsonResponse(
            {
                'success': False,
                'error': (
                    f'Cannot generate form: blacklist match ({reason}). '
                    'Resolve in applicant profile / Module 1 first.'
                ),
            },
            status=400,
        )
    if not applicant.is_income_eligible:
        return JsonResponse(
            {
                'success': False,
                'error': 'Cannot generate form: declared income exceeds Module 1 ceiling. Correct income in Module 1.',
            },
            status=400,
        )
    if applicant.has_property_in_talisay:
        return JsonResponse(
            {
                'success': False,
                'error': 'Cannot generate form: applicant is flagged as owning property in Talisay City.',
            },
            status=400,
        )
    
    # Check if all Group A requirements are verified
    group_a_count = applicant.requirement_submissions.filter(
        requirement__group='A',
        status='verified'
    ).count()
    
    if group_a_count < 7:
        return JsonResponse({
            'success': False,
            'error': f'Only {group_a_count}/7 requirements verified. All 7 must be complete.'
        })
    
    # Check if application already exists
    if hasattr(applicant, 'application'):
        return JsonResponse({
            'success': False,
            'error': 'Application form already generated.'
        })
    
    # Create application
    application = Application.objects.create(
        applicant=applicant,
        form_generated_by=request.user,
        status='draft'
    )
    
    # Update applicant status
    applicant.status = 'application'
    applicant.save()
    
    # Send SMS notification
    if applicant.phone_number:
        message = (
            f"Your housing application form {application.application_number} has been generated. "
            f"Please visit THA office to review and sign. Reference: {applicant.reference_number}"
        )
        send_sms(applicant.phone_number, message, 'form_generated', applicant=applicant)
    
    return JsonResponse({
        'success': True,
        'application_number': application.application_number,
        'message': f'Application form {application.application_number} generated successfully.'
    })


# =============================================================================
# SIGNATORY ROUTING (Jay, OIC, Head)
# =============================================================================

@login_required
@verify_position
@require_POST
def update_routing(request, position):
    """
    Update signatory routing step (AJAX).

    URL: /applications/<position>/routing/update/

    ACCESS CONTROL:
    - Jay (3rd Member): receive, forward_oic, forward_head
    - Victor (OIC): signed_oic
    - Arthur (Head): signed_head
    """
    application_id = request.POST.get('application_id')
    step = request.POST.get('step')
    notes = request.POST.get('notes', '')
    
    # Validate step and check permission
    step_permissions = {
        'received': ['fourth_member'],
        'forwarded_oic': ['fourth_member'],
        'signed_oic': ['oic'],
        'forwarded_head': ['fourth_member'],
        'signed_head': ['head'],
    }

    allowed_positions = step_permissions.get(step, [])
    if request.user.position not in allowed_positions:
        position_names = {
            'fourth_member': 'Jocel (4th Member)',
            'oic': 'Victor (OIC)',
            'head': 'Arthur (Head)',
        }
        required = ', '.join([position_names.get(p, p) for p in allowed_positions])
        return JsonResponse({
            'success': False,
            'error': f'Permission denied. This action requires: {required}'
        }, status=403)
    
    try:
        application = Application.objects.select_related('applicant').get(id=application_id)
        
        # Create routing step
        SignatoryRouting.objects.create(
            application=application,
            step=step,
            action_by=request.user,
            notes=notes
        )
        
        # Update application status based on step
        if step == 'signed_head':
            application.status = 'head_signed'
            application.fully_approved_at = timezone.now()
            
            # Send SMS: Fully Approved
            if application.applicant.phone_number:
                message = (
                    f"Congratulations! Your housing application {application.application_number} "
                    f"has been FULLY APPROVED. You are now on the Standby Queue. "
                    f"Please wait for lot availability notification. Reference: {application.applicant.reference_number}"
                )
                send_sms(application.applicant.phone_number, message, 'fully_approved', applicant=application.applicant)
            
        elif step == 'signed_oic':
            application.status = 'oic_signed'
        elif step in ['received', 'forwarded_oic', 'forwarded_head']:
            application.status = 'routing'
        
        application.save()
        
        return JsonResponse({
            'success': True,
            'new_status': application.status,
            'message': f'Routing step "{step}" recorded successfully.'
        })
    except Application.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Application not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# MOVE TO STANDBY QUEUE
# =============================================================================

@login_required
@verify_position
@require_POST
def move_to_standby(request, position):
    """
    Move fully approved application to standby queue.

    URL: /applications/<position>/standby/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary
    ✅ Joie (2nd Member) - Supervisor
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Jocel or Joie can manage standby queue.'
        }, status=403)
    
    application_id = request.POST.get('application_id')
    
    try:
        application = Application.objects.get(id=application_id)
        
        if application.status != 'head_signed':
            return JsonResponse({
                'success': False,
                'error': 'Application must be fully approved (Head signed) before moving to standby.'
            })
        
        application.status = 'standby'
        application.standby_entered_at = timezone.now()
        
        # Calculate standby position
        last_position = Application.objects.filter(
            status='standby'
        ).exclude(id=application.id).aggregate(
            max_pos=Max('standby_position')
        )['max_pos'] or 0
        application.standby_position = last_position + 1
        
        application.save()

        if application.applicant.phone_number:
            message = (
                f"Your housing application {application.application_number} is now on the STANDBY queue "
                f"(position #{application.standby_position}). You will be notified when a lot is ready for awarding. "
                f"Reference: {application.applicant.reference_number}"
            )
            send_sms(
                application.applicant.phone_number,
                message,
                'standby_queue',
                applicant=application.applicant,
            )
        
        return JsonResponse({
            'success': True,
            'standby_position': application.standby_position,
            'message': f'Moved to Standby Queue at position #{application.standby_position}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# LOT AWARDING (Jocel)
# =============================================================================

@login_required
@verify_position
@require_POST
def award_lot(request, position):
    """
    Record lot awarding for an applicant.

    URL: /applications/<position>/lot/award/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary lot awarding
    ✅ Joie (2nd Member) - Supervisor backup
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Jocel or Joie can record lot awarding.'
        }, status=403)
    
    application_id = request.POST.get('application_id')
    lot_number = request.POST.get('lot_number')
    block_number = request.POST.get('block_number', '')
    site_name = request.POST.get('site_name', '')
    
    if not lot_number:
        return JsonResponse({'success': False, 'error': 'Lot number is required.'})
    
    try:
        application = Application.objects.select_related('applicant').get(id=application_id)
        
        if application.status not in ['head_signed', 'standby']:
            return JsonResponse({
                'success': False,
                'error': 'Application must be fully approved before lot can be awarded.'
            })
        
        # Create lot awarding record
        lot_awarding = LotAwarding.objects.create(
            application=application,
            lot_number=lot_number,
            block_number=block_number,
            site_name=site_name,
            awarded_by=request.user
        )
        
        # Update application status
        application.status = 'awarded'
        application.save()
        
        # Update applicant status
        application.applicant.status = 'awarded'
        application.applicant.save()
        
        # Create electricity connection record (pending)
        ElectricityConnection.objects.create(
            application=application,
            status='pending'
        )
        
        # Send SMS notification
        if application.applicant.phone_number:
            message = (
                f"Congratulations! You have been awarded Lot {lot_number}"
                f"{' Block ' + block_number if block_number else ''}"
                f"{' at ' + site_name if site_name else ''}. "
                f"Please visit THA office for contract signing and key turnover. "
                f"Reference: {application.applicant.reference_number}"
            )
            send_sms(application.applicant.phone_number, message, 'lot_awarded', applicant=application.applicant)
        
        return JsonResponse({
            'success': True,
            'lot_number': lot_number,
            'message': f'Lot {lot_number} awarded successfully to {application.applicant.full_name}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# ELECTRICITY TRACKING (Joie, Laarni)
# =============================================================================

@login_required
@verify_position
def electricity_list(request, position):
    """
    Electricity connection tracking view.

    URL: /applications/<position>/electricity/

    ACCESS CONTROL:
    ✅ Joie (2nd Member) - Primary
    ✅ Laarni (5th Member) - Support
    """
    allowed_positions = ['second_member', 'fifth_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. Electricity tracking is for Joie and Laarni only.')
        return redirect('applications:applications_list')
    
    connections = ElectricityConnection.objects.select_related(
        'application', 'application__applicant', 'application__lot_awarding', 'applied_by'
    ).order_by('-created_at')
    
    # Status counts
    status_counts = {
        'pending': connections.filter(status='pending').count(),
        'applied': connections.filter(status='applied').count(),
        'inspection_scheduled': connections.filter(status='inspection_scheduled').count(),
        'inspection_completed': connections.filter(status='inspection_completed').count(),
        'connected': connections.filter(status='connected').count(),
        'issues': connections.filter(status='issues').count(),
    }
    
    # Filter by status
    filter_status = request.GET.get('status', 'all')
    if filter_status != 'all':
        connections = connections.filter(status=filter_status)
    
    # Check for overdue (>30 days without connection)
    overdue_connections = [c for c in connections if c.is_overdue]
    
    context = {
        'connections': connections,
        'status_counts': status_counts,
        'filter_status': filter_status,
        'overdue_count': len(overdue_connections),
        'total_count': connections.count(),
    }
    
    return render(request, 'applications/electricity_list.html', context)


@login_required
@verify_position
@require_POST
def update_electricity(request, position):
    """
    Update electricity connection status.

    URL: /applications/<position>/electricity/update/

    ACCESS CONTROL:
    ✅ Joie (2nd Member) - Primary
    ✅ Laarni (5th Member) - Support
    """
    allowed_positions = ['second_member', 'fifth_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Joie or Laarni can update electricity status.'
        }, status=403)
    
    connection_id = request.POST.get('connection_id')
    new_status = request.POST.get('status')
    negros_power_ref = request.POST.get('negros_power_reference', '')
    inspection_date = request.POST.get('inspection_date')
    inspection_result = request.POST.get('inspection_result', '')
    meter_number = request.POST.get('meter_number', '')
    issue_description = request.POST.get('issue_description', '')
    notes = request.POST.get('notes', '')
    
    try:
        connection = ElectricityConnection.objects.select_related(
            'application', 'application__applicant'
        ).get(id=connection_id)
        
        old_status = connection.status
        connection.status = new_status
        connection.notes = notes
        
        if new_status == 'applied':
            connection.applied_at = timezone.now()
            connection.applied_by = request.user
            connection.negros_power_reference = negros_power_ref
        elif new_status == 'inspection_scheduled' and inspection_date:
            from datetime import datetime
            connection.inspection_date = datetime.strptime(inspection_date, '%Y-%m-%d').date()
        elif new_status == 'inspection_completed':
            connection.inspection_result = inspection_result
        elif new_status == 'connected':
            connection.connected_at = timezone.now()
            connection.meter_number = meter_number
            
            # Send SMS: Electricity Connected
            applicant = connection.application.applicant
            if applicant.phone_number:
                message = (
                    f"Great news! Electricity has been connected to your housing unit. "
                    f"Meter Number: {meter_number}. "
                    f"Reference: {applicant.reference_number}"
                )
                send_sms(applicant.phone_number, message, 'electricity_connected', applicant=applicant)
                
        elif new_status == 'issues':
            connection.issue_description = issue_description
        
        connection.save()
        
        return JsonResponse({
            'success': True,
            'new_status': new_status,
            'message': f'Electricity status updated from {old_status} to {new_status}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# UI #10: SUPPORTING SERVICES COORDINATOR (Day 5 Week 1)
# =============================================================================

@login_required
@verify_position
def supporting_services_coordinator(request, position):
    """
    UI #10: Supporting Services Coordinator Form
    Process 4: Approval Routing - Notarial & Engineering Tracking

    URL: /applications/<position>/supporting-services/

    Actor: Jocel (Fourth Member / Records Officer)
    Purpose: Track completion of notarial services and engineering assessment
             before forwarding application to signatory routing

    GET: Display applications needing services completion
    POST (AJAX): Mark service as complete
    """

    # Authorization: Fourth Member / Records Officer / Jocel only
    if request.user.position not in ['fourth_member']:
        return render(request, 'common/access_denied.html',
                      {'message': 'Only the Records Officer can access this function.'}, status=403)

    if request.method == 'POST':
        return process_service_completion(request)

    # GET: Show applications that need services
    applications = (
        Application.objects
        .filter(status='completed')  # After applicant sign, before routing
        .select_related('applicant')
        .order_by('-form_generated_at')
    )

    # Categorize by service completion status
    pending_notarial = applications.filter(notarial_completed=False)
    pending_engineering = applications.filter(engineering_completed=False)
    both_pending = applications.filter(notarial_completed=False, engineering_completed=False)

    # Ready to route (all services done)
    ready_to_route = applications.filter(notarial_completed=True, engineering_completed=True)

    context = {
        'applications': applications,
        'pending_notarial': pending_notarial,
        'pending_engineering': pending_engineering,
        'both_pending': both_pending,
        'ready_to_route': ready_to_route,
        'total_applications': applications.count(),
    }

    return render(request, 'applications/supporting_services.html', context)


@login_required
@verify_position
@require_POST
def process_service_completion(request, position):
    """
    Handle AJAX POST to mark notarial/engineering services as complete.

    URL: /applications/<position>/service/complete/

    Expected POST data:
    - application_id: Application ID
    - service_type: 'notarial' or 'engineering'
    - action: 'complete' or 'reset'
    """
    try:
        application_id = request.POST.get('application_id')
        service_type = request.POST.get('service_type')  # 'notarial' or 'engineering'
        action = request.POST.get('action', 'complete')  # 'complete' or 'reset'

        application = Application.objects.get(id=application_id)

        if service_type == 'notarial':
            if action == 'complete':
                application.notarial_completed = True
                application.notarial_completed_at = timezone.now()
                message = '✓ Notarial services marked as complete'
            else:
                application.notarial_completed = False
                application.notarial_completed_at = None
                message = '↺ Notarial services reset to pending'

        elif service_type == 'engineering':
            if action == 'complete':
                application.engineering_completed = True
                application.engineering_completed_at = timezone.now()
                message = '✓ Engineering assessment marked as complete'
            else:
                application.engineering_completed = False
                application.engineering_completed_at = None
                message = '↺ Engineering assessment reset to pending'

        else:
            return JsonResponse({'success': False, 'error': 'Invalid service type'})

        application.save()

        # Check if both services are complete
        both_complete = application.notarial_completed and application.engineering_completed

        return JsonResponse({
            'success': True,
            'message': message,
            'notarial_completed': application.notarial_completed,
            'engineering_completed': application.engineering_completed,
            'both_complete': both_complete,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M'),
        })

    except Application.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Application not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@verify_position
@require_POST
def send_to_signatory_routing(request, position):
    """
    Send application to signatory routing after all services are complete.

    URL: /applications/<position>/routing/send/

    Expected POST data:
    - application_id: Application ID to forward
    """
    try:
        application_id = request.POST.get('application_id')
        application = Application.objects.get(id=application_id)

        # Verify both services are complete
        if not application.notarial_completed or not application.engineering_completed:
            return JsonResponse({
                'success': False,
                'error': 'Both notarial and engineering services must be marked complete'
            })

        # Already handle routing in existing code, update status
        application.status = 'routing'
        application.save()

        # Create signatory routing records (if not exists)
        # Typically: OIC → Head
        SignatoryRouting.objects.get_or_create(
            application=application,
            signatory_role='oic',
            defaults={
                'order': 1,
                'forwarded_by': request.user,
                'forwarded_at': timezone.now(),
            }
        )

        SignatoryRouting.objects.get_or_create(
            application=application,
            signatory_role='head',
            defaults={
                'order': 2,
                'forwarded_by': request.user,
            }
        )

        # Send SMS to applicant
        applicant = application.applicant
        if applicant.phone_number:
            message = (
                f"📋 APPLICATION UPDATE\n"
                f"Your application ({application.application_number}) has been forwarded for final approval.\n"
                f"You will be notified once approved.\n"
                f"Thank you, Talisay Housing Authority"
            )
            send_sms(applicant.phone_number, message, 'sent_to_routing', applicant=applicant)

        return JsonResponse({
            'success': True,
            'message': f'Application {application.application_number} forwarded to signatory routing',
            'new_status': application.status,
        })

    except Application.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Application not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
