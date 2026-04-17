from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Prefetch
from functools import wraps
from .models import Applicant, Barangay, QueueEntry, CDRRMOCertification
from .forms import (
    HouseholdMemberForm,
    WalkInApplicantForm
)
from .utils import check_blacklist, send_sms
import json


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



@login_required
@verify_position
def isf_review(request, position, isf_id):
    """DEPRECATED: Channel A (ISF Review) has been removed."""
    return JsonResponse({'error': 'Channel A has been removed'}, status=404)


@login_required
@verify_position
def register_landowner_walkin(request, position):
    """
    DEPRECATED: Landowner submission flow has been removed.
    This endpoint is no longer available.
    """
    return JsonResponse({'success': False, 'error': 'Landowner submission flow has been removed.'}, status=404)


@login_required
@verify_position
def edit_isf_record(request, position, isf_id):
    """DEPRECATED: Channel A (Edit ISF) has been removed."""
    return JsonResponse({'error': 'Channel A has been removed'}, status=404)


@login_required
@verify_position
def update_eligibility(request, position):
    """
    AJAX endpoint to update applicant eligibility status.
    Used by the review modal for marking eligible or disqualifying applicants.

    URL Route: /intake/staff/<position>/update-eligibility/

    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Primary eligibility checker
    ✅ Joie (second_member) - Supervisor oversight
    ✅ Victor (oic) - OIC override
    """
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    # Only Jocel and Joie can mark eligibility (operational staff)
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Jocel or Joie can mark eligibility.'}, status=403)
    
    applicant_id = request.POST.get('applicant_id')
    action = request.POST.get('action')
    channel = request.POST.get('channel', '')
    
    if not applicant_id or not action:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id or action'})

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
        
        # For Channel B, check CDRRMO certification only if applicant is actually in a danger zone
        if applicant.channel == 'danger_zone' and applicant.danger_zone_type:
            # Only require CDRRMO if applicant declared they're in a danger zone
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

        # Add to priority queue (all applicants are danger zone)
        queue_type = 'priority'

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
@verify_position
def update_applicant(request, position):
    """
    AJAX endpoint to update applicant data (edit mode in review modal).
    Handles Channel B/C (Applicants) walk-in registrations.

    URL Route: /intake/staff/<position>/update-applicant/

    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Primary data editor
    ✅ Joie (second_member) - Supervisor oversight
    """
    from django.http import JsonResponse
    from decimal import Decimal
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    # Only Jocel and Joie can edit applicant data (operational staff)
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Jocel or Joie can edit applicant data.'}, status=403)
    
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
        # Handle document update (auto-save)
        if action == 'update_doc':
            applicant = Applicant.objects.get(id=applicant_id)
            for field in doc_fields:
                if field in request.POST:
                    setattr(applicant, field, request.POST.get(field) == 'true')
            applicant.save()
            return JsonResponse({'success': True, 'message': 'Document status updated'})

        # Update Applicant data
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
                        applicant.status = 'disqualified'  # Not verified as danger zone
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

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@verify_position
@require_POST
def update_cdrrmo_certification(request, position):
    """
    Dedicated endpoint for CDRRMO certification decision workflow.

    URL Route: /intake/staff/<position>/update-cdrrmo-certification/

    Channel B applicants must be certified by CDRRMO as danger zone (or not).
    This endpoint records the CDRRMO officer's decision and determines queue placement.

    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Primary decision maker
    ✅ Joie (second_member) - Supervisor oversight

    Workflow:
    1. Jocel reviews Channel B applicant (walk-in with danger zone claim)
    2. Jocel coordinates with CDRRMO office (manual process)
    3. CDRRMO officer visits location and certifies YES/NO
    4. Jocel records decision here with notes
    5. System automatically:
       - If CERTIFIED: Adds to Priority Queue (high priority)
       - If NOT CERTIFIED: Moves to Walk-in FIFO Queue (penalty for false claim)
       - Send SMS with final queue placement
    """
    from decimal import Decimal

    # Permission check
    allowed_positions = ['fourth_member', 'second_member', 'oic', 'head']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        decision = request.POST.get('decision')  # 'certified' or 'not_certified'
        notes = request.POST.get('notes', '').strip()

        if not applicant_id or not decision:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id or decision'})

        if decision not in ['certified', 'not_certified']:
            return JsonResponse({'success': False, 'error': 'Invalid decision. Must be "certified" or "not_certified"'})

        # Get applicant
        applicant = Applicant.objects.get(id=applicant_id)

        # Check if CDRRMO certification exists
        if not hasattr(applicant, 'cdrrmo_certification'):
            return JsonResponse({'success': False, 'error': 'This applicant is not awaiting CDRRMO certification (not Channel B)'})

        cert = applicant.cdrrmo_certification

        # Check if already decided
        if cert.status != 'pending':
            return JsonResponse({'success': False, 'error': f'CDRRMO decision already made: {cert.get_status_display()}'})

        # Record decision
        cert.status = decision
        cert.result_recorded_by = request.user
        cert.certified_at = timezone.now()
        if notes:
            cert.certification_notes = notes
        cert.save()

        # Update applicant status and queue placement
        if decision == 'certified':
            # CDRRMO certified as danger zone → Priority Queue
            applicant.status = 'eligible'
            applicant.save()

            # Create queue entry (priority)
            queue_entry = QueueEntry.objects.create(
                applicant=applicant,
                queue_type='priority',
                status='active',
                position=QueueEntry.objects.filter(queue_type='priority', status='active').count() + 1
            )

            message = f'✅ {applicant.full_name} CERTIFIED as danger zone. Added to Priority Queue (Position {queue_entry.position}).'

            # Send SMS: Certified
            if applicant.phone_number:
                sms_msg = f'Your location has been verified as a danger zone. You are assigned Priority Queue Position {queue_entry.position}. Please visit THA office for next steps.'
                send_sms(applicant.phone_number, sms_msg, 'cdrrmo_certified', applicant.id)

        else:  # not_certified
            # CDRRMO NOT certified → Disqualified
            applicant.status = 'disqualified'
            applicant.save()

            message = f'❌ {applicant.full_name} NOT CERTIFIED. Applicant disqualified.'

            # Send SMS: Not certified
            if applicant.phone_number:
                sms_msg = f'Your location claim could not be verified as a danger zone. Your application has been disqualified. Please visit THA office for more information.'
                send_sms(applicant.phone_number, sms_msg, 'cdrrmo_not_certified', applicant.id)

            return JsonResponse({
                'success': True,
                'message': message,
                'decision': decision
            })

        queue_entry = None

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error updating CDRRMO certification: {str(e)}'})


