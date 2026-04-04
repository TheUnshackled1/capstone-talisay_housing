from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import LandownerSubmission, ISFRecord, Applicant, Barangay
from .forms import (
    LandownerSubmissionForm, 
    ISFRecordForm, 
    ISFReviewForm,
    HouseholdMemberForm
)
from .utils import check_blacklist, create_applicant_from_isf
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
def submission_list(request):
    """
    Staff view: List all ISF records for review (from landowner submissions).
    
    ACCESS CONTROL - Hierarchical Model:
    ✅ Jocel (fourth_member) - Primary reviewer
    ✅ Joie (second_member) - Supervisor/oversight, quality control
    ✅ Victor (oic) - Management oversight
    ✅ Arthur (head) - Executive oversight
    
    This allows for: backup coverage, quality control, management visibility
    """
    # Hierarchical access: Primary reviewer + Supervisor + Management
    if not request.user.position in ['fourth_member', 'second_member', 'oic', 'head']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    # Get all ISF records with related submission data
    isf_records = ISFRecord.objects.select_related('submission').order_by('-created_at')
    
    # Also get walk-in applicants (Channel B and C)
    from .models import Applicant
    walk_in_applicants = Applicant.objects.filter(
        channel__in=['danger_zone', 'walk_in']
    ).order_by('-created_at')
    
    # Count statistics
    total_isf = isf_records.count()
    pending_isf = isf_records.filter(status='pending').count()
    eligible_isf = isf_records.filter(status='eligible').count()
    disqualified_isf = isf_records.filter(status='disqualified').count()
    
    total_walkin = walk_in_applicants.count()
    pending_walkin = walk_in_applicants.filter(status='pending').count()
    eligible_walkin = walk_in_applicants.filter(status='eligible').count()
    disqualified_walkin = walk_in_applicants.filter(status='disqualified').count()
    
    return render(request, 'intake/staff/submission_list.html', {
        'isf_records': isf_records,
        'walk_in_applicants': walk_in_applicants,
        'total_isf': total_isf,
        'pending_isf': pending_isf,
        'eligible_isf': eligible_isf,
        'disqualified_isf': disqualified_isf,
        'total_walkin': total_walkin,
        'pending_walkin': pending_walkin,
        'eligible_walkin': eligible_walkin,
        'disqualified_walkin': disqualified_walkin,
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
