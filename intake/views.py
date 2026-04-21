from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q, Prefetch
from functools import wraps
from .models import Applicant, Barangay, QueueEntry, CDRRMOCertification, FieldVerificationPhoto
from .forms import (
    HouseholdMemberForm,
    WalkInApplicantForm
)
from .utils import check_blacklist, send_sms, ensure_priority_queue_entry
from . import sms_workflow
import json
from collections import defaultdict

# Module 1 income ceiling (₱) — keep in sync with `Applicant.is_income_eligible` in intake/models.py
MODULE1_MONTHLY_INCOME_CEILING_PESO = 10000


def _attach_applicants_sms_history(applicants):
    """Add smsHistory (latest SMSLog rows) for modal audit / workflow visibility."""
    from .models import SMSLog

    ids = [a['applicantId'] for a in applicants if a.get('applicantId')]
    by_app = defaultdict(list)
    if ids:
        for log in SMSLog.objects.filter(applicant_id__in=ids).order_by('-sent_at'):
            key = str(log.applicant_id)
            if len(by_app[key]) >= 12:
                continue
            by_app[key].append({
                'event': log.trigger_event,
                'status': log.status,
                'sentAt': log.sent_at.isoformat(),
            })
    for a in applicants:
        aid = a.get('applicantId')
        a['smsHistory'] = by_app.get(str(aid), []) if aid else []


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
        if applicant.status != 'pending_cdrrmo':
            return JsonResponse({
                'success': False,
                'error': (
                    f'This record is not pending CDRRMO processing (current status: {applicant.get_status_display()}). '
                    'No new CDRRMO office disposition can be recorded.'
                ),
            })
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})

    if action == 'set_doc_deadline':
        # Set document submission deadline and change status to "Requirements"
        from datetime import datetime
        deadline_str = request.POST.get('document_deadline')

        if not deadline_str:
            return JsonResponse({'success': False, 'error': 'Deadline not provided'})

        try:
            # Parse ISO format: "2026-04-25T17:00"
            deadline = datetime.fromisoformat(deadline_str)
            applicant.document_deadline = deadline
            applicant.status = 'requirements'  # Change to "Submitting Requirements"
            applicant.eligibility_checked_by = request.user
            applicant.eligibility_checked_at = timezone.now()
            applicant.save()

            # TODO: Send SMS notification to applicant with deadline

            return JsonResponse({'success': True, 'message': 'Deadline set successfully'})
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid deadline format'})

    elif action == 'mark_eligible':
        return JsonResponse({
            'success': False,
            'error': (
                'Eligibility decisions were moved to Module 2 (Application & Evaluation). '
                'Use /applications/staff/<position>/ and click View.'
            ),
        }, status=400)
    
    elif action == 'disqualify':
        return JsonResponse({
            'success': False,
            'error': (
                'Disqualification decisions were moved to Module 2 (Application & Evaluation). '
                'Use /applications/staff/<position>/ and click View.'
            ),
        }, status=400)
    
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
        if applicant.status != 'pending_cdrrmo':
            return JsonResponse({
                'success': False,
                'error': (
                    f'This record is not pending CDRRMO processing (current status: {applicant.get_status_display()}). '
                    'Field verification is disabled for non-pending records.'
                ),
            })

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
                    cert.disposition_source = 'field_unit'
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
        office_receipt = request.POST.get('office_receipt', '').strip().lower() in ('1', 'true', 'yes', 'on')

        if not applicant_id or not decision:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id or decision'})

        if decision not in ['certified', 'not_certified']:
            return JsonResponse({'success': False, 'error': 'Invalid decision. Must be "certified" or "not_certified"'})

        # Get applicant
        applicant = Applicant.objects.get(id=applicant_id)
        if applicant.status != 'pending_cdrrmo':
            return JsonResponse({
                'success': False,
                'error': (
                    f'This record is not pending CDRRMO staff finalization (current status: {applicant.get_status_display()}).'
                ),
            })

        # Check if CDRRMO certification exists
        if not hasattr(applicant, 'cdrrmo_certification'):
            return JsonResponse({'success': False, 'error': 'This applicant is not awaiting CDRRMO certification (not Channel B)'})

        cert = applicant.cdrrmo_certification

        # Check if already decided
        if cert.status != 'pending':
            return JsonResponse({'success': False, 'error': f'CDRRMO decision already made: {cert.get_status_display()}'})

        # Record decision — always intake-filed disposition (official paperwork / intake recording)
        cert.status = decision
        cert.result_recorded_by = request.user
        cert.certified_at = timezone.now()
        cert.disposition_source = 'office_intake'
        cert.office_intake_notes = notes if notes else ''
        cert.certification_notes = ''
        cert.save()

        # Update applicant status and queue placement
        if decision == 'certified':
            # CDRRMO certified as danger zone → Priority Queue
            applicant.status = 'eligible'
            applicant.save()

            queue_entry, _ = ensure_priority_queue_entry(applicant, added_by=request.user)

            message = f'✅ {applicant.full_name} CERTIFIED as danger zone. Added to Priority Queue (Position {queue_entry.position}).'

            if applicant.phone_number:
                if office_receipt:
                    sms_msg = sms_workflow.message_cdrrmo_office_received(applicant, queue_entry.position)
                    sms_event = sms_workflow.CDRRMO_OFFICE_CERTIFIED
                else:
                    sms_msg = sms_workflow.message_cdrrmo_certified_priority(applicant, queue_entry.position)
                    sms_event = sms_workflow.CDRRMO_CERTIFIED
                send_sms(applicant.phone_number, sms_msg, sms_event, applicant=applicant)

            return JsonResponse({
                'success': True,
                'message': message,
                'decision': decision,
                'queue_position': queue_entry.position,
            })

        else:  # not_certified
            # CDRRMO NOT certified → Disqualified
            applicant.status = 'disqualified'
            applicant.save()

            message = f'❌ {applicant.full_name} NOT CERTIFIED. Applicant disqualified.'

            if applicant.phone_number:
                sms_msg = sms_workflow.message_cdrrmo_not_certified(applicant)
                send_sms(applicant.phone_number, sms_msg, sms_workflow.CDRRMO_NOT_CERTIFIED, applicant=applicant)

            return JsonResponse({
                'success': True,
                'message': message,
                'decision': decision
            })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error updating CDRRMO certification: {str(e)}'})


