from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Prefetch, Max
from django.utils import timezone
from intake.models import Applicant
from .models import Application, Requirement, RequirementSubmission, SignatoryRouting


@login_required
def applications_list(request):
    """
    Module 2 - Housing Application & Evaluation
    Shows eligible applicants with document checklist progress, signatory routing, etc.
    """
    # Get all eligible applicants (status='eligible' or beyond in the workflow)
    applicants = Applicant.objects.filter(
        status__in=['eligible', 'requirements', 'application', 'standby', 'awarded']
    ).select_related('application').prefetch_related(
        'requirement_submissions',
        'requirement_submissions__requirement',
        Prefetch(
            'application__routing_steps',
            queryset=SignatoryRouting.objects.order_by('action_at')
        )
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
        if application:
            latest_routing = application.routing_steps.last()
            if latest_routing:
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
        
        applicants_data.append({
            'applicant': applicant,
            'application': application,
            'group_a_verified': group_a_verified,
            'can_generate_form': can_generate_form,
            'form_generated': application.status != 'draft' if application else False,
            'current_stage': current_stage,
            'routing_status': routing_status,
            'is_delayed': is_delayed,
            'delayed_at': delayed_at,
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
    }
    
    return render(request, 'applications/applications_list.html', context)


@login_required
def application_detail(request, application_id):
    """Get application detail for modal (AJAX)."""
    application = get_object_or_404(
        Application.objects.select_related('applicant').prefetch_related(
            'routing_steps',
            'applicant__requirement_submissions',
            'applicant__requirement_submissions__requirement'
        ),
        id=application_id
    )
    
    # Build response data
    data = {
        'id': str(application.id),
        'application_number': application.application_number,
        'applicant_name': application.applicant.full_name,
        'reference_number': application.applicant.reference_number,
        'status': application.status,
        'status_display': application.get_status_display(),
        'requirements': [],
        'routing_steps': [],
    }
    
    # Add requirements status
    for submission in application.applicant.requirement_submissions.all():
        data['requirements'].append({
            'code': submission.requirement.code,
            'name': submission.requirement.name,
            'group': submission.requirement.group,
            'status': submission.status,
            'verified': submission.status == 'verified',
        })
    
    # Add routing steps
    for step in application.routing_steps.all():
        data['routing_steps'].append({
            'step': step.step,
            'step_display': step.get_step_display(),
            'action_at': step.action_at.strftime('%Y-%m-%d %H:%M'),
            'is_delayed': step.is_delayed,
            'days_since': step.days_since_action,
        })
    
    return JsonResponse(data)


@login_required
@require_POST
def update_requirement(request):
    """Update requirement submission status (AJAX)."""
    applicant_id = request.POST.get('applicant_id')
    requirement_code = request.POST.get('requirement_code')
    status = request.POST.get('status')
    
    try:
        applicant = Applicant.objects.get(id=applicant_id)
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
            submission.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def generate_form(request, applicant_id):
    """Generate application form for applicant."""
    applicant = get_object_or_404(Applicant, id=applicant_id)
    
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
    
    return JsonResponse({
        'success': True,
        'application_number': application.application_number
    })


@login_required
@require_POST
def update_routing(request):
    """Update signatory routing step (AJAX)."""
    application_id = request.POST.get('application_id')
    step = request.POST.get('step')
    
    try:
        application = Application.objects.get(id=application_id)
        
        # Create routing step
        SignatoryRouting.objects.create(
            application=application,
            step=step,
            action_by=request.user
        )
        
        # Update application status based on step
        if step == 'signed_head':
            application.status = 'head_signed'
            application.fully_approved_at = timezone.now()
        elif step == 'signed_oic':
            application.status = 'oic_signed'
        elif step in ['received', 'forwarded_oic', 'forwarded_head']:
            application.status = 'routing'
        
        application.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def update_stage(request):
    """Update application stage (AJAX)."""
    application_id = request.POST.get('application_id')
    new_status = request.POST.get('status')
    
    try:
        application = Application.objects.get(id=application_id)
        application.status = new_status
        
        if new_status == 'standby':
            application.standby_entered_at = timezone.now()
            # Calculate standby position
            last_position = Application.objects.filter(
                status='standby'
            ).exclude(id=application.id).aggregate(
                max_pos=Max('standby_position')
            )['max_pos'] or 0
            application.standby_position = last_position + 1
        
        application.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

