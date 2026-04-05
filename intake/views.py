from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Prefetch
from .models import LandownerSubmission, ISFRecord, Applicant, Barangay, QueueEntry, CDRRMOCertification
from .forms import (
    LandownerSubmissionForm, 
    ISFRecordForm, 
    ISFReviewForm,
    HouseholdMemberForm,
    WalkInApplicantForm
)
from .utils import check_blacklist, create_applicant_from_isf, send_sms
import json



def landowner_form(request):
    """
    Public form for landowners to submit ISF records.
    No login required - accessible to anyone.
    MINIMAL FORM: Only 6 fields (landowner name + address, ISF: name + household + income + years)
    """
    if request.method == 'POST':
        form = LandownerSubmissionForm(request.POST)
        
        if form.is_valid():
            # Get ISF data from JSON field
            isf_data_json = request.POST.get('isf_data', '[]')
            try:
                isf_records_data = json.loads(isf_data_json)
            except json.JSONDecodeError:
                messages.error(request, 'Invalid ISF data format.')
                return render(request, 'intake/landowner_form.html', {
                    'form': form,
                    'isf_form': ISFRecordForm(),
                })
            
            if not isf_records_data:
                messages.error(request, 'Please add at least one ISF record.')
                return render(request, 'intake/landowner_form.html', {
                    'form': form,
                    'isf_form': ISFRecordForm(),
                })
            
            # Create the submission
            submission = form.save()
            
            # Create ISF records (minimal - no phone yet)
            isf_records = []
            for isf_data in isf_records_data:
                isf_record = ISFRecord.objects.create(
                    submission=submission,
                    full_name=isf_data.get('full_name', '').strip(),
                    household_members=int(isf_data.get('household_members', 1)),
                    monthly_income=float(isf_data.get('monthly_income', 0)),
                    years_residing=int(isf_data.get('years_residing', 0)),
                    # Phone number NOT collected yet - Jocel will add during review
                )
                isf_records.append(isf_record)
            
            # Success - redirect to confirmation page
            return render(request, 'intake/submission_success.html', {
                'submission': submission,
                'isf_records': isf_records,
            })
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LandownerSubmissionForm()
    
    return render(request, 'intake/landowner_form.html', {
        'form': form,
        'isf_form': ISFRecordForm(),
    })




@login_required
def submission_review(request, submission_id):
    """
    Staff view: Review a specific landowner submission.
    
    ACCESS CONTROL - Hierarchical Model:
    ✅ Jocel (fourth_member) - Primary reviewer, adds phone numbers, runs eligibility
    ✅ Joie (second_member) - Supervisor/oversight, can review Jocel's work
    ✅ Victor (oic) - Management oversight
    ✅ Arthur (head) - Executive oversight
    """
    # Hierarchical access: Primary reviewer + Supervisor + Management
    if not request.user.position in ['fourth_member', 'second_member', 'oic', 'head']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    submission = get_object_or_404(
        LandownerSubmission.objects.prefetch_related('isf_records'),
        id=submission_id
    )
    
    # Mark as reviewed if first time opening
    if submission.status == 'pending':
        submission.status = 'reviewed'
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save()
    
    isf_records = submission.isf_records.all()
    
    return render(request, 'intake/staff/submission_review.html', {
        'submission': submission,
        'isf_records': isf_records,
    })