@login_required
@require_POST
def field_verify_cdrrmo(request, position):
    """
    AJAX endpoint for RONDA/FIELD TEAM to submit CDRRMO verification findings.

    URL Route: /intake/staff/<position>/field-verify-cdrrmo/

    Channel B applicants: Ronda team visits location and records findings:
    - "Certified": Applicant IS in danger zone (confirmed)
    - "Not Certified": FALSE ALARM - applicant is NOT in danger zone

    ACCESS CONTROL:
    ✅ ronda / field - Field personnel only

    Workflow:
    1. Field team opens pending verification from dashboard
    2. Field team visits applicant's address
    3. Field team submits finding: Certified YES or NO
    4. System records finding with "verified_by" tracking
    5. Staff (Jocel) sees verified status in review modal
    6. Staff confirms and marks eligible or disqualifies
    """

    # Permission check - Only field/ronda personnel
    if request.user.position not in ['ronda', 'field']:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only field personnel can verify.'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        verification_decision = request.POST.get('verification_decision')  # 'certified' or 'not_certified'
        verification_notes = request.POST.get('verification_notes', '').strip()

        if not applicant_id or not verification_decision:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id or verification_decision'})

        if verification_decision not in ['certified', 'not_certified']:
            return JsonResponse({'success': False, 'error': 'Invalid decision. Must be "certified" or "not_certified"'})

        # Get applicant
        applicant = Applicant.objects.get(id=applicant_id)

        # Check if CDRRMO certification exists
        if not hasattr(applicant, 'cdrrmo_certification'):
            return JsonResponse({'success': False, 'error': 'This applicant is not awaiting CDRRMO verification'})

        cert = applicant.cdrrmo_certification

        if cert.status != 'pending':
            return JsonResponse({
                'success': False,
                'error': (
                    'A CDRRMO disposition is already on file (for example, official certification received at THA intake). '
                    'Field verification cannot overwrite it.'
                ),
            })

        # Field / Ronda on-site verification (separate from intake-filed CDRRMO paperwork)
        cert.status = verification_decision
        cert.certified_at = timezone.now()
        cert.result_recorded_by = request.user
        cert.disposition_source = 'field_unit'
        cert.office_intake_notes = ''
        cert.certification_notes = verification_notes if verification_notes else ''

        cert.save()

        # Move record into Module 2 handoff list once field verification is submitted.
        # This ensures evidence photos are visible from Application & Evaluation.
        if not applicant.module2_handoff_at:
            applicant.module2_handoff_at = timezone.now()
            applicant.module2_handoff_by = request.user
            applicant.save(update_fields=['module2_handoff_at', 'module2_handoff_by', 'updated_at'])

        # Optional on-site evidence photos (camera / gallery); validated server-side
        photos = request.FILES.getlist('evidence_photos')
        max_photos = 12
        max_bytes = 6 * 1024 * 1024
        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
        photos_saved = 0

        for upload in photos[:max_photos]:
            if upload.size > max_bytes:
                continue
            ct = (upload.content_type or '').lower()
            name = (upload.name or '').lower()
            if ct not in allowed_types and not name.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                continue
            FieldVerificationPhoto.objects.create(
                certification=cert,
                image=upload,
                uploaded_by=request.user,
            )
            photos_saved += 1

        sms_dispatched = None
        if applicant.phone_number:
            if verification_decision == 'certified':
                sms_body = sms_workflow.message_field_inspection_sustained(applicant)
                sms_ev = sms_workflow.FIELD_VERIFICATION_CERTIFIED
            else:
                sms_body = sms_workflow.message_field_inspection_not_sustained(applicant)
                sms_ev = sms_workflow.FIELD_VERIFICATION_NOT_CERTIFIED
            sms_dispatched = send_sms(applicant.phone_number, sms_body, sms_ev, applicant=applicant)

        return JsonResponse({
            'success': True,
            'message': f'Verification recorded as {"✓ Certified" if verification_decision == "certified" else "✗ Not Certified"}',
            'certification_status': verification_decision,
            'recorded_by': f'{request.user.first_name} {request.user.last_name}',
            'recorded_at': timezone.now().isoformat(),
            'photos_saved': photos_saved,
            'sms_dispatched': sms_dispatched,
            'moved_to_module2': True,
        })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error recording verification: {str(e)}'})


