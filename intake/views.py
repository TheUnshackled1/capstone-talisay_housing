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
def applicants_list(request):
    """
    Module 1: ISF Recording Management - Applicant Intake
    Accessible to: Second Member (Joie), Fourth Member (Jocel)
    Unified view for all applicant intake channels
    """
    allowed_positions = ['second_member', 'fourth_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. This module is for Second and Fourth Members only.')
        return redirect('accounts:dashboard')
    
    # Mock data - matching the React mockApplicants structure
    # Sorted in FIFO order (First In First Out - oldest first by dateRegistered)
    mock_applicants = [
        {
            'id': 5,
            'fullName': 'Mendoza, Elena Cruz',
            'referenceNumber': 'THA-2023-00234',
            'dateRegistered': '2023-09-12',
            'dateTime': '2023-09-12 09:15 AM',
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
            'id': 2,
            'fullName': 'Santos, Juan Pedro',
            'referenceNumber': 'THA-2024-00045',
            'dateRegistered': '2023-11-20',
            'dateTime': '2023-11-20 02:30 PM',
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
            'id': 4,
            'fullName': 'Garcia, Roberto Luis',
            'referenceNumber': 'THA-2024-00198',
            'dateRegistered': '2024-01-05',
            'dateTime': '2024-01-05 10:45 AM',
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
            'id': 1,
            'fullName': 'Dela Cruz, Maria Santos',
            'referenceNumber': 'THA-2024-00123',
            'dateRegistered': '2024-01-15',
            'dateTime': '2024-01-15 03:20 PM',
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
            'id': 6,
            'fullName': 'Torres, Miguel Angel',
            'referenceNumber': 'THA-2024-00067',
            'dateRegistered': '2024-01-22',
            'dateTime': '2024-01-22 11:05 AM',
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
        },
        {
            'id': 3,
            'fullName': 'Reyes, Ana Marie',
            'referenceNumber': 'THA-2024-00087',
            'dateRegistered': '2024-02-01',
            'dateTime': '2024-02-01 08:30 AM',
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
    
    return render(request, 'intake/staff/applicants.html', context)