@login_required
def isf_review(request, isf_id):
    """
    Staff view: Review individual ISF record.
    
    ACCESS CONTROL - Hierarchical Model:
    ✅ Jocel (fourth_member) - Primary reviewer, performs eligibility checks
    ✅ Joie (second_member) - Supervisor/oversight, quality control
    ✅ Victor (oic) - Management oversight
    ✅ Arthur (head) - Executive oversight
    
    Benefits:
    - Quality control and cross-checking of eligibility decisions
    - Backup coverage when primary reviewer is unavailable
    - Management visibility into workload and decision-making
    """
    # Hierarchical access: Primary reviewer + Supervisor + Management
    if not request.user.position in ['fourth_member', 'second_member', 'oic', 'head']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    isf_record = get_object_or_404(ISFRecord, id=isf_id)
    
    # Check if already converted to applicant
    if isf_record.converted_to_applicant:
        messages.warning(request, 'This ISF has already been converted to an applicant profile.')
        return redirect('intake:submission_review', submission_id=isf_record.submission.id)
    
    if request.method == 'POST':
        form = ISFReviewForm(request.POST, instance=isf_record)
        
        if form.is_valid():
            # Check blacklist first
            is_blacklisted, blacklist_entry = check_blacklist(
                full_name=isf_record.full_name,
                phone_number=form.cleaned_data.get('phone_number')
            )
            
            if is_blacklisted:
                messages.error(request, f'⚠️ BLACKLISTED: {blacklist_entry.full_name} - Reason: {blacklist_entry.get_reason_display()}')
                isf_record.status = 'disqualified'
                isf_record.disqualification_reason = f'Blacklisted: {blacklist_entry.notes}'
                isf_record.eligibility_checked_by = request.user
                isf_record.eligibility_checked_at = timezone.now()
                isf_record.save()
                return redirect('intake:submission_review', submission_id=isf_record.submission.id)
            
            # Check property ownership
            has_property = form.cleaned_data.get('has_property_in_talisay')
            if has_property == 'yes':
                isf_record.status = 'disqualified'
                isf_record.disqualification_reason = 'Owns property in Talisay City'
                isf_record.phone_number = form.cleaned_data.get('phone_number', '')
                isf_record.eligibility_checked_by = request.user
                isf_record.eligibility_checked_at = timezone.now()
                isf_record.save()
                
                # Send disqualification SMS if phone provided
                if isf_record.phone_number:
                    isf_record.send_eligibility_sms(eligible=False)
                
                messages.warning(request, f'Marked as disqualified: {isf_record.full_name}')
                return redirect('intake:submission_review', submission_id=isf_record.submission.id)
            
            # Check income eligibility
            if not isf_record.is_income_eligible:
                isf_record.status = 'disqualified'
                isf_record.disqualification_reason = f'Monthly income (₱{isf_record.monthly_income}) exceeds ₱10,000 limit'
                isf_record.phone_number = form.cleaned_data.get('phone_number', '')
                isf_record.eligibility_checked_by = request.user
                isf_record.eligibility_checked_at = timezone.now()
                isf_record.save()
                
                if isf_record.phone_number:
                    isf_record.send_eligibility_sms(eligible=False)
                
                messages.warning(request, f'Marked as disqualified: {isf_record.full_name}')
                return redirect('intake:submission_review', submission_id=isf_record.submission.id)
            
            # ELIGIBLE - Save updates and convert to Applicant
            isf_record = form.save(commit=False)
            isf_record.eligibility_checked_by = request.user
            isf_record.eligibility_checked_at = timezone.now()
            isf_record.save()
            
            # Extract barangay
            barangay_name = form.cleaned_data.get('barangay')
            
            # Create Applicant profile and add to Priority Queue
            applicant = create_applicant_from_isf(isf_record, request.user)
            
            if applicant:
                # Update barangay if needed
                barangay, _ = Barangay.objects.get_or_create(name=barangay_name)
                applicant.barangay = barangay
                applicant.save()
                
                messages.success(request, f'✓ {isf_record.full_name} marked as ELIGIBLE and added to Priority Queue!')
            else:
                messages.error(request, 'Failed to create applicant profile. Please try again.')
            
            return redirect('intake:submission_review', submission_id=isf_record.submission.id)
    else:
        form = ISFReviewForm(instance=isf_record)
    
    return render(request, 'intake/staff/isf_review.html', {
        'isf_record': isf_record,
        'form': form,
        'submission': isf_record.submission,
    })