@login_required
@verify_position
def update_cdrrmo_status(request, position):
    """
    AJAX endpoint for STAFF to approve/reject ronda team's CDRRMO verification findings.

    URL Route: /intake/staff/<position>/update-cdrrmo-status/

    Workflow:
    1. Ronda team submits field verification (certified or not_certified)
    2. Staff opens applicant review modal
    3. Staff sees ronda team's finding
    4. Staff clicks: Approve or Reject
    5. Based on decision:
       - APPROVED + Certified → Eligible + Priority Queue
       - APPROVED + Not Certified → Eligible via Walk-in + Walk-in Queue
       - REJECTED → Disqualified (ronda finding overruled)

    ACCESS CONTROL:
    ✅ Jocel (fourth_member) - Primary processor
    ✅ Joie (second_member) - Supervisor oversight
    """

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    # Only Jocel and Joie can approve CDRRMO (operational staff)
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Jocel or Joie can approve CDRRMO.'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        decision = request.POST.get('decision')  # 'approved' or 'rejected'
        staff_notes = request.POST.get('staff_notes', '').strip()

        if not applicant_id or not decision:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id or decision'})

        if decision not in ['approved', 'rejected']:
            return JsonResponse({'success': False, 'error': 'Invalid decision. Must be "approved" or "rejected"'})

        # Get applicant
        applicant = Applicant.objects.get(id=applicant_id)

        # Check if CDRRMO certification exists and is pending staff approval
        if not hasattr(applicant, 'cdrrmo_certification'):
            return JsonResponse({'success': False, 'error': 'This applicant does not have CDRRMO record'})

        cert = applicant.cdrrmo_certification
        if cert.status == 'pending':
            return JsonResponse({'success': False, 'error': 'Ronda team has not yet submitted verification'})

        if cert.disposition_source == 'office_intake':
            return JsonResponse({
                'success': False,
                'error': (
                    'This record was finalized from official CDRRMO paperwork filed at THA intake. '
                    'There is no separate field report to accept or reject.'
                ),
            })

        ronda_finding = cert.status  # 'certified' or 'not_certified'

        # Process staff decision
        if decision == 'approved':
            # Staff approved ronda team's finding
            # Update applicant eligibility based on ronda finding
            applicant.eligibility_checked_by = request.user
            applicant.eligibility_checked_at = timezone.now()

            if ronda_finding == 'certified':
                # Danger zone confirmed - mark eligible and priority queue
                applicant.status = 'eligible'
                queue_type = 'Priority'
                msg_outcome = 'moved to Priority Queue'

                queue_entry, _ = ensure_priority_queue_entry(applicant, added_by=request.user)
            else:
                # Not in danger zone - still mark eligible and add to FIFO queue immediately.
                applicant.status = 'eligible'
                queue_type = 'Priority'
                queue_entry, _ = ensure_priority_queue_entry(applicant, added_by=request.user)
                msg_outcome = 'marked eligible and added to queue'

            # Save applicant
            applicant.save()

            # Update CDRRMO cert - keep status as set by ronda team
            # Don't change the status, just mark as processed by staff
            cert.save()

            # Send SMS to applicant
            if applicant.phone_number:
                eligible_msg = (
                    "✅ Great news! Your housing application passed eligibility. "
                    f"You are assigned Priority Queue Position {queue_entry.position}. "
                    f"Reference: {applicant.reference_number}. Please visit THA office for next steps."
                )
                send_sms(applicant.phone_number, eligible_msg, 'eligibility_passed', applicant=applicant)

            return JsonResponse({
                'success': True,
                'message': f'CDRRMO approval confirmed! Applicant {msg_outcome}.',
                'status': 'approved',
                'queue_type': queue_type
            })

        else:  # decision == 'rejected'
            # Staff rejected ronda team's finding - disqualify applicant
            applicant.status = 'disqualified'
            applicant.disqualification_reason = f'CDRRMO verification disputed by staff. Ronda finding: {ronda_finding}. Staff assessment: insufficient grounds for acceptance.'
            applicant.eligibility_checked_by = request.user
            applicant.eligibility_checked_at = timezone.now()
            applicant.save()

            # Remove from queue if exists
            QueueEntry.objects.filter(applicant=applicant).delete()

            # CDRRMO status stays as set by ronda team - don't modify
            # Staff rejection is recorded in applicant.status=disqualified
            cert.save()

            # Send SMS to applicant
            if applicant.phone_number:
                reject_msg = f"❌ Unfortunately, your housing application could not be processed at this time. Reason: Danger zone verification could not be confirmed. Reference: {applicant.reference_number}. Please visit THA office for appeals."
                send_sms(applicant.phone_number, reject_msg, 'eligibility_fail', applicant=applicant)

            return JsonResponse({
                'success': True,
                'message': 'CDRRMO verification rejected. Applicant has been disqualified.',
                'status': 'rejected'
            })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing approval: {str(e)}'})


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
@require_POST
def proceed_to_applications(request, position):
    """
    Mark an intake record as handed off to Module 2.
    """
    if request.user.position not in ['second_member', 'fourth_member']:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    if applicant.status == 'disqualified':
        return JsonResponse({'success': False, 'error': 'Disqualified records cannot be forwarded to Module 2.'}, status=400)

    if not applicant.module2_handoff_at:
        applicant.module2_handoff_at = timezone.now()
        applicant.module2_handoff_by = request.user
        applicant.save(update_fields=['module2_handoff_at', 'module2_handoff_by', 'updated_at'])

    module2_url = reverse('applications:applications_list', kwargs={'position': request.user.position})
    return JsonResponse({'success': True, 'module2_url': module2_url})


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
            'incomeEligible': float(isf.monthly_income) <= MODULE1_MONTHLY_INCOME_CEILING_PESO,
            'incomeCeilingPeso': MODULE1_MONTHLY_INCOME_CEILING_PESO,
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
    walk_in_applicants = Applicant.objects.filter(
        module2_handoff_at__isnull=True
    ).select_related(
        'barangay', 'eligibility_checked_by', 'registered_by', 'cdrrmo_certification'
    ).prefetch_related(
        Prefetch(
            'queue_entries',
            queryset=QueueEntry.objects.filter(status='active'),
            to_attr='active_queue',
        ),
        Prefetch(
            'cdrrmo_certification__field_photos',
            queryset=FieldVerificationPhoto.objects.order_by('uploaded_at'),
        ),
    ).order_by('created_at')

    for app in walk_in_applicants:
        # Determine eligibility status display
        # For Channel B (Danger Zone): check if applicant actually selected "Yes" for danger zone
        if app.channel == 'danger_zone' and app.status == 'pending_cdrrmo':
            if app.danger_zone_type:
                eligibility_status = 'Pending CDRRMO verification'
            else:
                eligibility_status = 'Pending eligibility check'
        elif app.status == 'pending':
            eligibility_status = 'Pending eligibility check'
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
            qraw = (getattr(queue_entry, 'queue_type', None) or '').lower()
            if qraw == 'walk_in' or qraw == 'walk-in':
                queue_type = 'Walk-in'
            else:
                # Default / legacy: model uses 'priority' for danger-zone priority queue
                queue_type = 'Priority'
            queue_position = queue_entry.position

        # Get CDRRMO status for danger zone
        cdrrmo_status = None
        cdrrmo_status_value = None  # actual status value: pending, certified, not_certified
        danger_zone_type = None
        is_cdrrmo_flagged = False
        cdrrmo_days_pending = 0
        result_recorded_by_name = None
        certified_at = None
        certification_notes = None
        office_intake_notes = None
        cdrrmo_disposition_source = 'pending'
        ronda_evidence_photos = []
        if app.channel == 'danger_zone':
            try:
                cert = app.cdrrmo_certification
                cdrrmo_status = cert.get_status_display()
                cdrrmo_status_value = cert.status
                cdrrmo_disposition_source = cert.disposition_source
                danger_zone_type = cert.declared_location
                is_cdrrmo_flagged = cert.status == 'pending' and cert.is_overdue
                cdrrmo_days_pending = cert.days_pending if cert.status == 'pending' else 0
                result_recorded_by_name = f'{cert.result_recorded_by.first_name} {cert.result_recorded_by.last_name}' if cert.result_recorded_by else None
                certified_at = cert.certified_at.isoformat() if cert.certified_at else None
                certification_notes = cert.certification_notes or None
                office_intake_notes = cert.office_intake_notes or None
                for ph in cert.field_photos.all():
                    if ph.image:
                        try:
                            ronda_evidence_photos.append(request.build_absolute_uri(ph.image.url))
                        except (ValueError, AttributeError):
                            pass
            except CDRRMOCertification.DoesNotExist:
                cdrrmo_status = 'Not Requested'
                cdrrmo_status_value = None
                cdrrmo_disposition_source = 'pending'
        
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
            'lastName': app.last_name or '',
            'firstName': app.first_name or '',
            'middleName': app.middle_name or '',
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
                    'name': member.full_name or '',
                    'relationship': member.get_relationship_display() if hasattr(member, 'get_relationship_display') else (member.relationship or ''),
                    'age': member.age or 0,
                    'civilStatus': member.get_civil_status_display() if hasattr(member, 'get_civil_status_display') else (member.civil_status or '')
                }
                for member in app.household_members.all()
            ],
            # Section C: FAMILY INCOME
            'monthlyIncome': float(app.monthly_income),
            # Aligns with Applicant.is_income_eligible and update_eligibility (≤ ₱10,000)
            'incomeEligible': app.is_income_eligible,
            'incomeCeilingPeso': MODULE1_MONTHLY_INCOME_CEILING_PESO,
            'yearsResiding': app.years_residing,
            'occupation': app.occupation or '',
            'employmentStatus': app.get_employment_status_display() if app.employment_status else '',
            # Danger Zone details
            'isInDangerZone': app.channel == 'danger_zone' and bool(app.danger_zone_type),
            'dangerZoneType': app.danger_zone_type if hasattr(app, 'danger_zone_type') and app.danger_zone_type else '',
            'dangerZoneLocation': app.danger_zone_location if hasattr(app, 'danger_zone_location') and app.danger_zone_location else (danger_zone_type or ''),
            'eligibilityStatus': eligibility_status,
            'applicantStatus': app.status,
            'readyForModule2': (not bool(app.module2_handoff_at)) and app.status != 'disqualified',
            'module2HandedOff': bool(app.module2_handoff_at),
            'queueType': queue_type,
            'queuePosition': queue_position,
            'cdrrmoStatus': cdrrmo_status,
            'cdrrmo_status': cdrrmo_status_value,  # Raw status value for JS: pending, certified, not_certified
            'cdrrmo_disposition_source': cdrrmo_disposition_source,
            'office_intake_notes': office_intake_notes,
            'result_recorded_by_name': result_recorded_by_name,  # Who verified
            'certified_at': certified_at,  # When verified
            'certification_notes': certification_notes,  # Field / Ronda on-site notes only
            'ronda_evidence_photos': ronda_evidence_photos,  # Absolute URLs of field-captured evidence
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

    _attach_applicants_sms_history(applicants)
    
    # Get barangays from database
    barangays = list(Barangay.objects.filter(is_active=True).values_list('name', flat=True).order_by('name'))
    
    # Calculate stats
    total_applicants = len(applicants)
    priority_count = len([a for a in applicants if a['queueType'] == 'Priority'])
    walkin_count = len([a for a in applicants if a['queueType'] == 'Walk-in'])
    # Count Channel B applicants awaiting CDRRMO certification (only those who selected Yes for danger zone)
    pending_cdrrmo = len([
        a for a in applicants
        if a.get('applicantStatus') == 'pending_cdrrmo' and a.get('dangerZoneType')
    ])
    
    # Count CDRRMO overdue (pending > 14 days, only for those in actual danger zones)
    cdrrmo_overdue = len([a for a in applicants if a.get('isCdrrmoFlagged') and a.get('dangerZoneType')])
    ready_for_module2 = len([
        a for a in applicants
        if not a.get('module2HandedOff') and a.get('applicantStatus') != 'disqualified'
    ])
    
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
            'cdrrmo_overdue': cdrrmo_overdue,
            'ready_for_module2': ready_for_module2,
        }
    }
    return render(request, 'intake/staff/applicants.html', context)