@login_required
@verify_position
def delete_applicant(request, position):
    """
    AJAX endpoint to delete an applicant.
    Handles Channel B/C (Applicants) walk-in registrations.

    URL Route: /intake/staff/<position>/delete-applicant/

    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Can delete applicants
    ✅ Joie (second_member) - Supervisor oversight
    ✅ OIC and Head - Administrative override
    """
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    # Only Jocel and Joie can delete applicants (operational staff)
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Jocel or Joie can delete records.'}, status=403)
    
    applicant_id = request.POST.get('applicant_id')
    channel = request.POST.get('channel')
    
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id'})
    
    try:
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

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@verify_position
@require_POST
def resend_sms(request, position):
    """
    Resend SMS notification to applicant.
    Handles Channel B/C (Applicants) walk-in registrations.

    URL Route: /intake/staff/<position>/resend-sms/

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

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Record not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@verify_position
def applicants_list(request, position):
    """
    Module 1: Applicant Intake Management
    Accessible to: Second Member (Joie), Fourth Member (Jocel)
    Unified view for danger zone applicant intake:

    Channel B (Danger Zone) → Shows Applicants with channel='danger_zone'

    Displays in FIFO order (oldest first by registration date).

    URL Route: /intake/staff/<position>/applicants/
    """
    # Staff who can view applicants list:
    # - Jocel (fourth_member) & Joie (second_member): Full access - can review, edit, mark eligibility
    # - Ronda & Field Team: Read access - can view for verification
    # - OIC & Head: View only - oversight access
    allowed_positions = ['second_member', 'fourth_member', 'field', 'ronda', 'oic', 'head']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. This module is for authorized staff only.')
        return redirect('accounts:dashboard')

    # Determine if user has full access (can modify) or read-only (field/oversight)
    can_modify = request.user.position in ['second_member', 'fourth_member']

    # Build applicants list from danger zone channel only
    applicants = []

    # ====== CHANNEL B: Danger Zone Applicants ======
    # Landowner submission flow has been removed
    # Removed ISFRecord queries since LandownerSubmission model deleted
    isf_records = []

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
                applicant_profile = Applicant.objects.filter(isf_record=isf).first()
                if applicant_profile:
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
            'channelSource': 'staff_entry' if isf.submitted_by_staff else 'portal',  # Differentiate Channel A source
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
            # Priority: submitted_by_staff (if staff entered) → eligibility_checked_by (if reviewed) → Landowner Portal (public)
            'handledBy': (isf.submitted_by_staff.get_full_name() if isf.submitted_by_staff else
                         (isf.eligibility_checked_by.get_full_name() if isf.eligibility_checked_by else 'Landowner Portal')),
            'handledByPosition': (isf.submitted_by_staff.get_position_display_short() if isf.submitted_by_staff else
                                 (isf.eligibility_checked_by.get_position_display_short() if isf.eligibility_checked_by else 'Public')),
            'handledByInitials': ((isf.submitted_by_staff.first_name[:1] + isf.submitted_by_staff.last_name[:1]).upper() if isf.submitted_by_staff else
                                 ((isf.eligibility_checked_by.first_name[:1] + isf.eligibility_checked_by.last_name[:1]).upper() if isf.eligibility_checked_by else 'LP')),
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
    
    # ====== CHANNEL B: Danger Zone Applicants + ALL OTHER APPLICANTS ======
    # Get ALL applicants (danger zone, walk-in, etc.)
    walk_in_applicants = Applicant.objects.all().select_related(
        'barangay', 'eligibility_checked_by', 'registered_by'
    ).prefetch_related(
        Prefetch(
            'queue_entries',
            queryset=QueueEntry.objects.filter(status='active'),
            to_attr='active_queue'
        )
    ).order_by('created_at')

    for app in walk_in_applicants:
        # Determine eligibility status display
        # For Channel B (Danger Zone): check if applicant actually selected "Yes" for danger zone
        if app.channel == 'danger_zone' and app.status == 'pending_cdrrmo':
            # Only show "Pending CDRRMO" if they have a danger_zone_type (selected Yes)
            if app.danger_zone_type:
                eligibility_status = 'Pending CDRRMO'
            else:
                # They selected "No" for danger zone - they're eligible to proceed
                eligibility_status = 'Eligible'
        elif app.status == 'pending':
            eligibility_status = 'Pending'
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
            queue_type = 'Priority'
            queue_position = queue_entry.position

        # Get CDRRMO status for danger zone
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
            'channel': 'B' if app.channel == 'danger_zone' else 'C',  # Map database channels to UI channels
            'submissionId': None,
            'applicantId': str(app.id),
            # Section A: APPLICATION IDENTITY
            'lastName': '',  # Not stored separately - use fullName
            'firstName': '',  # Not stored separately - use fullName
            'middleName': '',  # Not stored separately - use fullName
            'sex': app.sex or '',
            'age': app.age or 0,
            'dateOfBirth': app.date_of_birth.isoformat() if app.date_of_birth else '',
            'placeOfBirth': app.place_of_birth or '',
            'barangay': app.barangay.name if app.barangay else 'Unknown',
            'phoneNumber': app.phone_number or '',
            'currentAddress': app.current_address or '',
            'spouseName': app.spouse_name or '',
            'spousePhone': app.spouse_phone or '',
            # Section B: HOUSEHOLD MEMBERS
            'householdSize': app.household_size,
            'householdMembers': [
                {
                    'name': member.name or '',
                    'relationship': member.relationship or '',
                    'age': member.age or 0,
                    'civilStatus': member.civil_status or ''
                }
                for member in app.household_members.all()
            ],
            # Section C: FAMILY INCOME
            'monthlyIncome': float(app.monthly_income),
            'yearsResiding': app.years_residing,
            'occupation': app.occupation or '',
            'employmentStatus': app.get_employment_status_display() if app.employment_status else '',
            # Danger Zone details
            'isInDangerZone': app.channel == 'danger_zone' and bool(app.danger_zone_type),
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
    # Count Channel B applicants awaiting CDRRMO certification (only those who selected Yes for danger zone)
    pending_cdrrmo = len([a for a in applicants if a.get('eligibilityStatus') == 'Pending CDRRMO' and a.get('dangerZoneType')])
    
    # Count CDRRMO overdue (pending > 14 days, only for those in actual danger zones)
    cdrrmo_overdue = len([a for a in applicants if a.get('isCdrrmoFlagged') and a.get('dangerZoneType')])
    
    context = {
        'page_title': 'ISF Recording Management',
        'user_position': request.user.position,
        'can_modify': can_modify,  # True for Jocel/Joie, False for Field Team
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


@login_required
@verify_position
def walkin_register(request, position):
    """
    Handle applicant registration from the modal form.
    Handles Channel B (Danger Zone) registrations only.

    URL Route: /intake/staff/<position>/walkin-register/

    Channel B: Danger Zone Walk-in → Creates Applicant + CDRRMO certification
    """
    from .utils import send_sms

    allowed_positions = ['fourth_member', 'field', 'ronda', 'second_member']
    if request.user.position not in allowed_positions:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        messages.error(request, 'You do not have permission to register applicants.')
        return redirect('accounts:dashboard')

    if request.method != 'POST':
        return redirect('intake:applicants_list')

    # ====== CHANNEL B: Danger Zone Applicants ======
    form = WalkInApplicantForm(request.POST)

    # Get the danger zone answer (Yes/No from the form)
    is_danger_zone_answer = request.POST.get('is_danger_zone', 'false') == 'true'

    if not form.is_valid():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return detailed form errors for debugging
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{field}: {error}")
            error_text = " | ".join(error_messages) if error_messages else "Form validation failed"
            return JsonResponse({'success': False, 'error': error_text})
        messages.error(request, 'Please fill all required fields.')
        return redirect('intake:applicants_list')

    # Get barangay instance
    barangay_name = form.cleaned_data['barangay']
    barangay, _ = Barangay.objects.get_or_create(name=barangay_name)

    # Check blacklist
    full_name = form.cleaned_data['full_name']
    phone_number = form.cleaned_data.get('phone_number', '')
    is_blacklisted, blacklist_entry = check_blacklist(full_name, phone_number)

    if is_blacklisted:
        msg = f'Applicant is blacklisted. Registration denied.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg})
        messages.error(request, msg)
        return redirect('intake:applicants_list')

    # Create applicant (always danger_zone channel)
    danger_zone_type = form.cleaned_data.get('danger_zone_type', '')
    danger_zone_location = form.cleaned_data.get('danger_zone_location', '')

    applicant = Applicant.objects.create(
        full_name=full_name,
        sex=form.cleaned_data.get('sex', ''),
        age=form.cleaned_data.get('age'),
        date_of_birth=form.cleaned_data.get('date_of_birth'),
        place_of_birth=form.cleaned_data.get('place_of_birth', ''),
        phone_number=phone_number,
        spouse_name=form.cleaned_data.get('spouse_name', ''),
        spouse_phone=form.cleaned_data.get('spouse_phone', ''),
        barangay=barangay,
        current_address=form.cleaned_data['current_address'],
        monthly_income=form.cleaned_data['monthly_income'],
        household_size=form.cleaned_data.get('household_size', 1) or 1,
        years_residing=form.cleaned_data.get('years_residing', 0),
        occupation=form.cleaned_data.get('occupation', ''),
        employment_status=form.cleaned_data.get('employment_status', ''),
        channel='danger_zone',
        status='pending_cdrrmo',
        danger_zone_type=danger_zone_type,
        danger_zone_location=danger_zone_location,
        registered_by=request.user,
        # Document checklist
        doc_brgy_residency=request.POST.get('doc_brgy_residency') == 'true',
        doc_brgy_indigency=request.POST.get('doc_brgy_indigency') == 'true',
        doc_cedula=request.POST.get('doc_cedula') == 'true',
        doc_police_clearance=request.POST.get('doc_police_clearance') == 'true',
        doc_no_property=request.POST.get('doc_no_property') == 'true',
        doc_2x2_picture=request.POST.get('doc_2x2_picture') == 'true',
        doc_sketch_location=request.POST.get('doc_sketch_location') == 'true',
    )

    # Create CDRRMO certification for danger zone
    declared_location = f"{danger_zone_type}: {danger_zone_location}" if danger_zone_location else danger_zone_type
    CDRRMOCertification.objects.create(
        applicant=applicant,
        declared_location=declared_location,
        status='pending',
        requested_by=request.user,
    )

    msg = f'{applicant.full_name} registered as Danger Zone applicant. Reference: {applicant.reference_number}'

    # Send SMS
    if phone_number:
        send_sms(phone_number, f"Registered for housing assistance. Reference: {applicant.reference_number}", 'registration', applicant=applicant)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from datetime import datetime

        # Prepare document checklist
        documents = {
            'doc_brgy_residency': 'Brgy. Certificate of Residency',
            'doc_brgy_indigency': 'Brgy. Certificate of Indigency',
            'doc_cedula': 'Cedula',
            'doc_police_clearance': 'Police Clearance',
            'doc_no_property': 'Certificate of No Property',
            'doc_2x2_picture': '2x2 Picture',
            'doc_sketch_location': 'Sketch of House Location',
        }

        documents_submitted = {}
        docs_count = 0
        for field, label in documents.items():
            is_checked = getattr(applicant, field, False)
            documents_submitted[field] = {
                'label': label,
                'checked': is_checked
            }
            if is_checked:
                docs_count += 1

        return JsonResponse({
            'success': True,
            'message': msg,
            'applicant': {
                'id': str(applicant.id),
                'fullName': applicant.full_name,
                'referenceNumber': applicant.reference_number,
                'dateRegistered': applicant.created_at.strftime('%Y-%m-%d'),
                'channel': applicant.channel,
                'status': applicant.status,
                'barangay': applicant.barangay.name if applicant.barangay else '',
                'monthlyIncome': float(applicant.monthly_income),
                'householdSize': applicant.household_size,
                'yearsResiding': applicant.years_residing,
                'phoneNumber': applicant.phone_number,
                'currentAddress': applicant.current_address,
                'dangerZoneType': applicant.danger_zone_type,
                'dangerZoneLocation': applicant.danger_zone_location,
                'isInDangerZone': is_danger_zone_answer,  # Use the actual Yes/No answer
                'documents': documents_submitted,
                'docsCount': f"{docs_count}/7",
            }
        })

    messages.success(request, f'✓ {msg}')
    return redirect('intake:applicants_list')