@login_required
def walkin_review(request, applicant_id):
    """
    Staff view: Review walk-in or danger zone applicant (Channel B/C).
    
    ACCESS CONTROL - Hierarchical Model:
    ✅ Jocel (fourth_member) - Primary reviewer, performs eligibility checks
    ✅ Joie (second_member) - Supervisor/oversight, quality control
    ✅ Victor (oic) - Management oversight
    ✅ Arthur (head) - Executive oversight
    """
    from .utils import send_sms
    from .models import QueueEntry
    
    # Hierarchical access: Primary reviewer + Supervisor + Management
    if not request.user.position in ['fourth_member', 'second_member', 'oic', 'head']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    # Get the applicant
    applicant = get_object_or_404(Applicant, id=applicant_id)
    
    # Only allow Channel B/C applicants
    if applicant.channel not in ['danger_zone', 'walk_in']:
        messages.error(request, 'This review page is for walk-in and danger zone applicants only.')
        return redirect('intake:applicants_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'eligible':
            # Mark as eligible
            applicant.status = 'eligible'
            applicant.eligibility_checked_by = request.user
            applicant.eligibility_checked_at = timezone.now()
            applicant.save()
            
            # Determine queue type based on channel
            queue_type = 'priority' if applicant.channel == 'danger_zone' else 'walk_in'
            
            # Get next position in appropriate queue
            last_position = QueueEntry.objects.filter(
                queue_type=queue_type,
                status='active'
            ).order_by('-position').first()
            
            next_position = (last_position.position + 1) if last_position else 1
            
            # Add to queue
            QueueEntry.objects.create(
                applicant=applicant,
                queue_type=queue_type,
                position=next_position,
                status='active',
                added_by=request.user
            )
            
            # Send SMS notification
            if applicant.phone_number:
                message = f"You passed eligibility. Please visit the Talisay Housing Authority office to submit your 7 requirements. Reference: {applicant.reference_number}"
                send_sms(applicant.phone_number, message, 'eligibility_passed', applicant=applicant)
            
            messages.success(request, f'✓ {applicant.full_name} marked as ELIGIBLE and added to {queue_type.replace("_", " ").title()} Queue!')
            return redirect('intake:applicants_list')
            
        elif action == 'disqualify':
            reason = request.POST.get('disqualification_reason', '')
            applicant.status = 'disqualified'
            applicant.disqualification_reason = reason
            applicant.eligibility_checked_by = request.user
            applicant.eligibility_checked_at = timezone.now()
            applicant.save()
            
            # Send SMS notification
            if applicant.phone_number:
                message = f"Your housing application could not be processed. Reason: {reason or 'See office for details'}. Reference: {applicant.reference_number}"
                send_sms(applicant.phone_number, message, 'eligibility_failed', applicant=applicant)
            
            messages.warning(request, f'✕ {applicant.full_name} marked as DISQUALIFIED.')
            return redirect('intake:applicants_list')
    
    # Get barangays for dropdown
    barangays = Barangay.objects.all().order_by('name')
    
    return render(request, 'intake/staff/walkin_review.html', {
        'applicant': applicant,
        'barangays': barangays,
    })


@login_required
def walkin_register(request):
    """
    Staff view: Register applicants from all channels.
    
    Channel A: Landowner walk-in → Creates LandownerSubmission + ISFRecords → Priority Queue
    Channel B: Danger Zone Walk-in → Pending CDRRMO certification → Priority Queue
    Channel C: Regular Walk-in → Direct eligibility check → Walk-in FIFO Queue
    
    ACCESS CONTROL:
    ✅ Jay (third_member) - Primary registration (census/field verification)
    ✅ Jocel (fourth_member) - Registration backup
    ✅ Paul/Roberto (field) - Field registration
    ✅ Joie (second_member) - Supervisor oversight
    """
    allowed_positions = ['third_member', 'fourth_member', 'field', 'second_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'You do not have permission to register applicants.')
        return redirect('accounts:dashboard')
    
    barangays = Barangay.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        channel = request.POST.get('channel', 'walk_in')
        
        # ====== CHANNEL A: Landowner Walk-in ======
        if channel == 'landowner':
            landowner_name = request.POST.get('landowner_name', '').strip()
            landowner_email = request.POST.get('landowner_email', '').strip()
            landowner_phone = request.POST.get('landowner_phone', '').strip()
            property_address = request.POST.get('property_address', '').strip()
            
            # Get ISF data from form arrays
            isf_names = request.POST.getlist('isf_name[]')
            isf_incomes = request.POST.getlist('isf_income[]')
            isf_households = request.POST.getlist('isf_household[]')
            isf_years = request.POST.getlist('isf_years[]')
            
            # Validation
            if not landowner_name:
                messages.error(request, 'Landowner name is required.')
                return redirect('intake:applicants_list')
            
            if not property_address:
                messages.error(request, 'Property address is required.')
                return redirect('intake:applicants_list')
            
            # Filter out empty ISF entries
            valid_isfs = []
            for i, name in enumerate(isf_names):
                if name and name.strip():
                    try:
                        income = float(isf_incomes[i]) if i < len(isf_incomes) and isf_incomes[i] else 0
                    except (ValueError, TypeError):
                        income = 0
                    try:
                        household = int(isf_households[i]) if i < len(isf_households) and isf_households[i] else 1
                    except (ValueError, TypeError):
                        household = 1
                    try:
                        years = int(isf_years[i]) if i < len(isf_years) and isf_years[i] else 0
                    except (ValueError, TypeError):
                        years = 0
                    
                    valid_isfs.append({
                        'name': name.strip(),
                        'income': income,
                        'household': household,
                        'years': years
                    })
            
            if not valid_isfs:
                messages.error(request, 'At least one ISF record is required.')
                return redirect('intake:applicants_list')
            
            # Create landowner submission
            submission = LandownerSubmission.objects.create(
                landowner_name=landowner_name,
                landowner_email=landowner_email or None,
                landowner_phone=landowner_phone or None,
                property_address=property_address,
                status='pending',
                submitted_by_staff=request.user,
            )
            
            # Create ISF records
            created_count = 0
            blacklisted_count = 0
            for isf in valid_isfs:
                # Check blacklist
                is_blacklisted, _ = check_blacklist(isf['name'], '')
                
                if is_blacklisted:
                    blacklisted_count += 1
                    continue
                
                ISFRecord.objects.create(
                    submission=submission,
                    full_name=isf['name'],
                    monthly_income=isf['income'],
                    household_member_count=isf['household'],
                    years_residing=isf['years'],
                    status='pending',
                )
                created_count += 1
            
            # Send SMS to landowner
            if landowner_phone:
                message = f"Your ISF submission has been received. Reference: {submission.reference_number}. {created_count} ISF records registered."
                send_sms(landowner_phone, message, 'registration')
            
            if blacklisted_count > 0:
                messages.warning(
                    request,
                    f'✓ Landowner submission created. {created_count} ISF records registered. '
                    f'{blacklisted_count} blacklisted applicants skipped. Reference: {submission.reference_number}'
                )
            else:
                messages.success(
                    request,
                    f'✓ Landowner submission created with {created_count} ISF records. '
                    f'Reference: {submission.reference_number}'
                )
            
            return redirect('intake:applicants_list')
        
        # ====== CHANNEL B & C: Walk-in Applicants ======
        form = WalkInApplicantForm(request.POST)
        
        if form.is_valid():
            # Get barangay instance
            barangay_name = form.cleaned_data['barangay']
            barangay, _ = Barangay.objects.get_or_create(name=barangay_name)
            
            # Check blacklist before proceeding
            full_name = form.cleaned_data['full_name']
            phone_number = form.cleaned_data.get('phone_number', '')
            is_blacklisted, blacklist_entry = check_blacklist(full_name, phone_number)
            
            if is_blacklisted:
                messages.error(
                    request,
                    f'⚠️ BLACKLISTED: {full_name} is on the blacklist. '
                    f'Reason: {blacklist_entry.get_reason_display()}. Registration denied.'
                )
                return redirect('intake:applicants_list')
            
            # Create applicant
            channel = form.cleaned_data['channel']
            applicant = Applicant.objects.create(
                full_name=full_name,
                phone_number=phone_number,
                barangay=barangay,
                current_address=form.cleaned_data['current_address'],
                monthly_income=form.cleaned_data['monthly_income'],
                years_residing=form.cleaned_data['years_residing'],
                channel=channel,
                status='pending_cdrrmo' if channel == 'danger_zone' else 'pending',
                registered_by=request.user,
            )
            
            # For Channel B (danger zone), create CDRRMO certification request
            if channel == 'danger_zone':
                danger_zone_type = form.cleaned_data.get('danger_zone_type', '')
                danger_zone_location = form.cleaned_data.get('danger_zone_location', '')
                
                CDRRMOCertification.objects.create(
                    applicant=applicant,
                    declared_location=f"{dict(form.fields['danger_zone_type'].choices).get(danger_zone_type, danger_zone_type)}: {danger_zone_location}",
                    status='pending',
                    requested_by=request.user,
                )
                
                messages.success(
                    request,
                    f'✓ {applicant.full_name} registered as DANGER ZONE applicant. '
                    f'Reference: {applicant.reference_number}. Awaiting CDRRMO certification.'
                )
            else:
                messages.success(
                    request,
                    f'✓ {applicant.full_name} registered as WALK-IN applicant. '
                    f'Reference: {applicant.reference_number}. Ready for eligibility review.'
                )
            
            # Send SMS confirmation
            if phone_number:
                message = f"You have been registered for housing assistance. Reference: {applicant.reference_number}. Please keep this for follow-up."
                send_sms(phone_number, message, 'registration', applicant=applicant)
            
            return redirect('intake:applicants_list')
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            return redirect('intake:applicants_list')
    
    # GET request - render standalone form
    form = WalkInApplicantForm()
    return render(request, 'intake/staff/walkin_register.html', {
        'form': form,
        'barangays': barangays,
    })


@login_required
def update_eligibility(request):
    """
    AJAX endpoint to update applicant eligibility status.
    Used by the review modal for marking eligible or disqualifying applicants.
    
    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Primary eligibility checker
    ✅ Joie (second_member) - Supervisor oversight
    ✅ Victor (oic) - OIC override
    """
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    allowed_positions = ['fourth_member', 'second_member', 'oic', 'head']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    applicant_id = request.POST.get('applicant_id')
    action = request.POST.get('action')
    
    if not applicant_id or not action:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id or action'})
    
    try:
        applicant = Applicant.objects.get(id=applicant_id)
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    
    if action == 'mark_eligible':
        # Check eligibility criteria
        if applicant.monthly_income > 10000:
            return JsonResponse({
                'success': False, 
                'error': f'Income ₱{applicant.monthly_income:,.2f} exceeds ₱10,000 limit'
            })
        
        # For Channel B, check CDRRMO certification
        if applicant.channel == 'danger_zone':
            try:
                cert = applicant.cdrrmo_certification
                if cert.status != 'certified':
                    return JsonResponse({
                        'success': False,
                        'error': 'CDRRMO certification required for danger zone applicants'
                    })
            except CDRRMOCertification.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'CDRRMO certification not found'
                })
        
        # Mark as eligible
        applicant.status = 'eligible'
        applicant.eligibility_checked_by = request.user
        applicant.eligibility_checked_at = timezone.now()
        applicant.save()
        
        # Add to appropriate queue
        queue_type = 'priority' if applicant.channel in ['landowner', 'danger_zone'] else 'walk_in'
        
        # Get next position in queue
        last_position = QueueEntry.objects.filter(
            queue_type=queue_type,
            status='active'
        ).order_by('-position').values_list('position', flat=True).first() or 0
        
        QueueEntry.objects.create(
            applicant=applicant,
            queue_type=queue_type,
            position=last_position + 1,
            status='active',
            added_by=request.user,
        )
        
        # Send SMS notification
        if applicant.phone_number:
            queue_name = 'Priority Queue' if queue_type == 'priority' else 'Walk-in Queue'
            message = f"Congratulations! You are ELIGIBLE for housing assistance. You are now in the {queue_name} (Position #{last_position + 1}). Reference: {applicant.reference_number}"
            send_sms(applicant.phone_number, message, 'eligibility', applicant=applicant)
        
        return JsonResponse({
            'success': True,
            'message': f'Marked as eligible. Added to {queue_type.replace("_", "-").title()} Queue at position #{last_position + 1}'
        })
    
    elif action == 'disqualify':
        reason = request.POST.get('reason', '')
        notes = request.POST.get('notes', '')
        
        reason_labels = {
            'income_exceeds': 'Income exceeds ₱10,000 limit',
            'property_owner': 'Owns property in Talisay City',
            'blacklisted': 'On blacklist',
            'incomplete_docs': 'Incomplete documents',
            'false_info': 'False information provided',
            'other': notes or 'Other reason'
        }
        
        applicant.status = 'disqualified'
        applicant.disqualification_reason = reason_labels.get(reason, reason)
        applicant.eligibility_checked_by = request.user
        applicant.eligibility_checked_at = timezone.now()
        applicant.save()
        
        # Send SMS notification
        if applicant.phone_number:
            message = f"We regret to inform you that your housing application has been DISQUALIFIED. Reason: {applicant.disqualification_reason}. Reference: {applicant.reference_number}. Please visit THA office for more information."
            send_sms(applicant.phone_number, message, 'eligibility', applicant=applicant)
        
        return JsonResponse({
            'success': True,
            'message': f'Applicant disqualified. Reason: {applicant.disqualification_reason}'
        })
    
    return JsonResponse({'success': False, 'error': f'Unknown action: {action}'})


