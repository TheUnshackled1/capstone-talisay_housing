from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, Prefetch
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from functools import wraps
from .models import Applicant, Barangay, Archive, SMSLog
from applications.models import QueueEntry
from documents.models import Document, Requirement
from .forms import (
    HouseholdMemberForm,
    WalkInApplicantForm
)
from .utils import send_sms
from . import sms_workflow
import json
import re
from collections import defaultdict
from django.utils.dateparse import parse_date

# Module 1 income ceiling (₱) — keep in sync with `Applicant.is_income_eligible` in intake/models.py
MODULE1_MONTHLY_INCOME_CEILING_PESO = 10000

# Module 1 residency eligibility threshold (years residing in Talisay City).
# Soft check only: applicants below this threshold are still allowed to register
# and submit. The flag is surfaced for downstream eligibility evaluation.
MODULE1_MIN_YEARS_RESIDING_TALISAY = 5

# Applicant Situation Options A/B/C need an extra vault slot (ISF situational documentation).
DISPLACEMENT_PATHS_NEED_ISF_EXTRA = frozenset({'danger_zone', 'ejected', 'relocated'})
ISF_EXTRA_VAULT_DOC_TYPE = 'isf_situational_docs'
VOTER_CERT_VAULT_DOC_TYPE = 'voter_certification'


def _archive_requirement_scan_rows(requirements_group_a, scanned_types_set, displacement_reason='', latest_doc_by_type=None):
    """
    Build checklist rows from `documents.Requirement` rows; `scanned` is True when this
    requirement's `vault_document_type` matches an uploaded Applicant Document.

    When displacement is Options A, B, or C, one extra trackable row is appended for
    `ISF_EXTRA_VAULT_DOC_TYPE` (Option D keeps the base count only).
    """
    scanned_types_set = scanned_types_set or set()
    latest_doc_by_type = latest_doc_by_type or {}
    rows = []
    for req in requirements_group_a:
        dtype = (getattr(req, 'vault_document_type', None) or '').strip()
        scanned = bool(dtype and dtype in scanned_types_set)
        latest_meta = latest_doc_by_type.get(dtype, {}) if dtype else {}
        rows.append({
            'code': req.code,
            'name': req.name,
            'group_display': req.get_group_display(),
            'is_required_for_form': req.is_required_for_form,
            'is_active': req.is_active,
            'scanned': scanned,
            'latest_file_url': latest_meta.get('url', ''),
            'latest_file_name': latest_meta.get('name', ''),
        })
    scanned_count = 0
    trackable_total = 0
    for req in requirements_group_a:
        dtype = (getattr(req, 'vault_document_type', None) or '').strip()
        if not dtype:
            continue
        trackable_total += 1
        if dtype in scanned_types_set:
            scanned_count += 1

    dr = (displacement_reason or '').strip()
    if dr in DISPLACEMENT_PATHS_NEED_ISF_EXTRA:
        scanned_isf = ISF_EXTRA_VAULT_DOC_TYPE in scanned_types_set
        latest_isf = latest_doc_by_type.get(ISF_EXTRA_VAULT_DOC_TYPE, {})
        rows.append({
            'code': 'ISF-SIT',
            'name': 'ISF situational documentation (A: Danger Zone/Hazard, B: Evicted, C: Government Project)',
            'group_display': 'Group A - Applicant Requirements',
            # Follow-up only: displayed in checklist but does not affect 7-doc proceed gate.
            'is_required_for_form': False,
            'is_active': True,
            'scanned': scanned_isf,
            'latest_file_url': latest_isf.get('url', ''),
            'latest_file_name': latest_isf.get('name', ''),
        })

    latest_voter = latest_doc_by_type.get(VOTER_CERT_VAULT_DOC_TYPE, {})
    rows.append({
        'code': 'RVT',
        'name': 'Voter Certification (COMELEC / Barangay voter record)',
        'group_display': 'Group A - Applicant Requirements',
        # Optional supporting evidence for the registered-voter eligibility check.
        'is_required_for_form': False,
        'is_active': True,
        'scanned': VOTER_CERT_VAULT_DOC_TYPE in scanned_types_set,
        'latest_file_url': latest_voter.get('url', ''),
        'latest_file_name': latest_voter.get('name', ''),
    })

    return rows, scanned_count, trackable_total


def _is_residency_eligible(years_residing):
    """Soft eligibility check for Talisay City residency tenure.

    Does NOT block intake. The result is exposed alongside the applicant
    payload so reviewers can see eligibility at a glance.
    """
    try:
        return int(years_residing or 0) >= MODULE1_MIN_YEARS_RESIDING_TALISAY
    except (TypeError, ValueError):
        return False


