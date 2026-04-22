from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q, Prefetch
from django.core.exceptions import ObjectDoesNotExist
from functools import wraps
from .models import Applicant, Barangay, CDRRMOCertification, FieldVerificationPhoto, HazardDeclarationAudit
from applications.models import QueueEntry
from .forms import (
    HouseholdMemberForm,
    WalkInApplicantForm
)
from .utils import check_blacklist, send_sms, ensure_priority_queue_entry
from . import sms_workflow
import json
import re
from collections import defaultdict

# Module 1 income ceiling (₱) — keep in sync with `Applicant.is_income_eligible` in intake/models.py
MODULE1_MONTHLY_INCOME_CEILING_PESO = 10000


def _is_weak_hazard_location(raw_location):
    location = " ".join((raw_location or "").split()).strip().lower()
    if len(location) < 12:
        return True
    weak_values = {
        "n/a", "na", "none", "unknown", "same", "same as address",
        "same address", "barangay", "sitio", "landmark",
    }
    return location in weak_values


def _validate_hazard_details(is_danger_zone, danger_zone_type, danger_zone_location):
    if not is_danger_zone:
        return None
    if not (danger_zone_type or "").strip():
        return "Hazard classification is required when hazard-area residence is marked Yes."
    if _is_weak_hazard_location(danger_zone_location):
        return (
            "Location particulars must be specific (at least 12 characters), "
            "for example: sitio, landmark, and riverbank/road segment."
        )
    return None


def _log_hazard_declaration_change(
    applicant,
    changed_by,
    declared_before,
    declared_after,
    danger_zone_type_before='',
    danger_zone_type_after='',
    danger_zone_location_before='',
    danger_zone_location_after='',
    change_source='registration',
    notes='',
):
    HazardDeclarationAudit.objects.create(
        applicant=applicant,
        changed_by=changed_by,
        declared_before=declared_before,
        declared_after=declared_after,
        danger_zone_type_before=(danger_zone_type_before or '').strip(),
        danger_zone_type_after=(danger_zone_type_after or '').strip(),
        danger_zone_location_before=(danger_zone_location_before or '').strip(),
        danger_zone_location_after=(danger_zone_location_after or '').strip(),
        change_source=change_source,
        notes=(notes or '').strip(),
    )


def _describe_applicant_location(applicant):
    """
    Human-readable "where is this record now" label for duplicate checks.
    Priority: explicit module objects (Application / requirements activity), then applicant status.
    """
    location = 'Applicant Intake (Module 1)'
    status_text = applicant.get_status_display()

    # Module 2 object exists: applicant already moved into Applications.
    try:
        application = applicant.application
    except ObjectDoesNotExist:
        application = None
    if application is not None:
        location = 'Applications (Module 2)'
        status_text = application.get_status_display()
    elif applicant.requirement_submissions.exclude(status='pending').exists() or applicant.status == 'requirements':
        # Requirement submissions are processed under Documents module workflow.
        location = 'Documents (Requirements)'
    elif applicant.module2_handoff_at:
        location = 'Applications (Module 2 queue)'
    elif applicant.status == 'application':
        location = 'Applications (Module 2)'
    elif applicant.status in {'standby', 'awarded'}:
        location = 'Housing Units / Post-Approval'

    return location, status_text