@login_required
def applicants_list(request):
    """
    Module 1: ISF Recording Management - Applicant Intake
    Accessible to: Second Member (Joie), Fourth Member (Jocel)
    Unified view for all applicant intake channels:
    
    Channel A (Landowner Portal) → Shows pending ISFRecords from LandownerSubmissions
    Channel B (Danger Zone) → Shows Applicants with channel='danger_zone'
    Channel C (Walk-in) → Shows Applicants with channel='walk_in'
    
    Displays in FIFO order (oldest first by registration date).
    """
    allowed_positions = ['second_member', 'fourth_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. This module is for Second and Fourth Members only.')
        return redirect('accounts:dashboard')
    
    # Build unified applicants list from multiple sources
    applicants = []
    
    # ====== CHANNEL A: Landowner Submissions (ISF Records) ======
    # Get all ISF records with pending or reviewed status
    isf_records = ISFRecord.objects.select_related(
        'submission', 'eligibility_checked_by'
    ).order_by('created_at')
    
    for isf in isf_records:
        # Determine eligibility status display
        if isf.status == 'pending':
            eligibility_status = 'Pending'
        elif isf.status == 'eligible':
            eligibility_status = 'Eligible'
        else:
            eligibility_status = 'Disqualified'
        
        # Get queue info if converted to applicant
        queue_type = 'None'
        queue_position = None
        if isf.converted_to_applicant:
            try:
                applicant_profile = isf.applicant_profile
                queue_entry = QueueEntry.objects.filter(
                    applicant=applicant_profile,
                    status='active'
                ).first()
                if queue_entry:
                    queue_type = 'Priority' if queue_entry.queue_type == 'priority' else 'Walk-in'
                    queue_position = queue_entry.position
            except:
                pass
        
        applicants.append({
            'id': str(isf.id),
            'fullName': isf.full_name,
            'referenceNumber': isf.reference_number,
            'dateRegistered': isf.created_at.strftime('%Y-%m-%d'),
            'dateTime': isf.created_at.strftime('%Y-%m-%d %I:%M %p'),
            'channel': 'A',
            'submissionId': str(isf.submission.id),  # For Channel A review
            'applicantId': None,
            'barangay': isf.submission.barangay,
            'monthlyIncome': float(isf.monthly_income),
            'householdSize': isf.household_members,
            'yearsResiding': isf.years_residing,
            'eligibilityStatus': eligibility_status,
            'queueType': queue_type,
            'queuePosition': queue_position,
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': isf.disqualification_reason or None,
        })
    
    # ====== CHANNEL B & C: Walk-in Applicants ======
    # Get all direct applicants (Channel B: danger_zone, Channel C: walk_in)
    walk_in_applicants = Applicant.objects.filter(
        channel__in=['danger_zone', 'walk_in']
    ).select_related('barangay', 'eligibility_checked_by').prefetch_related(
        Prefetch(
            'queue_entries',
            queryset=QueueEntry.objects.filter(status='active'),
            to_attr='active_queue'
        )
    ).order_by('created_at')
    
    for app in walk_in_applicants:
        # Determine eligibility status display
        if app.status == 'pending':
            eligibility_status = 'Pending'
        elif app.status == 'pending_cdrrmo':
            eligibility_status = 'Pending CDRRMO'
        elif app.status == 'eligible':
            eligibility_status = 'Eligible'
        elif app.status == 'disqualified':
            eligibility_status = 'Disqualified'
        else:
            eligibility_status = app.get_status_display()
        
        # Get queue info
        queue_type = 'None'
        queue_position = None
        if app.active_queue:
            queue_entry = app.active_queue[0]
            queue_type = 'Priority' if queue_entry.queue_type == 'priority' else 'Walk-in'
            queue_position = queue_entry.position
        
        # Get CDRRMO status for Channel B
        cdrrmo_status = None
        danger_zone_type = None
        is_cdrrmo_flagged = False
        if app.channel == 'danger_zone':
            try:
                cert = app.cdrrmo_certification
                cdrrmo_status = cert.get_status_display()
                danger_zone_type = cert.declared_location
                is_cdrrmo_flagged = cert.status == 'pending' and cert.is_overdue
            except CDRRMOCertification.DoesNotExist:
                cdrrmo_status = 'Not Requested'
        
        applicants.append({
            'id': str(app.id),
            'fullName': app.full_name,
            'referenceNumber': app.reference_number,
            'dateRegistered': app.created_at.strftime('%Y-%m-%d'),
            'dateTime': app.created_at.strftime('%Y-%m-%d %I:%M %p'),
            'channel': 'B' if app.channel == 'danger_zone' else 'C',
            'submissionId': None,
            'applicantId': str(app.id),  # For Channel B/C review
            'barangay': app.barangay.name if app.barangay else 'Unknown',
            'monthlyIncome': float(app.monthly_income),
            'householdSize': app.household_member_count,
            'yearsResiding': app.years_residing,
            'eligibilityStatus': eligibility_status,
            'queueType': queue_type,
            'queuePosition': queue_position,
            'cdrrmoStatus': cdrrmo_status,
            'dangerZoneType': danger_zone_type,
            'isCdrrmoFlagged': is_cdrrmo_flagged,
            'signatoryRoutingDelayed': False,  # TODO: Link to Module 2
            'disqualificationReason': app.disqualification_reason or None,
        })
    
    # Sort all applicants by dateRegistered (FIFO - oldest first)
    applicants.sort(key=lambda x: x['dateRegistered'])
    
    # Get barangays from database
    barangays = list(Barangay.objects.filter(is_active=True).values_list('name', flat=True).order_by('name'))
    
    # Calculate stats
    total_applicants = len(applicants)
    priority_count = len([a for a in applicants if a['queueType'] == 'Priority'])
    walkin_count = len([a for a in applicants if a['queueType'] == 'Walk-in'])
    pending_cdrrmo = len([a for a in applicants if a.get('cdrrmoStatus') == 'Pending CDRRMO Visit'])
    
    context = {
        'page_title': 'ISF Recording Management',
        'user_position': request.user.position,
        'applicants': applicants,
        'applicants_json': json.dumps(applicants),
        'barangays': barangays,
        'stats': {
            'total': total_applicants,
            'priority': priority_count,
            'walkin': walkin_count,
            'pending_cdrrmo': pending_cdrrmo
        }
    }
    
    return render(request, 'intake/staff/applicants.html', context)