def _is_weak_hazard_location(raw_location):
    location = " ".join((raw_location or "").split()).strip().lower()
    if len(location) < 12:
        return True
    weak_values = {
        "n/a", "na", "none", "unknown", "same", "same as address",
        "same address", "barangay", "sitio", "landmark",
    }
    return location in weak_values


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
    elif applicant.archives.exists():
        location = 'Intake Archives (proceeded from registration list)'
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


@login_required
def duplicate_preview(request, position):
    """
    Lightweight pre-submit duplicate hint for intake form.
    Match basis: DOB + barangay + last name + first name (case-insensitive).
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'GET required'}, status=405)
    if request.user.position != position:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    date_of_birth_raw = (request.GET.get('date_of_birth') or '').strip()
    barangay_name = (request.GET.get('barangay') or '').strip()
    last_name = (request.GET.get('last_name') or '').strip()
    first_name = (request.GET.get('first_name') or '').strip()

    if not (date_of_birth_raw and barangay_name and last_name and first_name):
        return JsonResponse({'success': True, 'duplicate': False})

    date_of_birth = parse_date(date_of_birth_raw)
    if not date_of_birth:
        return JsonResponse({'success': True, 'duplicate': False})

    duplicate_applicant = (
        Applicant.objects
        .select_related('registered_by', 'barangay')
        .prefetch_related('requirement_submissions')
        .filter(
            date_of_birth=date_of_birth,
            barangay__name=barangay_name,
            last_name__iexact=last_name,
            first_name__iexact=first_name,
        )
        .order_by('-updated_at', '-created_at')
        .first()
    )
    if not duplicate_applicant:
        return JsonResponse({'success': True, 'duplicate': False})

    location, status_text = _describe_applicant_location(duplicate_applicant)
    handled_by = duplicate_applicant.registered_by.get_full_name() if duplicate_applicant.registered_by else 'Unknown'
    return JsonResponse({
        'success': True,
        'duplicate': True,
        'record_id': str(duplicate_applicant.id),
        'reference_number': duplicate_applicant.reference_number,
        'full_name': duplicate_applicant.full_name,
        'location': location,
        'status': status_text,
        'handled_by': handled_by,
        'can_open_in_intake': not duplicate_applicant.archives.exists(),
    })


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
                'Eligibility decisions were moved to Module 2 (Application & Eligibility). '
                'Use /applications/staff/<position>/ and click View.'
            ),
        }, status=400)
    
    elif action == 'disqualify':
        return JsonResponse({
            'success': False,
            'error': (
                'Disqualification decisions were moved to Module 2 (Application & Eligibility). '
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
        # Walk-in registrations start as `pending`; hazard claims may move to `pending_cdrrmo`.
        _intake_amendment_statuses = frozenset({'pending', 'pending_cdrrmo'})
        if applicant.status not in _intake_amendment_statuses:
            return JsonResponse({
                'success': False,
                'error': (
                    f'Amendments are only allowed while the record is pending intake review '
                    f'(current status: {applicant.get_status_display()}).'
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
        if years_residing is not None and str(years_residing).strip() != '':
            try:
                applicant.years_residing = int(years_residing)
            except (TypeError, ValueError):
                pass
        if phone_number:
            applicant.phone_number = phone_number
        if current_address:
            applicant.current_address = current_address

        voter_raw = (request.POST.get('is_registered_voter_talisay') or '').strip().lower()
        if voter_raw in ('yes', 'true', '1', 'on'):
            applicant.is_registered_voter_talisay = True
        elif voter_raw in ('no', 'false', '0', 'off'):
            applicant.is_registered_voter_talisay = False

        prop_raw = (request.POST.get('has_property_in_talisay') or '').strip().lower()
        if prop_raw in ('yes', 'true', '1'):
            applicant.has_property_in_talisay = True
        elif prop_raw in ('no', 'false', '0'):
            applicant.has_property_in_talisay = False

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

        # Update document checklist only for keys sent (Channel B save omits them — do not wipe).
        for field in doc_fields:
            if field in request.POST:
                setattr(applicant, field, request.POST.get(field) == 'true')

        applicant.save()

        new_danger_zone_type = (applicant.danger_zone_type or '').strip()
        new_danger_zone_location = (applicant.danger_zone_location or '').strip()
        new_declared = bool(new_danger_zone_type)
        if (
            old_declared != new_declared
            or old_danger_zone_type != new_danger_zone_type
            or old_danger_zone_location != new_danger_zone_location
        ):
            pass  # Audit trail removed - models deleted

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
@csrf_exempt
@require_POST
def upload_scanned_requirement(request, position):
    """
    Accepts scanner-uploaded file payloads and stores them in the central Document vault.
    Also mirrors checklist booleans on Applicant for backward-compatible UI counts.
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = (request.POST.get('applicant_id') or request.GET.get('applicant_id') or '').strip()
    doc_key = (request.POST.get('doc_key') or request.GET.get('doc_key') or '').strip()
    doc_code = (request.POST.get('doc_code') or request.GET.get('doc_code') or '').strip().upper()

    key_to_document_type = {
        'doc_brgy_residency': 'barangay_residency',
        'doc_brgy_indigency': 'barangay_indigency',
        'doc_cedula': 'cedula',
        'doc_police_clearance': 'police_clearance',
        'doc_no_property': 'no_property',
        'doc_2x2_picture': 'photo_2x2',
        'doc_sketch_location': 'house_sketch',
        'doc_isf_situational': 'isf_situational_docs',
        'doc_voter_cert': 'voter_certification',
    }

    if not applicant_id or doc_key not in key_to_document_type:
        return JsonResponse({'success': False, 'error': 'Missing or invalid applicant/document mapping.'}, status=400)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file and request.FILES:
        uploaded_file = next(iter(request.FILES.values()))
    if not uploaded_file:
        return JsonResponse({'success': False, 'error': 'No scanned file payload received.'}, status=400)

    try:
        applicant = Applicant.objects.get(id=applicant_id)
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found.'}, status=404)

    document_type = key_to_document_type[doc_key]
    label_map = dict(Document.DOCUMENT_TYPE_CHOICES)
    doc_title = f"{applicant.full_name} - {label_map.get(document_type, document_type)}"

    doc, created = Document.objects.update_or_create(
        applicant=applicant,
        document_type=document_type,
        defaults={
            'title': doc_title,
            'file': uploaded_file,
            'file_name': uploaded_file.name,
            'file_size': uploaded_file.size,
            'mime_type': getattr(uploaded_file, 'content_type', '') or '',
            'uploaded_by': request.user,
        },
    )

    if hasattr(applicant, doc_key):
        setattr(applicant, doc_key, True)
        applicant.save(update_fields=[doc_key])

    return JsonResponse({
        'success': True,
        'message': 'Scanned file saved to vault.',
        'document_id': str(doc.id),
        'created': created,
        'doc_code': doc_code,
        'doc_type': document_type,
        'document_url': doc.file.url if getattr(doc, 'file', None) else '',
        'document_name': doc.file_name or (uploaded_file.name if uploaded_file else ''),
    })


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
            if not record.archives.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'SMS for this type is only allowed after the record is proceeded to Archives.',
                })
            handoff_message = sms_workflow.message_proceed_to_evaluation(record)
            sent = send_sms(
                record.phone_number,
                handoff_message,
                sms_workflow.PROCEED_TO_EVALUATION,
                applicant=record,
            )
            if not sent:
                return JsonResponse({'success': False, 'error': 'Failed to send SMS'})
            record.registration_sms_sent = True
            record.save(update_fields=['registration_sms_sent', 'updated_at'])
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
 
    if request.user.position not in ['second_member', 'fourth_member']:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    if applicant.status == 'disqualified':
        return JsonResponse({'success': False, 'error': 'Disqualified records cannot be archived.'}, status=400)
    promote_to_module2 = str(request.POST.get('promote_to_module2', '')).strip().lower() in {'1', 'true', 'yes', 'on'}

    with transaction.atomic():
        # Intake Archives receipt.
        archive_record, created = Archive.objects.get_or_create(
            applicant=applicant,
            defaults={
                'reference_number_snapshot': applicant.reference_number,
                'full_name_snapshot': applicant.full_name,
                'last_name_snapshot': applicant.last_name,
                'first_name_snapshot': applicant.first_name,
                'middle_name_snapshot': applicant.middle_name,
                'extension_name_snapshot': applicant.extension_name,
                'date_of_birth_snapshot': applicant.date_of_birth,
                'channel': _map_applicant_channel_to_archive(applicant),
                'barangay_name_snapshot': applicant.barangay.name if applicant.barangay else '',
                'sms_sent': applicant.registration_sms_sent,
                'cdrrmo_certified': bool(getattr(applicant, 'cdrrmo_certification', None) and applicant.cdrrmo_certification.status == 'certified'),
                'archived_by': request.user,
            }
        )
        # Optional promotion path used by the archive checklist CTA:
        # once baseline R01-R07 are complete, mark as handed off for Module 2 list visibility.
        if promote_to_module2 and applicant.module2_handoff_at is None:
            applicant.module2_handoff_at = timezone.now()
            applicant.module2_handoff_by = request.user
            applicant.save(update_fields=['module2_handoff_at', 'module2_handoff_by', 'updated_at'])

    return JsonResponse({
        'success': True,
        'message': (
            f'Applicant {applicant.reference_number} moved to Application & Eligibility.'
            if promote_to_module2
            else f'Applicant {applicant.reference_number} moved to Archives.'
        ),
        'created': created,
        'promoted_to_module2': bool(promote_to_module2),
    })