@login_required
@verify_position
def walkin_register(request, position):
    """
    Office walk-in encoding (Module 1) — aligns with THA intake process:

    1. Applicant appears at the office (no prior record).
    2. Staff encodes identity, household, income, situation.
    3. If a hazard-area claim is declared, staff records it; status is pending CDRRMO
       *verification* (claim only — CDRRMO does not use this system).
    4–6. System persists Applicant profile, generates reference number, stores permanently.
    7. System sends registration SMS automatically when a mobile number is on file.

    URL Route: /intake/staff/<position>/walkin-register/
    """
    allowed_positions = ['fourth_member', 'field', 'ronda', 'second_member']
    if request.user.position not in allowed_positions:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        messages.error(request, 'You do not have permission to register applicants.')
        return redirect('accounts:dashboard')

    applicants_list_url = reverse('intake:applicants_list', kwargs={'position': position})

    if request.method != 'POST':
        return redirect(applicants_list_url)

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
        return redirect(applicants_list_url)

    # Age policy (server-side): 18-55 standard, >55 requires explicit staff consideration.
    date_of_birth = form.cleaned_data.get('date_of_birth')
    if not date_of_birth:
        msg = 'Date of birth is required.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg})
        messages.error(request, msg)
        return redirect(applicants_list_url)
    today = timezone.localdate()
    computed_age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    if computed_age < 18:
        msg = 'Applicant must be at least 18 years old.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg})
        messages.error(request, msg)
        return redirect(applicants_list_url)
    staff_consideration_overage = str(request.POST.get('consider_overage', '')).lower() in {'1', 'true', 'yes', 'on'}
    if computed_age > 55 and not staff_consideration_overage:
        msg = 'Applicant is above 55 years old. Staff consideration must be confirmed to proceed.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg})
        messages.error(request, msg)
        return redirect(applicants_list_url)

    # Get barangay instance
    barangay_name = form.cleaned_data['barangay']
    barangay, _ = Barangay.objects.get_or_create(name=barangay_name)

    # Check blacklist
    # WalkInApplicantForm currently posts split name fields; build a safe full name
    # instead of hard-indexing a non-existent `full_name` key.
    full_name = (form.cleaned_data.get('full_name') or '').strip()
    if not full_name:
        last_name = (form.cleaned_data.get('last_name') or '').strip()
        first_name = (form.cleaned_data.get('first_name') or '').strip()
        middle_name = (form.cleaned_data.get('middle_name') or '').strip()
        if last_name and first_name:
            full_name = f"{last_name}, {first_name}{(' ' + middle_name) if middle_name else ''}"
        else:
            full_name = "Unnamed Applicant"
    phone_number = form.cleaned_data.get('phone_number', '')
    is_blacklisted, blacklist_entry = check_blacklist(full_name, phone_number)

    if is_blacklisted:
        msg = f'Applicant is blacklisted. Registration denied.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg})
        messages.error(request, msg)
        return redirect(applicants_list_url)

    # Channel B — office walk-in; hazard claim is optional (steps 2–3).
    if is_danger_zone_answer:
        danger_zone_type = (form.cleaned_data.get('danger_zone_type') or '').strip()
        danger_zone_location = (form.cleaned_data.get('danger_zone_location') or '').strip()
        initial_status = 'pending_cdrrmo'
    else:
        danger_zone_type = ''
        danger_zone_location = ''
        initial_status = 'pending'

    applicant = Applicant.objects.create(
        last_name=form.cleaned_data.get('last_name', ''),
        first_name=form.cleaned_data.get('first_name', ''),
        middle_name=form.cleaned_data.get('middle_name', ''),
        full_name=full_name,
        sex=form.cleaned_data.get('sex', ''),
        age=computed_age,
        date_of_birth=date_of_birth,
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
        status=initial_status,
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

    # CDRRMO row only when a hazard-area *claim* was recorded (pending verification — not certified).
    if is_danger_zone_answer:
        declared_location = f"{danger_zone_type}: {danger_zone_location}" if danger_zone_location else danger_zone_type
        CDRRMOCertification.objects.create(
            applicant=applicant,
            declared_location=declared_location or '—',
            status='pending',
            disposition_source='pending',
            requested_by=request.user,
        )

    # Process household members from form
    for i in range(1, 51):  # Support up to 50 household members
        name = request.POST.get(f'hh_member_{i}_name', '').strip()
        relationship = request.POST.get(f'hh_member_{i}_relationship', '').strip()
        age = request.POST.get(f'hh_member_{i}_age', '').strip()
        civil_status = request.POST.get(f'hh_member_{i}_status', 'single').strip()

        # Only create if at least name and relationship are provided
        if name and relationship:
            try:
                age_int = int(age) if age else 0
                from intake.models import HouseholdMember
                HouseholdMember.objects.create(
                    applicant=applicant,
                    full_name=name,
                    relationship=relationship,
                    age=age_int,
                    civil_status=civil_status
                )
            except (ValueError, TypeError):
                # Skip invalid age values
                pass

    if is_danger_zone_answer:
        msg = (
            f'{applicant.full_name} registered. Hazard-area claim on file — pending CDRRMO verification. '
            f'Reference: {applicant.reference_number}'
        )
    else:
        msg = (
            f'{applicant.full_name} registered. Reference: {applicant.reference_number}. '
            f'Pending eligibility check (no hazard claim).'
        )

    # Step 7: automatic registration SMS when mobile is on file (updates registration_sms_sent)
    applicant.send_registration_sms()

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
            'registrationSmsSent': applicant.registration_sms_sent,
            'applicant': {
                'id': str(applicant.id),
                'fullName': applicant.full_name,
                'lastName': applicant.last_name,
                'firstName': applicant.first_name,
                'middleName': applicant.middle_name,
                'referenceNumber': applicant.reference_number,
                'dateRegistered': applicant.created_at.strftime('%Y-%m-%d'),
                'channel': applicant.channel,
                'status': applicant.status,
                'barangay': applicant.barangay.name if applicant.barangay else '',
                'monthlyIncome': float(applicant.monthly_income),
                'incomeEligible': applicant.is_income_eligible,
                'incomeCeilingPeso': MODULE1_MONTHLY_INCOME_CEILING_PESO,
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
    return redirect(applicants_list_url)