def _build_duplicate_record_message(applicant):
    location, status_text = _describe_applicant_location(applicant)
    handled_by = applicant.registered_by.get_full_name() if applicant.registered_by else 'Unknown'
    return (
        "Duplicate record detected.\n"
        f"Matched record: {applicant.reference_number} ({applicant.full_name}).\n"
        "Match basis: same Date of Birth, Barangay, Last name, and First name.\n"
        f"Current location: {location}.\n"
        f"Current status: {status_text}.\n"
        f"Last handled by: {handled_by}."
    )


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
        old_danger_zone_type = (applicant.danger_zone_type or '').strip()
        old_danger_zone_location = (applicant.danger_zone_location or '').strip()
        old_declared = bool(old_danger_zone_type)
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
                if _is_weak_hazard_location(danger_zone_location):
                    return JsonResponse({
                        'success': False,
                        'error': 'Location particulars must be specific (at least 12 characters).'
                    })
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

        new_danger_zone_type = (applicant.danger_zone_type or '').strip()
        new_danger_zone_location = (applicant.danger_zone_location or '').strip()
        new_declared = bool(new_danger_zone_type)
        if (
            old_declared != new_declared
            or old_danger_zone_type != new_danger_zone_type
            or old_danger_zone_location != new_danger_zone_location
        ):
            _log_hazard_declaration_change(
                applicant=applicant,
                changed_by=request.user,
                declared_before=old_declared,
                declared_after=new_declared,
                danger_zone_type_before=old_danger_zone_type,
                danger_zone_type_after=new_danger_zone_type,
                danger_zone_location_before=old_danger_zone_location,
                danger_zone_location_after=new_danger_zone_location,
                change_source='staff_edit',
                notes='Updated from intake review modal.',
            )

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
    Deprecated intake proxy.
    CDRRMO action ownership moved to applications app.
    """
    from applications.views import update_cdrrmo_certification as app_update_cdrrmo_certification
    return app_update_cdrrmo_certification(request, position)


@login_required
@require_POST
def field_verify_cdrrmo(request, position):
    """
    Deprecated intake proxy.
    CDRRMO field verification moved to applications app.
    """
    from applications.views import field_verify_cdrrmo as app_field_verify_cdrrmo
    return app_field_verify_cdrrmo(request, position)


@login_required
@verify_position
def update_cdrrmo_status(request, position):
    """
    Deprecated intake proxy.
    CDRRMO staff finalization moved to applications app.
    """
    from applications.views import update_cdrrmo_status as app_update_cdrrmo_status
    return app_update_cdrrmo_status(request, position)


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
    For hazard-declared applicants, ensure a pending CDRRMO case exists
    so field/ronda verification starts after the Module 2 handoff.
    """
    if request.user.position not in ['second_member', 'fourth_member']:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    if applicant.status == 'disqualified':
        return JsonResponse({'success': False, 'error': 'Disqualified records cannot be forwarded to Module 2.'}, status=400)

    update_fields = ['updated_at']

    if not applicant.module2_handoff_at:
        applicant.module2_handoff_at = timezone.now()
        applicant.module2_handoff_by = request.user
        update_fields.extend(['module2_handoff_at', 'module2_handoff_by'])

    # Hazard-declared records must enter pending CDRRMO flow in Module 2.
    if applicant.channel == 'danger_zone' and bool((applicant.danger_zone_type or '').strip()):
        cert = getattr(applicant, 'cdrrmo_certification', None)
        if cert is None:
            CDRRMOCertification.objects.create(
                applicant=applicant,
                declared_location=(applicant.danger_zone_location or applicant.danger_zone_type or '').strip() or 'Declared hazard area',
                requested_by=request.user,
                status='pending',
                disposition_source='pending',
            )

        # Move encoding-stage record into CDRRMO awaiting state for Module 2.
        if applicant.status == 'pending':
            applicant.status = 'pending_cdrrmo'
            update_fields.append('status')

    if len(update_fields) > 1:
        applicant.save(update_fields=update_fields)

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
            'dateTime': isf.created_at.strftime('%b %d, %Y | %I:%M %p'),
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

    handed_off_applicants = Applicant.objects.filter(
        module2_handoff_at__isnull=False
    ).select_related(
        'barangay', 'registered_by', 'module2_handoff_by'
    ).order_by('module2_handoff_at', 'created_at', 'id')

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
            'dateTime': app.created_at.strftime('%b %d, %Y | %I:%M %p'),
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
            'barangay': app.barangay.name if app.barangay else 'Unknown',
            'phoneNumber': app.phone_number or '',
            'currentAddress': app.current_address or '',
            # Section B: HOUSEHOLD MEMBERS
            'householdSize': app.household_size,
            'householdMembers': [
                {
                    'name': member.full_name or '',
                    'relationship': member.get_relationship_display() if hasattr(member, 'get_relationship_display') else (member.relationship or ''),
                    'age': member.age or 0,
                    'civilStatus': member.get_civil_status_display() if hasattr(member, 'get_civil_status_display') else (member.civil_status or ''),
                    'contactNumber': getattr(member, 'contact_number', '') or '',
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

    # Read-only archive/receipt rows: records already proceeded to Module 2.
    archive_records = []
    for app in handed_off_applicants:
        danger_declared = bool(getattr(app, 'danger_zone_type', ''))
        channel_code = 'B' if app.channel == 'danger_zone' else 'C'
        if channel_code == 'B':
            channel_label = 'Channel B — Hazard (Yes)' if danger_declared else 'Channel B — No hazard (No)'
        else:
            channel_label = 'Channel C — Walk-in'
        proceeded_at = app.module2_handoff_at or app.created_at

        # Convert UTC time to Manila time for display
        from django.utils import timezone
        local_proceeded_at = timezone.localtime(proceeded_at) if proceeded_at else None

        archive_records.append({
            'id': str(app.id),
            'dateTime': local_proceeded_at.strftime('%b %d, %Y | %I:%M %p') if local_proceeded_at else '',
            'referenceNumber': app.reference_number,
            'fullName': app.full_name,
            'barangay': app.barangay.name if app.barangay else '',
            'channel': channel_code,
            'channelLabel': channel_label,
            'handledBy': app.registered_by.get_full_name() if app.registered_by else 'Unknown',
            'handledByPosition': app.registered_by.get_position_display_short() if app.registered_by else '',
            'handledByInitials': (app.registered_by.first_name[:1] + app.registered_by.last_name[:1]).upper() if app.registered_by else '??',
            'registrationSmsSent': app.registration_sms_sent,
            'hasPhone': bool(app.phone_number),
            'handoffAt': app.module2_handoff_at.strftime('%Y-%m-%d %I:%M %p') if app.module2_handoff_at else '',
            'handoffBy': app.module2_handoff_by.get_full_name() if app.module2_handoff_by else '',
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
        },
        'archive_records': archive_records,
    }
    return render(request, 'intake/staff/applicants.html', context)


@login_required
@verify_position
def walkin_register(request, position):
    """
    Module 1: Register & Record Walk-in Applicant

    PURPOSE: Encode applicant identity, household, income, danger zone claim (if any).
    - Staff enters all required information
    - System generates reference number
    - Registration SMS sent to applicant
    - Record saved to database — ready for Module 2 processing

    NOTE: All screening (blacklist, eligibility, CDRRMO coordination) happens in Module 2.
    This view is ENCODING & RECORDING ONLY.

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
    # Backward-compatible normalization for legacy client values.
    post_data = request.POST.copy()
    if post_data.get('employment_status') == 'self-employed':
        post_data['employment_status'] = 'self_employed'
    form = WalkInApplicantForm(post_data)

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

    # Duplicate guard: same DOB + barangay + last name + first name.
    duplicate_last_name = (form.cleaned_data.get('last_name') or '').strip()
    duplicate_first_name = (form.cleaned_data.get('first_name') or '').strip()
    duplicate_applicant = (
        Applicant.objects
        .select_related('registered_by', 'barangay')
        .prefetch_related('requirement_submissions')
        .filter(
            date_of_birth=date_of_birth,
            barangay=barangay,
            last_name__iexact=duplicate_last_name,
            first_name__iexact=duplicate_first_name,
        )
        .order_by('-updated_at', '-created_at')
        .first()
    )
    if duplicate_applicant:
        duplicate_msg = _build_duplicate_record_message(duplicate_applicant)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': duplicate_msg,
                'duplicate': True,
                'duplicate_reference': duplicate_applicant.reference_number,
                'duplicate_record_id': str(duplicate_applicant.id),
            })
        messages.error(request, duplicate_msg)
        return redirect(applicants_list_url)

    # Build full name from components (for display/reference only)
    # Note: Module 2 will perform blacklist check and other screening
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

    # Channel B — office walk-in; record danger zone claim if provided (for reference only)
    # Screening and eligibility determination will be done in Module 2
    if is_danger_zone_answer:
        danger_zone_type = (form.cleaned_data.get('danger_zone_type') or '').strip()
        danger_zone_location = (form.cleaned_data.get('danger_zone_location') or '').strip()
    else:
        danger_zone_type = ''
        danger_zone_location = ''
    hazard_validation_error = _validate_hazard_details(
        is_danger_zone_answer,
        danger_zone_type,
        danger_zone_location,
    )
    if hazard_validation_error:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': hazard_validation_error})
        messages.error(request, hazard_validation_error)
        return redirect(applicants_list_url)

    # All applicants start in 'pending' status - Module 2 will conduct screening
    initial_status = 'pending'

    applicant = Applicant.objects.create(
        last_name=form.cleaned_data.get('last_name', ''),
        first_name=form.cleaned_data.get('first_name', ''),
        middle_name=form.cleaned_data.get('middle_name', ''),
        full_name=full_name,
        sex=form.cleaned_data.get('sex', ''),
        age=computed_age,
        date_of_birth=date_of_birth,
        phone_number=phone_number,
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
    _log_hazard_declaration_change(
        applicant=applicant,
        changed_by=request.user,
        declared_before=None,
        declared_after=is_danger_zone_answer,
        danger_zone_type_before='',
        danger_zone_type_after=danger_zone_type,
        danger_zone_location_before='',
        danger_zone_location_after=danger_zone_location,
        change_source='registration',
        notes='Initial hazard declaration captured during intake registration.',
    )

    # NOTE: CDRRMO certification will be created in Module 2 during screening (if danger zone claim is verified)

    # Process household members from form
    for i in range(1, 51):  # Support up to 50 household members
        name = request.POST.get(f'hh_member_{i}_name', '').strip()
        relationship = request.POST.get(f'hh_member_{i}_relationship', '').strip()
        age = request.POST.get(f'hh_member_{i}_age', '').strip()
        civil_status = request.POST.get(f'hh_member_{i}_status', 'single').strip()
        contact_number_raw = request.POST.get(f'hh_member_{i}_contact', '').strip()
        contact_number = re.sub(r'\D', '', contact_number_raw) if contact_number_raw else ''

        # Only create if at least name and relationship are provided
        if name and relationship:
            try:
                age_int = int(age) if age else 0
                if contact_number and (len(contact_number) != 11 or not contact_number.startswith('09')):
                    msg = f'Household Member {i}: contact number must be 11 digits and start with 09.'
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': msg})
                    messages.error(request, msg)
                    return redirect(applicants_list_url)
                from intake.models import HouseholdMember
                HouseholdMember.objects.create(
                    applicant=applicant,
                    full_name=name,
                    relationship=relationship,
                    age=age_int,
                    civil_status=civil_status,
                    contact_number=contact_number,
                )
            except (ValueError, TypeError):
                # Skip invalid age values
                pass

    # Step 7: Send registration SMS, confirming applicant was successfully recorded
    # (Module 2 will send additional SMS for eligibility decisions)
    applicant.send_registration_sms()

    msg = f'Successfully registered: {applicant.full_name} | Reference: {applicant.reference_number}'

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