def _map_applicant_channel_to_archive(applicant):
    """Map applicant channel to archive channel."""
    channel_value = applicant.channel
    if channel_value == 'walk_in':
        return 'channel_a'
    elif channel_value == 'danger_zone':
        return 'channel_b_hazard' if (applicant.danger_zone_type or '').strip() else 'channel_b_no_hazard'
    elif channel_value == 'landowner':
        return 'channel_c'
    else:
        return channel_value


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
    # - OIC: View only - oversight access
    allowed_positions = ['second_member', 'fourth_member', 'field', 'ronda', 'oic']
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
        
        local_created_at = timezone.localtime(isf.created_at)
        applicants.append({
            'id': str(isf.id),
            'fullName': isf.full_name,
            'referenceNumber': isf.reference_number,
            'dateRegistered': local_created_at.strftime('%Y-%m-%d'),
            'dateTime': local_created_at.strftime('%b %d, %Y | %I:%M %p'),
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
            'residencyEligible': _is_residency_eligible(isf.years_residing),
            'minYearsResidingTalisay': MODULE1_MIN_YEARS_RESIDING_TALISAY,
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
    # Active "Total List": applicants not yet in Intake Archives (proceed button creates Archive only).
    walk_in_applicants = Applicant.objects.filter(
        archives__isnull=True,
    ).select_related(
        'barangay', 'eligibility_checked_by', 'registered_by'
    ).prefetch_related(
        Prefetch(
            'queue_entries',
            queryset=QueueEntry.objects.filter(status='active'),
            to_attr='active_queue',
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
            # CDRRMO model has been removed from intake app
            cdrrmo_status = 'Not Requested'
            cdrrmo_status_value = None
            cdrrmo_disposition_source = 'pending'

        local_created_at = timezone.localtime(app.created_at)
        applicants.append({
            'id': str(app.id),
            'fullName': app.full_name,
            'referenceNumber': app.reference_number,
            'dateRegistered': local_created_at.strftime('%Y-%m-%d'),
            'dateTime': local_created_at.strftime('%b %d, %Y | %I:%M %p'),
            'dateOfBirthDisplay': app.date_of_birth.strftime('%m/%d/%Y') if app.date_of_birth else '',
            'channel': 'B' if app.channel == 'danger_zone' else 'C',  # Map database channels to UI channels
            'submissionId': None,
            'applicantId': str(app.id),
            # Section A: APPLICATION IDENTITY
            'lastName': app.last_name or '',
            'firstName': app.first_name or '',
            'middleName': app.middle_name or '',
            'extensionName': app.extension_name or '',
            'sex': app.sex or '',
            'isRegisteredVoterTalisay': bool(app.is_registered_voter_talisay),
            'hasPropertyInTalisay': bool(app.has_property_in_talisay),
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
            # Soft residency eligibility (≥ MODULE1_MIN_YEARS_RESIDING_TALISAY years).
            # Not a hard block at intake — surfaced here for reviewer visibility.
            'residencyEligible': _is_residency_eligible(app.years_residing),
            'minYearsResidingTalisay': MODULE1_MIN_YEARS_RESIDING_TALISAY,
            'occupation': app.occupation or '',
            'employmentStatus': app.get_employment_status_display() if app.employment_status else '',
            # Danger Zone details
            'isInDangerZone': app.channel == 'danger_zone' and bool(app.danger_zone_type),
            'dangerZoneType': app.danger_zone_type if hasattr(app, 'danger_zone_type') and app.danger_zone_type else '',
            'dangerZoneLocation': app.danger_zone_location if hasattr(app, 'danger_zone_location') and app.danger_zone_location else (danger_zone_type or ''),
            # Applicant Situation (A, B, C, D) and specific details
            'displacementReason': (app.displacement_reason or '').strip(),
            'ejectionType': (app.ejection_type or '').strip() if hasattr(app, 'ejection_type') else '',
            'ejectionDate': app.ejection_date.isoformat() if hasattr(app, 'ejection_date') and app.ejection_date else '',
            'projectName': (app.project_name or '').strip() if hasattr(app, 'project_name') else '',
            'eligibilityStatus': eligibility_status,
            'applicantStatus': app.status,
            # Legacy JSON keys — "Module 2" here means ready to proceed to Intake Archives / not disqualified.
            'readyForModule2': app.status != 'disqualified',
            'module2HandedOff': False,
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

    # Read-only archive/receipt rows (proceed from modal creates Archive; no Module 2 handoff on Applicant).
    # Query Archive model for snapshot data
    archive_records = []
    archives = list(
        Archive.objects.filter(
            applicant__module2_handoff_at__isnull=True,
        ).select_related(
            'archived_by',
            'applicant',
            'applicant__application__form_generated_by',
        ).order_by('archived_at')
    )

    applicant_ids_for_docs = [a.applicant_id for a in archives if a.applicant_id]
    docs_by_applicant_id = defaultdict(set)
    latest_doc_meta_by_applicant_id = defaultdict(dict)
    if applicant_ids_for_docs:
        for aid, doc_type in Document.objects.filter(
            applicant_id__in=applicant_ids_for_docs,
        ).values_list('applicant_id', 'document_type'):
            docs_by_applicant_id[aid].add(doc_type)
        latest_docs = (
            Document.objects.filter(applicant_id__in=applicant_ids_for_docs)
            .exclude(file='')
            .order_by('applicant_id', 'document_type', '-uploaded_at')
        )
        for doc in latest_docs:
            dtype = (doc.document_type or '').strip()
            if not dtype:
                continue
            slot = latest_doc_meta_by_applicant_id[doc.applicant_id]
            if dtype in slot:
                continue
            try:
                file_url = request.build_absolute_uri(doc.file.url)
            except (ValueError, AttributeError):
                file_url = ''
            slot[dtype] = {
                'url': file_url,
                'name': (doc.file_name or doc.title or doc.get_document_type_display() or '').strip(),
            }

    requirements_group_a = list(Requirement.objects.filter(group='A').order_by('order', 'code'))

    channel_display_map = {
        'channel_a': ('A', 'Channel A — Walk-in'),
        'channel_b_no_hazard': ('B', 'Channel B — No hazard (No)'),
        'channel_b_hazard': ('B', 'Channel B — Hazard (Yes)'),
        'channel_c': ('C', 'Channel C — Landowner'),
    }

    for archive in archives:
        channel_code, channel_label = channel_display_map.get(archive.channel, ('?', archive.channel))

        # Convert UTC time to Manila time for display
        local_archived_at = timezone.localtime(archive.archived_at) if archive.archived_at else None

        module3_summary = 'Not yet proceeded beyond Archives'
        module3_proceeded_at = ''
        module3_proceeded_by = ''
        module3_application_number = ''
        if archive.applicant_id and hasattr(archive.applicant, 'application'):
            app_obj = getattr(archive.applicant, 'application', None)
            if app_obj and app_obj.form_generated_at:
                local_form_generated_at = timezone.localtime(app_obj.form_generated_at)
                module3_proceeded_at = local_form_generated_at.strftime('%Y-%m-%d %I:%M %p')
                module3_proceeded_by = app_obj.form_generated_by.get_full_name() if app_obj.form_generated_by else 'Unknown'
                module3_application_number = app_obj.application_number or ''
                module3_summary = f"Application #{module3_application_number} • {module3_proceeded_at}"

        applicant_phone = ''
        if archive.applicant_id and archive.applicant:
            applicant_phone = (archive.applicant.phone_number or '').strip()
        has_phone = bool(applicant_phone)
        sms_sent_state = bool(archive.sms_sent)
        if archive.applicant_id and archive.applicant:
            sms_sent_state = bool(archive.applicant.registration_sms_sent)

        scanned_types = docs_by_applicant_id.get(archive.applicant_id, set()) if archive.applicant_id else set()
        disp_snapshot = ''
        if archive.applicant_id and archive.applicant:
            disp_snapshot = (archive.applicant.displacement_reason or '').strip()
        requirement_scan_rows, scanned_count, trackable_total = _archive_requirement_scan_rows(
            requirements_group_a,
            scanned_types,
            displacement_reason=disp_snapshot,
            latest_doc_by_type=latest_doc_meta_by_applicant_id.get(archive.applicant_id, {}),
        )
        requirements_total = trackable_total if trackable_total > 0 else max(len(requirement_scan_rows), 1)

        archive_records.append({
            'id': str(archive.id),
            'dateTime': local_archived_at.strftime('%b %d, %Y | %I:%M %p') if local_archived_at else '',
            'dateOfBirthDisplay': archive.date_of_birth_snapshot.strftime('%m/%d/%Y') if archive.date_of_birth_snapshot else '',
            'referenceNumber': archive.reference_number_snapshot,
            'fullName': archive.full_name_snapshot,
            'lastName': archive.last_name_snapshot or '',
            'firstName': archive.first_name_snapshot or '',
            'middleName': archive.middle_name_snapshot or '',
            'extensionName': archive.extension_name_snapshot or '',
            'barangay': archive.barangay_name_snapshot,
            'channel': channel_code,
            'channelLabel': channel_label,
            'handledBy': archive.archived_by.get_full_name() if archive.archived_by else 'Unknown',
            'handledByPosition': archive.archived_by.get_position_display_short() if archive.archived_by else '',
            'handledByInitials': (archive.archived_by.first_name[:1] + archive.archived_by.last_name[:1]).upper() if archive.archived_by else '??',
            'registrationSmsSent': sms_sent_state,
            'hasPhone': has_phone,
            'handoffAt': local_archived_at.strftime('%Y-%m-%d %I:%M %p') if local_archived_at else '',
            'handoffBy': archive.archived_by.get_full_name() if archive.archived_by else '',
            'module2Summary': f"{archive.reference_number_snapshot} • {archive.full_name_snapshot}",
            'module3Summary': module3_summary,
            'module3ProceededAt': module3_proceeded_at,
            'module3ProceededBy': module3_proceeded_by,
            'module3ApplicationNumber': module3_application_number,
            'requirementScanRows': requirement_scan_rows,
            'scannedCount': scanned_count,
            'requirementsTotal': requirements_total,
            'applicantId': str(archive.applicant_id) if archive.applicant_id else '',
        })

    archive_documents_modal = {
        r['referenceNumber']: {
            'referenceNumber': r['referenceNumber'],
            'fullName': r['fullName'],
            'applicantId': r.get('applicantId', ''),
            'rows': r['requirementScanRows'],
        }
        for r in archive_records
    }

    archive_form_modal = {}
    for archive in archives:
        ref = archive.reference_number_snapshot or ''
        applicant = getattr(archive, 'applicant', None)
        if not ref or not applicant:
            continue

        displacement_reason = (applicant.displacement_reason or '').strip()
        displacement_map = {
            'danger_zone': (
                'Option A',
                'Resident of Danger Zone or Hazard Area',
                'Applicant resides in a flood-prone, landslide, storm-surge, riverbank, cliff-edge, or coastal hazard area requiring relocation for safety.',
            ),
            'ejected': (
                'Option B',
                'Ejected or Evicted from Prior Residence',
                'Applicant has been evicted or displaced through private land eviction, court order, landowner recovery, or analogous proceedings.',
            ),
            'relocated': (
                'Option C',
                'Displaced by Government Project or Infrastructure',
                'Applicant is required to relocate due to a road-widening, drainage, infrastructure, or other government-initiated project.',
            ),
            'not_abc': (
                'Option D',
                'None of A, B, or C (Other / not listed)',
                'The situation does not fall under a hazard area, ejection, or a government project. The applicant is recorded for the Walk-in path (no Priority on this ground).',
            ),
        }
        disp_label, disp_title, disp_desc = displacement_map.get(
            displacement_reason,
            ('N/A', 'Not recorded', 'Applicant situation has not been recorded.'),
        )

        archive_form_modal[ref] = {
            'fullName': archive.full_name_snapshot or '',
            'referenceNumber': ref,
            'dateRegistered': timezone.localtime(archive.archived_at).strftime('%Y-%m-%d') if archive.archived_at else '',
            'lastName': archive.last_name_snapshot or '',
            'firstName': archive.first_name_snapshot or '',
            'middleName': archive.middle_name_snapshot or '',
            'extensionName': archive.extension_name_snapshot or '',
            'sex': applicant.sex or '',
            'age': applicant.age,
            'dateOfBirthDisplay': archive.date_of_birth_snapshot.strftime('%m/%d/%Y') if archive.date_of_birth_snapshot else '',
            'isRegisteredVoter': applicant.is_registered_voter_talisay,
            'currentAddress': applicant.current_address or '',
            'barangay': archive.barangay_name_snapshot or '',
            'phoneNumber': applicant.phone_number or '',
            'yearsResiding': applicant.years_residing,
            'householdSize': applicant.household_size,
            'occupation': applicant.occupation or '',
            'employmentStatus': applicant.get_employment_status_display() if applicant.employment_status else '',
            'monthlyIncome': str(applicant.monthly_income or ''),
            'displacementOptionLabel': disp_label,
            'displacementTitle': disp_title,
            'displacementDescription': disp_desc,
        }
    
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
        'page_title': 'ISF Registration',
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
        'archive_documents_modal': archive_documents_modal,
        'archive_form_modal': json.dumps(archive_form_modal),
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
    # Radio may send various formats; normalize to yes/no for TypedChoiceField.
    voter_raw = (post_data.get('is_registered_voter_talisay') or '').strip().lower()
    if voter_raw in ('yes', '1', 'on', 'true'):
        post_data['is_registered_voter_talisay'] = 'yes'
    elif voter_raw in ('no', '0', 'off', 'false'):
        post_data['is_registered_voter_talisay'] = 'no'
    form = WalkInApplicantForm(post_data)

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

    # Applicant Situation (Options A–D) and particulars — validated in WalkInApplicantForm.clean().
    dr_reg = (form.cleaned_data.get('displacement_reason') or '').strip()
    if dr_reg == 'danger_zone':
        danger_zone_type = (form.cleaned_data.get('danger_zone_type') or '').strip()
        danger_zone_location = (form.cleaned_data.get('danger_zone_location') or '').strip()
    else:
        danger_zone_type = ''
        danger_zone_location = ''

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
        is_registered_voter_talisay=bool(form.cleaned_data.get('is_registered_voter_talisay')),
        occupation=form.cleaned_data.get('occupation', ''),
        employment_status=form.cleaned_data.get('employment_status', ''),
        has_property_in_talisay=(form.cleaned_data.get('has_property_in_talisay') == 'yes'),
        channel='danger_zone',
        status=initial_status,
        displacement_reason=dr_reg,
        danger_zone_type=danger_zone_type,
        danger_zone_location=danger_zone_location,
        ejection_type=(form.cleaned_data.get('ejection_type') or '').strip()
        if dr_reg == 'ejected' else '',
        ejection_date=form.cleaned_data.get('ejection_date')
        if dr_reg == 'ejected' else None,
        project_name=(form.cleaned_data.get('project_name') or '').strip()
        if dr_reg == 'relocated' else '',
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

    # No SMS on registration.
    # Policy: first applicant-facing SMS is sent when staff proceeds record to Module 2.

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
                'extensionName': applicant.extension_name,
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
                'residencyEligible': _is_residency_eligible(applicant.years_residing),
                'minYearsResidingTalisay': MODULE1_MIN_YEARS_RESIDING_TALISAY,
                'isRegisteredVoterTalisay': bool(applicant.is_registered_voter_talisay),
                'phoneNumber': applicant.phone_number,
                'currentAddress': applicant.current_address,
                'dangerZoneType': applicant.danger_zone_type,
                'dangerZoneLocation': applicant.danger_zone_location,
                'isInDangerZone': dr_reg == 'danger_zone',
                'documents': documents_submitted,
                'docsCount': f"{docs_count}/7",
            }
        })

    messages.success(request, f'✓ {msg}')
    return redirect(applicants_list_url)


@login_required
def archive_list(request, position):
    """
    Display Intake Archive receipts (records proceeded from the registration list).
    URL: /intake/staff/<position>/archive/
    """
    from django.core.paginator import Paginator

    # Get filters from query parameters
    selected_channel = request.GET.get('channel', '')
    selected_barangay = request.GET.get('barangay', '')
    search_query = (request.GET.get('q') or '').strip()

    # Build query
    archives_qs = Archive.objects.select_related(
        'applicant',
        'archived_by',
        'applicant__application__form_generated_by',
    ).order_by('archived_at')

    if selected_channel:
        archives_qs = archives_qs.filter(channel=selected_channel)

    if selected_barangay:
        archives_qs = archives_qs.filter(barangay_name_snapshot=selected_barangay)
    if search_query:
        archives_qs = archives_qs.filter(
            Q(full_name_snapshot__icontains=search_query) |
            Q(reference_number_snapshot__icontains=search_query) |
            Q(barangay_name_snapshot__icontains=search_query)
        )

    # Get unique channels and barangays for filters
    channel_choices = {
        'channel_a': 'Channel A — Walk-in',
        'channel_b_no_hazard': 'Channel B — No hazard',
        'channel_b_hazard': 'Channel B — Hazard',
        'channel_c': 'Channel C — Landowner',
    }

    barangays = Archive.objects.values_list('barangay_name_snapshot', flat=True).distinct().order_by('barangay_name_snapshot')
    barangays = [b for b in barangays if b]  # Remove empty values

    applicant_ids_for_docs = list(
        archives_qs.exclude(applicant_id__isnull=True).values_list('applicant_id', flat=True)
    )
    docs_by_applicant_id = defaultdict(set)
    if applicant_ids_for_docs:
        for aid, doc_type in Document.objects.filter(
            applicant_id__in=applicant_ids_for_docs,
        ).values_list('applicant_id', 'document_type'):
            docs_by_applicant_id[aid].add(doc_type)
    requirements_group_a = list(Requirement.objects.filter(group='A').order_by('order', 'code'))

    # Prepare records for template
    records = []
    for archive in archives_qs:
        staff_user = archive.archived_by
        staff_name = staff_user.get_full_name() if staff_user else '—'
        staff_position_val = getattr(staff_user, 'position', None)
        if staff_position_val:
            staff_position_display = staff_user.get_position_display_short() if hasattr(staff_user, 'get_position_display_short') else staff_position_val
        else:
            staff_position_display = '—'

        staff_initials = staff_user.first_name[:1] + staff_user.last_name[:1] if staff_user else '—'
        channel_display = channel_choices.get(archive.channel, archive.channel)

        # Convert to local timezone for display
        local_archived_at = timezone.localtime(archive.archived_at)
        date_time_display = local_archived_at.strftime('%b %d, %Y | %I:%M %p')
        handoff_at_detail = local_archived_at.strftime('%Y-%m-%d %I:%M %p')

        # Get DOB display
        dob_display = archive.date_of_birth_snapshot.strftime('%m/%d/%Y') if archive.date_of_birth_snapshot else 'N/A'

        scanned_types = docs_by_applicant_id.get(archive.applicant_id, set()) if archive.applicant_id else set()
        disp_snapshot = ''
        if archive.applicant_id and archive.applicant:
            disp_snapshot = (archive.applicant.displacement_reason or '').strip()
        requirement_scan_rows, scanned_count, trackable_total = _archive_requirement_scan_rows(
            requirements_group_a,
            scanned_types,
            displacement_reason=disp_snapshot,
        )
        requirements_total = trackable_total if trackable_total > 0 else max(len(requirement_scan_rows), 1)

        module3_summary = 'Not yet proceeded beyond Archives'
        module3_proceeded_at = ''
        module3_proceeded_by = ''
        if archive.applicant_id and hasattr(archive.applicant, 'application'):
            app_obj = getattr(archive.applicant, 'application', None)
            if app_obj and app_obj.form_generated_at:
                local_form_generated_at = timezone.localtime(app_obj.form_generated_at)
                module3_proceeded_at = local_form_generated_at.strftime('%Y-%m-%d %I:%M %p')
                module3_proceeded_by = app_obj.form_generated_by.get_full_name() if app_obj.form_generated_by else 'Unknown'
                module3_summary = f"Application #{app_obj.application_number} • {module3_proceeded_at}"

        sms_text = 'No Phone'
        if bool(archive.applicant.phone_number if archive.applicant else False):
            sms_text = 'Sent' if archive.sms_sent else 'Not Sent'

        records.append({
            'id': str(archive.id),
            'dateTime': date_time_display,
            'handoffAt': handoff_at_detail,
            'referenceNumber': archive.reference_number_snapshot,
            'fullName': archive.full_name_snapshot,
            'lastName': archive.last_name_snapshot,
            'firstName': archive.first_name_snapshot,
            'middleName': archive.middle_name_snapshot,
            'extensionName': archive.extension_name_snapshot,
            'channel': archive.channel,
            'channelLabel': channel_display,
            'handledBy': staff_name,
            'handledByPosition': staff_position_display,
            'handledByInitials': staff_initials,
            'handoffBy': staff_name,
            'registrationSmsSent': archive.sms_sent,
            'hasPhone': bool(archive.applicant.phone_number if archive.applicant else False),
            'smsText': sms_text,
            'dateOfBirthDisplay': dob_display,
            'barangay': archive.barangay_name_snapshot,
            'scannedCount': scanned_count,
            'requirementsTotal': requirements_total,
            'module2Summary': f"{archive.reference_number_snapshot} • {archive.full_name_snapshot}",
            'module3Summary': module3_summary,
            'module3ProceededAt': module3_proceeded_at,
            'module3ProceededBy': module3_proceeded_by,
        })

    # Pagination
    paginator = Paginator(records, 10)  # 10 records per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Archive Records',
        'staff_position': position,
        'position': position,
        'total_archived': archives_qs.count(),
        'channels': channel_choices,
        'selected_channel': selected_channel,
        'barangays': barangays,
        'selected_barangay': selected_barangay,
        'archive_records': page_obj.object_list,
        'page_obj': page_obj,
    }

    return render(request, 'intake/archive_list.html', context)
