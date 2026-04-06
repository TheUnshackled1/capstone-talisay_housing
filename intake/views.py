from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
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
    Enhanced form: landowner name, phone, email, address, barangay + ISF data
    """
    # Get barangay list for template dropdown
    from .forms import BARANGAY_CHOICES
    barangays = [b[0] for b in BARANGAY_CHOICES if b[0]]  # Exclude empty choice
    
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
                    'barangays': barangays,
                })
            
            if not isf_records_data:
                messages.error(request, 'Please add at least one ISF record.')
                return render(request, 'intake/landowner_form.html', {
                    'form': form,
                    'isf_form': ISFRecordForm(),
                    'barangays': barangays,
                })
            
            # Create the submission with barangay from form
            submission = form.save(commit=False)
            submission.barangay = request.POST.get('barangay', '')
            submission.save()
            
            # Create ISF records with phone and barangay
            isf_records = []
            for isf_data in isf_records_data:
                isf_record = ISFRecord.objects.create(
                    submission=submission,
                    full_name=isf_data.get('full_name', '').strip(),
                    phone_number=isf_data.get('phone_number', '').strip(),
                    barangay=isf_data.get('barangay', '').strip() or submission.barangay,
                    household_members=int(isf_data.get('household_members', 1)),
                    monthly_income=float(isf_data.get('monthly_income', 0)),
                    years_residing=int(isf_data.get('years_residing', 0)),
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
        'barangays': barangays,
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
            danger_zone_type = form.cleaned_data.get('danger_zone_type', '') if channel == 'danger_zone' else ''
            danger_zone_location = form.cleaned_data.get('danger_zone_location', '') if channel == 'danger_zone' else ''
            
            # Get document checklist values from form
            doc_brgy_residency = request.POST.get('doc_brgy_residency') == 'true'
            doc_brgy_indigency = request.POST.get('doc_brgy_indigency') == 'true'
            doc_cedula = request.POST.get('doc_cedula') == 'true'
            doc_police_clearance = request.POST.get('doc_police_clearance') == 'true'
            doc_no_property = request.POST.get('doc_no_property') == 'true'
            doc_2x2_picture = request.POST.get('doc_2x2_picture') == 'true'
            doc_sketch_location = request.POST.get('doc_sketch_location') == 'true'
            
            applicant = Applicant.objects.create(
                full_name=full_name,
                phone_number=phone_number,
                barangay=barangay,
                current_address=form.cleaned_data['current_address'],
                monthly_income=form.cleaned_data['monthly_income'],
                household_size=form.cleaned_data.get('household_size', 1) or 1,
                years_residing=form.cleaned_data['years_residing'],
                channel=channel,
                status='pending_cdrrmo' if channel == 'danger_zone' else 'pending',
                danger_zone_type=danger_zone_type,
                danger_zone_location=danger_zone_location,
                registered_by=request.user,
                doc_brgy_residency=doc_brgy_residency,
                doc_brgy_indigency=doc_brgy_indigency,
                doc_cedula=doc_cedula,
                doc_police_clearance=doc_police_clearance,
                doc_no_property=doc_no_property,
                doc_2x2_picture=doc_2x2_picture,
                doc_sketch_location=doc_sketch_location,
            )
            
            # For Channel B (danger zone), create CDRRMO certification request
            if channel == 'danger_zone':
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
    channel = request.POST.get('channel', '')
    
    if not applicant_id or not action:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id or action'})
    
    # Handle Channel A (ISFRecord) separately
    if channel == 'A':
        try:
            isf = ISFRecord.objects.get(id=applicant_id)
        except ISFRecord.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'ISF record not found'})
        
        if action == 'mark_eligible':
            # Check eligibility criteria
            if isf.monthly_income > 10000:
                return JsonResponse({
                    'success': False, 
                    'error': f'Income ₱{isf.monthly_income:,.2f} exceeds ₱10,000 limit'
                })
            
            # Mark ISF as eligible
            isf.status = 'eligible'
            isf.eligibility_checked_by = request.user
            isf.eligibility_checked_at = timezone.now()
            isf.save()
            
            # Create/convert to Applicant and add to Priority Queue
            if not isf.converted_to_applicant:
                applicant = Applicant.objects.create(
                    full_name=isf.full_name,
                    phone_number=isf.phone_number or '',
                    barangay=isf.barangay,
                    monthly_income=isf.monthly_income,
                    household_size=isf.household_members,
                    years_residing=isf.years_residing,
                    channel='landowner',
                    status='eligible',
                    reference_number=isf.reference_number,
                    eligibility_checked_by=request.user,
                    eligibility_checked_at=timezone.now()
                )
                isf.converted_to_applicant = True
                isf.applicant_profile = applicant
                isf.save()
                
                # Add to Priority Queue
                last_position = QueueEntry.objects.filter(
                    queue_type='priority',
                    status='active'
                ).order_by('-position').values_list('position', flat=True).first() or 0
                
                QueueEntry.objects.create(
                    applicant=applicant,
                    queue_type='priority',
                    position=last_position + 1,
                    status='active',
                    added_by=request.user,
                )
                
                # Send SMS if phone number available
                if applicant.phone_number:
                    message = f"Congratulations! You are ELIGIBLE for housing assistance. You are now in the Priority Queue (Position #{last_position + 1}). Reference: {applicant.reference_number}"
                    send_sms(applicant.phone_number, message, 'eligibility', applicant=applicant)
                
                return JsonResponse({
                    'success': True,
                    'message': f'ISF marked as eligible. Added to Priority Queue at position #{last_position + 1}'
                })
            
            return JsonResponse({
                'success': True,
                'message': 'ISF already converted to applicant'
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
            
            isf.status = 'disqualified'
            isf.disqualification_reason = reason_labels.get(reason, reason)
            isf.eligibility_checked_by = request.user
            isf.eligibility_checked_at = timezone.now()
            isf.save()
            
            # Send SMS if phone available
            if isf.phone_number:
                message = f"We regret to inform you that your housing application has been DISQUALIFIED. Reason: {isf.disqualification_reason}. Reference: {isf.reference_number}. Please visit THA office for more information."
                send_sms(isf.phone_number, message, 'eligibility')
            
            return JsonResponse({
                'success': True,
                'message': f'ISF disqualified. Reason: {isf.disqualification_reason}'
            })
        
        return JsonResponse({'success': False, 'error': f'Unknown action: {action}'})
    
    # Channel B/C: Handle Applicant
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
def update_applicant(request):
    """
    AJAX endpoint to update applicant data (edit mode in review modal).
    Handles both Channel A (ISF records) and Channel B/C (Applicants).
    
    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Primary data editor
    ✅ Joie (second_member) - Supervisor oversight
    """
    from django.http import JsonResponse
    from decimal import Decimal
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    allowed_positions = ['fourth_member', 'second_member', 'oic', 'head']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    applicant_id = request.POST.get('applicant_id')
    channel = request.POST.get('channel')
    action = request.POST.get('action', 'update')
    
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id'})
    
    # Document field mapping
    doc_fields = [
        'doc_brgy_residency', 'doc_brgy_indigency', 'doc_cedula',
        'doc_police_clearance', 'doc_no_property', 'doc_2x2_picture', 'doc_sketch_location'
    ]
    
    try:
        # Handle single document update (auto-save)
        if action == 'update_doc':
            if channel == 'A':
                isf = ISFRecord.objects.get(id=applicant_id)
                for field in doc_fields:
                    if field in request.POST:
                        setattr(isf, field, request.POST.get(field) == 'true')
                isf.save()
                return JsonResponse({'success': True, 'message': 'Document status updated'})
            else:
                applicant = Applicant.objects.get(id=applicant_id)
                for field in doc_fields:
                    if field in request.POST:
                        setattr(applicant, field, request.POST.get(field) == 'true')
                applicant.save()
                return JsonResponse({'success': True, 'message': 'Document status updated'})
        
        if channel == 'A':
            # Update Channel A: ISF Record
            isf = ISFRecord.objects.get(id=applicant_id)
            
            # Update ISF fields
            isf_name = request.POST.get('isf_name', '').strip()
            isf_income = request.POST.get('isf_income')
            isf_household = request.POST.get('isf_household')
            isf_years = request.POST.get('isf_years')
            isf_barangay = request.POST.get('isf_barangay', '').strip()
            
            if isf_name:
                isf.full_name = isf_name
            if isf_income:
                isf.monthly_income = Decimal(isf_income)
            if isf_household:
                isf.household_members = int(isf_household)
            if isf_years:
                isf.years_residing = int(isf_years)
            if isf_barangay:
                # ISFRecord.barangay is a CharField, just assign the string value
                isf.barangay = isf_barangay
            
            # Update document checklist
            isf.doc_brgy_residency = request.POST.get('doc_brgy_residency') == 'true'
            isf.doc_brgy_indigency = request.POST.get('doc_brgy_indigency') == 'true'
            isf.doc_cedula = request.POST.get('doc_cedula') == 'true'
            isf.doc_police_clearance = request.POST.get('doc_police_clearance') == 'true'
            isf.doc_no_property = request.POST.get('doc_no_property') == 'true'
            isf.doc_2x2_picture = request.POST.get('doc_2x2_picture') == 'true'
            isf.doc_sketch_location = request.POST.get('doc_sketch_location') == 'true'
            
            isf.save()
            
            # Also update landowner info if provided
            submission_id = request.POST.get('submission_id')
            if submission_id:
                try:
                    submission = LandownerSubmission.objects.get(id=submission_id)
                    lo_name = request.POST.get('landowner_name', '').strip()
                    lo_phone = request.POST.get('landowner_phone', '').strip()
                    prop_addr = request.POST.get('property_address', '').strip()
                    sub_barangay = request.POST.get('submission_barangay', '').strip()
                    
                    if lo_name:
                        submission.landowner_name = lo_name
                    if lo_phone:
                        submission.landowner_phone = lo_phone
                    if prop_addr:
                        submission.property_address = prop_addr
                    if sub_barangay:
                        submission.barangay = sub_barangay
                    
                    submission.save()
                except LandownerSubmission.DoesNotExist:
                    pass
            
            return JsonResponse({
                'success': True,
                'message': 'ISF record updated successfully'
            })
        
        else:
            # Update Channel B/C: Applicant
            applicant = Applicant.objects.get(id=applicant_id)
            
            full_name = request.POST.get('full_name', '').strip()
            barangay_name = request.POST.get('barangay', '').strip()
            monthly_income = request.POST.get('monthly_income')
            household_size = request.POST.get('household_size')
            years_residing = request.POST.get('years_residing')
            phone_number = request.POST.get('phone_number', '').strip()
            current_address = request.POST.get('current_address', '').strip()
            
            if full_name:
                applicant.full_name = full_name
            if barangay_name:
                try:
                    brgy = Barangay.objects.get(name=barangay_name)
                    applicant.barangay = brgy
                except Barangay.DoesNotExist:
                    pass
            if monthly_income:
                applicant.monthly_income = Decimal(monthly_income)
            if household_size:
                applicant.household_size = int(household_size)
            if years_residing:
                applicant.years_residing = int(years_residing)
            if phone_number:
                applicant.phone_number = phone_number
            if current_address:
                applicant.current_address = current_address
            
            # Channel B specific: Danger zone fields
            if channel == 'B':
                danger_zone_type = request.POST.get('danger_zone_type', '').strip()
                danger_zone_location = request.POST.get('danger_zone_location', '').strip()
                cdrrmo_status = request.POST.get('cdrrmo_status', '').strip()
                cdrrmo_notes = request.POST.get('cdrrmo_notes', '').strip()
                
                if danger_zone_type:
                    applicant.danger_zone_type = danger_zone_type
                if danger_zone_location:
                    applicant.danger_zone_location = danger_zone_location
                
                # Update CDRRMO certification status
                if cdrrmo_status and cdrrmo_status in ['certified', 'not_certified']:
                    try:
                        cert = applicant.cdrrmo_certification
                        cert.status = cdrrmo_status
                        cert.result_recorded_by = request.user
                        cert.certified_at = timezone.now()
                        if cdrrmo_notes:
                            cert.certification_notes = cdrrmo_notes
                        cert.save()
                        
                        # Update applicant status based on CDRRMO result
                        if cdrrmo_status == 'certified':
                            applicant.status = 'pending'  # Ready for eligibility check
                        elif cdrrmo_status == 'not_certified':
                            applicant.status = 'pending'  # Move to walk-in queue instead
                            applicant.channel = 'walk_in'  # Downgrade to regular walk-in
                    except CDRRMOCertification.DoesNotExist:
                        pass
            
            # Update document checklist
            applicant.doc_brgy_residency = request.POST.get('doc_brgy_residency') == 'true'
            applicant.doc_brgy_indigency = request.POST.get('doc_brgy_indigency') == 'true'
            applicant.doc_cedula = request.POST.get('doc_cedula') == 'true'
            applicant.doc_police_clearance = request.POST.get('doc_police_clearance') == 'true'
            applicant.doc_no_property = request.POST.get('doc_no_property') == 'true'
            applicant.doc_2x2_picture = request.POST.get('doc_2x2_picture') == 'true'
            applicant.doc_sketch_location = request.POST.get('doc_sketch_location') == 'true'
            
            applicant.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Applicant updated successfully'
            })
    
    except ISFRecord.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'ISF record not found'})
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def delete_applicant(request):
    """
    AJAX endpoint to delete an applicant.
    Handles both Channel A (ISF records) and Channel B/C (Applicants).
    
    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Can delete applicants
    ✅ Joie (second_member) - Supervisor oversight
    ✅ OIC and Head - Administrative override
    """
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    allowed_positions = ['fourth_member', 'second_member', 'oic', 'head']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    applicant_id = request.POST.get('applicant_id')
    channel = request.POST.get('channel')
    
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id'})
    
    try:
        if channel == 'A':
            # Delete Channel A: ISF Record
            isf = ISFRecord.objects.get(id=applicant_id)
            isf_name = isf.full_name
            isf_ref = isf.reference_number
            
            # If this ISF was converted to an applicant, also handle that
            if isf.converted_to_applicant and hasattr(isf, 'applicant_profile'):
                isf.applicant_profile.delete()
            
            isf.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'ISF record "{isf_name}" ({isf_ref}) deleted successfully'
            })
            
        else:
            # Delete Channel B or C: Applicant
            applicant = Applicant.objects.get(id=applicant_id)
            app_name = applicant.full_name
            app_ref = applicant.reference_number
            
            # Delete related objects (CDRRMO certification, queue entries, etc.)
            if hasattr(applicant, 'cdrrmocertification'):
                applicant.cdrrmocertification.delete()
            
            # Remove from queues
            applicant.queue_entries.all().delete()
            
            # Delete the applicant
            applicant.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Applicant "{app_name}" ({app_ref}) deleted successfully'
            })
            
    except ISFRecord.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'ISF record not found'})
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def resend_sms(request):
    """
    Resend SMS notification to applicant.
    Accessible to: Second Member (Joie), Fourth Member (Jocel)
    """
    allowed_positions = ['second_member', 'fourth_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    channel = request.POST.get('channel')
    record_id = request.POST.get('id')
    sms_type = request.POST.get('sms_type', 'registration')  # 'registration' or 'eligibility'
    
    if not channel or not record_id:
        return JsonResponse({'success': False, 'error': 'Missing channel or id'})
    
    try:
        if channel == 'A':
            record = ISFRecord.objects.get(id=record_id)
            if not record.phone_number:
                return JsonResponse({'success': False, 'error': 'No phone number on record'})
            
            if sms_type == 'registration':
                record.registration_sms_sent = False  # Reset to trigger resend
                record.send_registration_sms()
            else:
                record.eligibility_sms_sent = False
                record.send_eligibility_sms(eligible=record.status == 'eligible')
        else:
            record = Applicant.objects.get(id=record_id)
            if not record.phone_number:
                return JsonResponse({'success': False, 'error': 'No phone number on record'})
            
            if sms_type == 'registration':
                record.registration_sms_sent = False
                record.send_registration_sms()
            else:
                record.eligibility_sms_sent = False
                record.send_eligibility_sms(eligible=record.status == 'eligible')
        
        return JsonResponse({
            'success': True,
            'message': f'{sms_type.title()} SMS resent successfully'
        })
        
    except (ISFRecord.DoesNotExist, Applicant.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Record not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


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
            'barangay': isf.barangay or isf.submission.barangay or '',  # ISF barangay or submission barangay
            'monthlyIncome': float(isf.monthly_income),
            'householdSize': isf.household_members,
            'yearsResiding': isf.years_residing,
            'phoneNumber': isf.phone_number or '',
            # Landowner info from submission
            'landownerName': isf.submission.landowner_name or '',
            'landownerPhone': isf.submission.landowner_phone or '',
            'propertyAddress': isf.submission.property_address or '',
            'submissionBarangay': isf.submission.barangay or '',  # Landowner's barangay
            'eligibilityStatus': eligibility_status,
            'queueType': queue_type,
            'queuePosition': queue_position,
            'cdrrmoStatus': None,
            'dangerZoneType': None,
            'isCdrrmoFlagged': False,
            'signatoryRoutingDelayed': False,
            'disqualificationReason': isf.disqualification_reason or None,
            # Staff who handled this record
            'handledBy': isf.eligibility_checked_by.get_full_name() if isf.eligibility_checked_by else 'Landowner Portal',
            'handledByPosition': isf.eligibility_checked_by.get_position_display_short() if isf.eligibility_checked_by else 'Public',
            'handledByInitials': (isf.eligibility_checked_by.first_name[:1] + isf.eligibility_checked_by.last_name[:1]).upper() if isf.eligibility_checked_by else 'LP',
            # Document checklist count (7 documents)
            'docsCount': sum([
                isf.doc_brgy_residency,
                isf.doc_brgy_indigency,
                isf.doc_cedula,
                isf.doc_police_clearance,
                isf.doc_no_property,
                isf.doc_2x2_picture,
                isf.doc_sketch_location,
            ]),
            'docsTotal': 7,
            # Individual document states for modal checkboxes
            'docBrgyResidency': isf.doc_brgy_residency,
            'docBrgyIndigency': isf.doc_brgy_indigency,
            'docCedula': isf.doc_cedula,
            'docPoliceClearance': isf.doc_police_clearance,
            'docNoProperty': isf.doc_no_property,
            'doc2x2Picture': isf.doc_2x2_picture,
            'docSketchLocation': isf.doc_sketch_location,
            # SMS status
            'registrationSmsSent': isf.registration_sms_sent,
            'eligibilitySmsSent': isf.eligibility_sms_sent,
            'hasPhone': bool(isf.phone_number),
        })
    
    # ====== CHANNEL B & C: Walk-in Applicants ======
    # Get all direct applicants (Channel B: danger_zone, Channel C: walk_in)
    walk_in_applicants = Applicant.objects.filter(
        channel__in=['danger_zone', 'walk_in']
    ).select_related('barangay', 'eligibility_checked_by', 'registered_by').prefetch_related(
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
        cdrrmo_days_pending = 0
        if app.channel == 'danger_zone':
            try:
                cert = app.cdrrmo_certification
                cdrrmo_status = cert.get_status_display()
                danger_zone_type = cert.declared_location
                is_cdrrmo_flagged = cert.status == 'pending' and cert.is_overdue
                cdrrmo_days_pending = cert.days_pending if cert.status == 'pending' else 0
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
            'householdSize': app.household_size,
            'yearsResiding': app.years_residing,
            'phoneNumber': app.phone_number or '',
            'currentAddress': app.current_address or '',
            # Channel B specific - get from model or CDRRMO cert
            'dangerZoneType': app.danger_zone_type if hasattr(app, 'danger_zone_type') and app.danger_zone_type else '',
            'dangerZoneLocation': app.danger_zone_location if hasattr(app, 'danger_zone_location') and app.danger_zone_location else (danger_zone_type or ''),
            'eligibilityStatus': eligibility_status,
            'queueType': queue_type,
            'queuePosition': queue_position,
            'cdrrmoStatus': cdrrmo_status,
            'isCdrrmoFlagged': is_cdrrmo_flagged,
            'cdrrmoDaysPending': cdrrmo_days_pending,
            'signatoryRoutingDelayed': False,  # TODO: Link to Module 2
            'disqualificationReason': app.disqualification_reason or None,
            # Staff who handled this record
            'handledBy': app.registered_by.get_full_name() if app.registered_by else 'Unknown',
            'handledByPosition': app.registered_by.get_position_display_short() if app.registered_by else '',
            'handledByInitials': (app.registered_by.first_name[:1] + app.registered_by.last_name[:1]).upper() if app.registered_by else '??',
            # Document checklist count (7 documents)
            'docsCount': sum([
                app.doc_brgy_residency,
                app.doc_brgy_indigency,
                app.doc_cedula,
                app.doc_police_clearance,
                app.doc_no_property,
                app.doc_2x2_picture,
                app.doc_sketch_location,
            ]),
            'docsTotal': 7,
            # Individual document states for modal checkboxes
            'docBrgyResidency': app.doc_brgy_residency,
            'docBrgyIndigency': app.doc_brgy_indigency,
            'docCedula': app.doc_cedula,
            'docPoliceClearance': app.doc_police_clearance,
            'docNoProperty': app.doc_no_property,
            'doc2x2Picture': app.doc_2x2_picture,
            'docSketchLocation': app.doc_sketch_location,
            # SMS status
            'registrationSmsSent': app.registration_sms_sent,
            'eligibilitySmsSent': app.eligibility_sms_sent,
            'hasPhone': bool(app.phone_number),
        })
    
    # Sort all applicants by dateRegistered (FIFO - oldest first)
    applicants.sort(key=lambda x: x['dateRegistered'])
    
    # Get barangays from database
    barangays = list(Barangay.objects.filter(is_active=True).values_list('name', flat=True).order_by('name'))
    
    # Calculate stats
    total_applicants = len(applicants)
    priority_count = len([a for a in applicants if a['queueType'] == 'Priority'])
    walkin_count = len([a for a in applicants if a['queueType'] == 'Walk-in'])
    # Count Channel B applicants awaiting CDRRMO certification
    pending_cdrrmo = len([a for a in applicants if a.get('eligibilityStatus') == 'Pending CDRRMO' or a.get('cdrrmoStatus') == 'Pending CDRRMO Visit'])
    
    # Count CDRRMO overdue (pending > 14 days)
    cdrrmo_overdue = len([a for a in applicants if a.get('isCdrrmoFlagged')])
    
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
            'pending_cdrrmo': pending_cdrrmo,
            'cdrrmo_overdue': cdrrmo_overdue
        }
    }
    
    return render(request, 'intake/staff/applicants.html', context)
