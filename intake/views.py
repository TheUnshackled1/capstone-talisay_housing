from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, Prefetch, Exists, OuterRef
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from functools import wraps
from urllib.parse import urlencode
from .models import Applicant, Barangay, Archive, SMSLog
from applications.staff_pipeline_status import (
    archive_applicant_status,
    archive_stage_filter_key,
    ARCHIVE_STAGE_FILTER_CHOICES,
)
from applications.form_pipeline import applicant_has_signed_application_payload
from applications.models import QueueEntry
from units.models import LotAward, Blacklist
from units.historical_beneficiary import (
    applicant_excluded_from_intake_registration,
    intake_registration_exclude_q,
)
from documents.models import Document, Requirement, document_filed_via_display, upsert_document_vault_upload
from .forms import (
    HouseholdMemberForm,
    WalkInApplicantForm
)
import json
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)
from django.utils.dateparse import parse_date
from .utils import send_sms
from . import sms_workflow
from applications.utils import check_blacklist_module2

# Module 1 income ceiling (₱) — keep in sync with `Applicant.is_income_eligible` in intake/models.py
MODULE1_MONTHLY_INCOME_CEILING_PESO = 10000


def _intake_module2_blacklist_check_payload(applicant):
    """Flags for Intake document checklist — block proceed when on Units blacklist."""
    empty = {
        'blacklistBlocked': False,
        'blacklistReason': '',
        'blacklistRegistryName': '',
        'blacklistRegistryRef': '',
    }
    if not applicant:
        return empty
    is_bl, bl_entry = check_blacklist_module2(
        applicant.full_name,
        applicant.phone_number or None,
        applicant_id=applicant.id,
        last_name=applicant.last_name,
        first_name=applicant.first_name,
        date_of_birth=applicant.date_of_birth,
        barangay_id=applicant.barangay_id,
    )
    if not is_bl:
        return empty
    reason_label = bl_entry.get_reason_display() if bl_entry else 'Blacklist match'
    registry_applicant = None
    if bl_entry is not None and getattr(bl_entry, '_entry', None) is not None:
        registry_applicant = getattr(bl_entry._entry, 'applicant', None)
    registry_name = (registry_applicant.full_name if registry_applicant else applicant.full_name) or ''
    registry_ref = (registry_applicant.reference_number if registry_applicant else applicant.reference_number) or ''
    return {
        'blacklistBlocked': True,
        'blacklistReason': reason_label,
        'blacklistRegistryName': registry_name,
        'blacklistRegistryRef': registry_ref,
    }

# Module 1 residency eligibility threshold (years residing in Talisay City).
# Soft check only: applicants below this threshold are still allowed to register
# and submit. The flag is surfaced for downstream eligibility evaluation.
MODULE1_MIN_YEARS_RESIDING_TALISAY = 5
MODULE1_MAX_YEARS_RESIDING_TALISAY = 99


def _parse_years_residing(raw):
    """Normalize years residing to 0–99 (2 digits). Returns None if empty/invalid."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    digits = re.sub(r'\D', '', text)[:2]
    if not digits:
        return None
    return max(0, min(MODULE1_MAX_YEARS_RESIDING_TALISAY, int(digits)))


def _relative_time_ago(dt):
    """
    Short relative labels from registration datetime to now (e.g. Just now, 2 hours ago, 1 day ago).
    """
    if dt is None:
        return '—'
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    secs = int((now - dt).total_seconds())
    if secs < 60:
        return 'Just now'
    mins = secs // 60
    if mins < 60:
        return f'{mins} minute{"s" if mins != 1 else ""} ago'
    hours = mins // 60
    if hours < 24:
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    days = hours // 24
    if days < 7:
        return f'{days} day{"s" if days != 1 else ""} ago'
    weeks = days // 7
    if days < 60:
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    months = days // 30
    if months < 12:
        m = max(months, 1)
        return f'{m} month{"s" if m != 1 else ""} ago'
    years = days // 365
    y = max(years, 1)
    return f'{y} year{"s" if y != 1 else ""} ago'

# Applicant Situation Options A/B/C need one extra situational vault slot.
DISPLACEMENT_PATHS_NEED_ISF_EXTRA = frozenset({'danger_zone', 'ejected', 'relocated'})
ISF_EXTRA_VAULT_DOC_TYPE = 'isf_situational_docs'
CDRRMO_EXTRA_VAULT_DOC_TYPE = 'cdrrmo_cert'

# Mirrors `upload_scanned_requirement` — vault row satisfies checklist whether filed via Upload or Scan.
APPLICANT_DOC_KEY_TO_VAULT_TYPE = {
    'doc_brgy_residency': 'barangay_residency',
    'doc_brgy_indigency': 'barangay_indigency',
    'doc_cedula': 'cedula',
    'doc_police_clearance': 'police_clearance',
    'doc_no_property': 'no_property',
    'doc_2x2_picture': 'photo_2x2',
    'doc_sketch_location': 'house_sketch',
    'doc_isf_situational': ISF_EXTRA_VAULT_DOC_TYPE,
    'doc_voter_cert': 'voter_certification',
    'doc_cdrrmo': CDRRMO_EXTRA_VAULT_DOC_TYPE,
    'doc_signed_application': 'signed_application',
}


def _applicant_vault_document_types(applicant):
    return set(
        Document.objects.filter(applicant_id=applicant.pk)
        .exclude(document_type='')
        .values_list('document_type', flat=True)
    )


def _sync_applicant_doc_flags_from_vault(applicant, scanned_types=None):
    """Keep legacy boolean checklist fields aligned with vault (upload or scan)."""
    scanned_types = scanned_types if scanned_types is not None else _applicant_vault_document_types(applicant)
    update_fields = []
    for doc_key, vault_type in APPLICANT_DOC_KEY_TO_VAULT_TYPE.items():
        if vault_type not in scanned_types:
            continue
        if hasattr(applicant, doc_key) and not getattr(applicant, doc_key):
            setattr(applicant, doc_key, True)
            update_fields.append(doc_key)
    if update_fields:
        update_fields.append('updated_at')
        applicant.save(update_fields=update_fields)


def _latest_doc_meta_by_type_for_applicant(applicant, request):
    latest_doc_by_type = {}
    latest_docs = (
        Document.objects.filter(applicant_id=applicant.pk)
        .with_file_payload()
        .select_related('blob_record')
        .order_by('document_type', '-uploaded_at')
    )
    for doc in latest_docs:
        dtype = (doc.document_type or '').strip()
        if not dtype or dtype in latest_doc_by_type:
            continue
        try:
            doc_url = doc.absolute_download_url(request)
        except (ValueError, AttributeError):
            doc_url = ''
        if not doc_url:
            continue
        capture_method = (doc.capture_method or '').strip()
        latest_doc_by_type[dtype] = {
            'url': doc_url,
            'name': (doc.file_name or doc.title or doc.get_document_type_display() or '').strip(),
            'capture_method': capture_method,
            'filed_via': capture_method,
            'filed_via_label': document_filed_via_display(capture_method),
        }
    return latest_doc_by_type


def _build_applicant_requirement_scan_payload(applicant, request):
    """Live checklist rows: `scanned` when vault has the requirement (upload or scan)."""
    scanned_types = _applicant_vault_document_types(applicant)
    _sync_applicant_doc_flags_from_vault(applicant, scanned_types)
    latest_doc_by_type = _latest_doc_meta_by_type_for_applicant(applicant, request)
    displacement_reason = (applicant.displacement_reason or '').strip()
    requirements_group_a = list(Requirement.objects.filter(group='A').order_by('order', 'code'))
    rows, scanned_count, trackable_total = _archive_requirement_scan_rows(
        requirements_group_a,
        scanned_types,
        displacement_reason=displacement_reason,
        latest_doc_by_type=latest_doc_by_type,
    )
    required_rows = [row for row in rows if row.get('is_required_for_form')]
    scanned_required = sum(1 for row in required_rows if row.get('scanned'))
    bl_gate = _intake_module2_blacklist_check_payload(applicant)
    return {
        'success': True,
        'rows': rows,
        'scannedCount': scanned_count,
        'trackableTotal': trackable_total,
        'requiredScannedCount': scanned_required,
        'requiredTotal': len(required_rows),
        'vaultDocumentTypes': sorted(scanned_types),
        'applicantId': str(applicant.pk),
        'referenceNumber': applicant.reference_number or '',
        'fullName': applicant.full_name or '',
        'displacementReason': displacement_reason,
        **bl_gate,
    }


def _archive_list_status_label_and_tier(scanned_count, requirements_total, blacklist_blocked=False):
    """
    LIST OF APPLICANTS — Status column.

    When blacklisted, docs may be Complete but proceed to Module 2 is blocked → Cannot proceed.
    """
    if blacklist_blocked:
        return 'Cannot proceed', 'blocked'
    return _requirements_filing_status_label_and_tier(scanned_count, requirements_total)


def _requirements_filing_status_label_and_tier(scanned_count, requirements_total):
    """
    LIST OF APPLICANTS — Status tracks the same Applicant requirements scan checklist as Documents.

    Pending: no requirement scans filed yet. Incomplete: some filed but not all. Complete: all filed.
    """
    try:
        total = int(requirements_total)
    except (TypeError, ValueError):
        total = 0
    try:
        scanned = int(scanned_count)
    except (TypeError, ValueError):
        scanned = 0
    if total <= 0:
        return 'Pending', 'pending'
    if scanned >= total:
        return 'Complete', 'complete'
    if scanned > 0:
        return 'Incomplete', 'incomplete'
    return 'Pending', 'pending'


def _archive_list_name_class_for_displacement(displacement_reason):
    """CSS suffix for LIST OF APPLICANTS full name — matches Application & Evaluation ledger (.option-a … .option-d)."""
    dr = (displacement_reason or '').strip()
    if dr == 'danger_zone':
        return 'option-a'
    if dr == 'ejected':
        return 'option-b'
    if dr == 'relocated':
        return 'option-c'
    if dr == 'not_abc':
        return 'option-d'
    return ''


def _isf_situational_row_display_name(displacement_reason=''):
    """
    Human-facing checklist row title for situational follow-up docs.
    """
    dr = (displacement_reason or '').strip()
    if dr == 'danger_zone':
        return 'Resident of Danger Zone or Hazard Area Follow-up'
    if dr == 'ejected':
        return 'Ejected or Evicted from Prior Residence Follow-up'
    if dr == 'relocated':
        return 'Displaced by Government Project or Infrastructure Follow-up'
    return 'ISF situational documentation Follow-up'


def _isf_situational_policy_tooltip(displacement_reason=''):
    """Long description for checklist tooltips (Applicant Situation A/B/C)."""
    dr = (displacement_reason or '').strip()
    if dr == 'danger_zone':
        return (
            'Applicant resides in a flood-prone, landslide, storm-surge, riverbank, cliff-edge, '
            'or coastal hazard area requiring relocation for safety.'
        )
    if dr == 'ejected':
        return (
            'Applicant has been evicted or displaced through private land eviction, court order, '
            'landowner recovery, or analogous proceedings.'
        )
    if dr == 'relocated':
        return (
            'Applicant is required to relocate due to a road-widening, drainage, infrastructure, '
            'or other government-initiated project.'
        )
    return ''


def _requirement_scan_row_dict(req, scanned, latest_meta=None):
    latest_meta = latest_meta or {}
    filed_via = latest_meta.get('filed_via', '') if scanned else ''
    filed_via_label = latest_meta.get('filed_via_label', '') if scanned else ''
    return {
        'code': req.code,
        'name': req.name,
        'group_display': req.get_group_display(),
        'is_required_for_form': req.is_required_for_form,
        'is_active': req.is_active,
        'scanned': scanned,
        'latest_file_url': latest_meta.get('url', ''),
        'latest_file_name': latest_meta.get('name', ''),
        'filed_via': filed_via,
        'filed_via_label': filed_via_label,
    }


def _requirement_scan_row_extras(scanned, latest_meta=None):
    latest_meta = latest_meta or {}
    if not scanned:
        return {'filed_via': '', 'filed_via_label': ''}
    return {
        'filed_via': latest_meta.get('filed_via', ''),
        'filed_via_label': latest_meta.get('filed_via_label', ''),
    }


def _archive_requirement_scan_rows(requirements_group_a, scanned_types_set, displacement_reason='', latest_doc_by_type=None):
    """
    Build checklist rows from `documents.Requirement` rows; `scanned` is True when this
    requirement's `vault_document_type` exists in the applicant vault (upload or scan).

    When displacement is Option A/B/C, one extra trackable row is appended:
    - Option A: CDRRMO certification
    - Option B/C: ISF situational documentation
    (Option D keeps the base count only).

    Requirement `RVT` (voter certification) is rendered immediately after R01–R07 as optional
    follow-up; one optional situational row follows when displacement is Options A, B, or C.
    """
    scanned_types_set = scanned_types_set or set()
    latest_doc_by_type = latest_doc_by_type or {}

    base_reqs = []
    rvt_req = None
    for req in requirements_group_a:
        code = getattr(req, 'code', None)
        vault_t = (getattr(req, 'vault_document_type', None) or '').strip()
        if code == 'RVT':
            rvt_req = req
            continue
        # ISF situational slot is synthetic (with situational label); ignore DB rows so a
        # catalog/admin name like "(A: Danger Zone/Hazard, …)" never overrides it.
        if code == 'ISF-SIT' or vault_t == ISF_EXTRA_VAULT_DOC_TYPE:
            continue
        base_reqs.append(req)

    rows = []
    for req in base_reqs:
        dtype = (getattr(req, 'vault_document_type', None) or '').strip()
        scanned = bool(dtype and dtype in scanned_types_set)
        latest_meta = latest_doc_by_type.get(dtype, {}) if dtype else {}
        rows.append(_requirement_scan_row_dict(req, scanned, latest_meta))

    scanned_count = 0
    trackable_total = 0
    for req in base_reqs:
        dtype = (getattr(req, 'vault_document_type', None) or '').strip()
        if not dtype:
            continue
        trackable_total += 1
        if dtype in scanned_types_set:
            scanned_count += 1

    if rvt_req is not None:
        dtype = (getattr(rvt_req, 'vault_document_type', None) or '').strip()
        scanned = bool(dtype and dtype in scanned_types_set)
        latest_meta = latest_doc_by_type.get(dtype, {}) if dtype else {}
        rvt_row = _requirement_scan_row_dict(rvt_req, scanned, latest_meta)
        # Intake checklist: voter certification is optional (does not gate proceed).
        rvt_row['is_required_for_form'] = False
        rows.append(rvt_row)
        if dtype:
            trackable_total += 1
            if dtype in scanned_types_set:
                scanned_count += 1

    dr = (displacement_reason or '').strip()
    if dr == 'danger_zone':
        scanned_cdrrmo = CDRRMO_EXTRA_VAULT_DOC_TYPE in scanned_types_set
        latest_cdrrmo = latest_doc_by_type.get(CDRRMO_EXTRA_VAULT_DOC_TYPE, {})
        rows.append({
            'code': 'CDRRMO',
            'name': _isf_situational_row_display_name(dr),
            'policy_tooltip': _isf_situational_policy_tooltip(dr),
            'group_display': 'Group A - Applicant Requirements',
            # Follow-up only: displayed in checklist but does not affect baseline proceed gate.
            'is_required_for_form': False,
            'is_active': True,
            'scanned': scanned_cdrrmo,
            'latest_file_url': latest_cdrrmo.get('url', ''),
            'latest_file_name': latest_cdrrmo.get('name', ''),
            **_requirement_scan_row_extras(scanned_cdrrmo, latest_cdrrmo),
        })
        # LIST OF APPLICANTS badge + parity with modal row count (R01–RVT + optional situational row).
        trackable_total += 1
        if scanned_cdrrmo:
            scanned_count += 1
    elif dr in ('ejected', 'relocated'):
        scanned_isf = ISF_EXTRA_VAULT_DOC_TYPE in scanned_types_set
        latest_isf = latest_doc_by_type.get(ISF_EXTRA_VAULT_DOC_TYPE, {})
        rows.append({
            'code': 'ISF-SIT',
            'name': _isf_situational_row_display_name(dr),
            'policy_tooltip': _isf_situational_policy_tooltip(dr),
            'group_display': 'Group A - Applicant Requirements',
            # Follow-up only: displayed in checklist but does not affect baseline proceed gate.
            'is_required_for_form': False,
            'is_active': True,
            'scanned': scanned_isf,
            'latest_file_url': latest_isf.get('url', ''),
            'latest_file_name': latest_isf.get('name', ''),
            **_requirement_scan_row_extras(scanned_isf, latest_isf),
        })
        # LIST OF APPLICANTS badge + parity with modal row count (R01–RVT + optional situational row).
        trackable_total += 1
        if scanned_isf:
            scanned_count += 1

    return rows, scanned_count, trackable_total


def _required_requirement_counts(vault_types, displacement_reason, requirements_group_a):
    """(scanned_required, required_total) for walk-in / checklist chips."""
    rows, _, _ = _archive_requirement_scan_rows(
        requirements_group_a,
        vault_types or set(),
        displacement_reason=(displacement_reason or '').strip(),
        latest_doc_by_type={},
    )
    required_rows = [row for row in rows if row.get('is_required_for_form')]
    scanned_required = sum(1 for row in required_rows if row.get('scanned'))
    return scanned_required, len(required_rows)


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
    if applicant.status == 'disqualified':
        location = 'Disqualified Registry'
        status_text = 'Permanently Disqualified / Blacklisted'
    elif applicant_excluded_from_intake_registration(applicant):
        location = 'Housing Units / GK Masterlist (Module 4)'
        status_text = 'On-site beneficiary (active lot award)'
    elif application is not None:
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
        'can_open_in_intake': (
            not duplicate_applicant.archives.exists()
            and not applicant_excluded_from_intake_registration(duplicate_applicant)
        ),
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
        'doc_police_clearance', 'doc_no_property', 'doc_2x2_picture', 'doc_sketch_location',
        'doc_voter_cert',
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
            applicant.full_name = full_name[:30]
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
        parsed_years = _parse_years_residing(years_residing)
        if parsed_years is not None:
            applicant.years_residing = parsed_years
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
    applicant_id = (request.POST.get('applicant_id') or request.GET.get('applicant_id') or '').strip()
    doc_key = (request.POST.get('doc_key') or request.GET.get('doc_key') or '').strip()
    doc_code = (request.POST.get('doc_code') or request.GET.get('doc_code') or '').strip().upper()

    if not applicant_id or doc_key not in APPLICANT_DOC_KEY_TO_VAULT_TYPE:
        return JsonResponse({'success': False, 'error': 'Missing or invalid applicant/document mapping.'}, status=400)

    allowed_positions = ['fourth_member', 'second_member']
    if doc_key == 'doc_signed_application':
        if not request.user.is_staff:
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    elif request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file and request.FILES:
        uploaded_file = next(iter(request.FILES.values()))
    if not uploaded_file:
        return JsonResponse({'success': False, 'error': 'No scanned file payload received.'}, status=400)

    capture_method = (request.POST.get('capture_method') or request.GET.get('capture_method') or '').strip().lower()
    if capture_method not in (Document.CAPTURE_UPLOAD, Document.CAPTURE_SCAN):
        capture_method = Document.CAPTURE_SCAN

    try:
        applicant = Applicant.objects.get(id=applicant_id)
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found.'}, status=404)

    document_type = APPLICANT_DOC_KEY_TO_VAULT_TYPE[doc_key]
    label_map = dict(Document.DOCUMENT_TYPE_CHOICES)
    doc_title = f"{applicant.full_name} - {label_map.get(document_type, document_type)}"

    doc, created = upsert_document_vault_upload(
        applicant=applicant,
        document_type=document_type,
        uploaded_file=uploaded_file,
        title=doc_title,
        uploaded_by=request.user,
        capture_method=capture_method,
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
        'document_url': doc.absolute_download_url(request),
        'document_name': doc.file_name or (uploaded_file.name if uploaded_file else ''),
        'capture_method': doc.capture_method or capture_method,
        'filed_via_label': document_filed_via_display(doc.capture_method or capture_method),
    })


@login_required
@verify_position
@csrf_exempt
@require_POST
def remove_scanned_requirement(request, position):
    """
    Remove a scanned/uploaded requirement from the vault and clear the legacy checklist flag.
    """
    applicant_id = (request.POST.get('applicant_id') or '').strip()
    doc_key = (request.POST.get('doc_key') or '').strip()

    if not applicant_id or doc_key not in APPLICANT_DOC_KEY_TO_VAULT_TYPE:
        return JsonResponse({'success': False, 'error': 'Missing or invalid applicant/document mapping.'}, status=400)

    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    try:
        applicant = Applicant.objects.get(id=applicant_id)
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found.'}, status=404)

    document_type = APPLICANT_DOC_KEY_TO_VAULT_TYPE[doc_key]
    doc = (
        Document.objects.filter(applicant_id=applicant.pk, document_type=document_type)
        .order_by('-uploaded_at')
        .first()
    )
    if doc:
        if doc.file:
            doc.file.delete(save=False)
        doc.delete()

    update_fields = []
    if hasattr(applicant, doc_key):
        setattr(applicant, doc_key, False)
        update_fields.append(doc_key)
    if update_fields:
        update_fields.append('updated_at')
        applicant.save(update_fields=update_fields)

    return JsonResponse({'success': True, 'message': 'Requirement removed.'})


@login_required
@verify_position
def applicant_requirement_scan_status(request, position):
    """Fresh document scan checklist rows (vault upload or scan counts as filed)."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'GET required.'}, status=405)

    if request.user.position not in ('second_member', 'fourth_member'):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = (request.GET.get('applicant_id') or '').strip()
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    try:
        applicant = Applicant.objects.get(pk=applicant_id)
    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found.'}, status=404)

    return JsonResponse(_build_applicant_requirement_scan_payload(applicant, request))


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
def unarchive_applicant(request, position):
    """
    AJAX endpoint to unarchive (restore) an applicant back to the active registered list.
    URL Route: /intake/staff/<position>/unarchive-applicant/
    """
    from django.http import JsonResponse
    
    if request.user.position not in ['second_member', 'fourth_member']:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Jocel or Joie can restore records.'}, status=403)
    
    archive_id = request.POST.get('archive_id')
    if not archive_id:
        return JsonResponse({'success': False, 'error': 'Missing archive_id.'}, status=400)
    
    try:
        archive_record = Archive.objects.get(id=archive_id)
        applicant = archive_record.applicant
        
        with transaction.atomic():
            # Flag the archive as restored and reset formal archive status so the
            # applicant returns to the REGISTERED APPLICANTS working list.
            archive_record.is_restored = True
            archive_record.formally_archived = False
            archive_record.save(update_fields=['is_restored', 'formally_archived'])
            
            # Unset module 2 handoff in case they were pushed to evaluation
            if applicant.module2_handoff_at is not None:
                applicant.module2_handoff_at = None
                applicant.module2_handoff_by = None
                applicant.save(update_fields=['module2_handoff_at', 'module2_handoff_by'])
                
        return JsonResponse({
            'success': True,
            'message': f'Applicant "{applicant.full_name}" restored successfully.'
        })
    except Archive.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Archive record not found.'})
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
    if applicant_excluded_from_intake_registration(applicant):
        return JsonResponse({
            'success': False,
            'error': (
                'This beneficiary is already on a housing unit (GK Masterlist / Module 4). '
                'Manage them under Housing Unit monitoring, not ISF Registration or Intake Archives proceed.'
            ),
        }, status=400)

    promote_to_module2 = str(request.POST.get('promote_to_module2', '')).strip().lower() in {'1', 'true', 'yes', 'on'}

    if promote_to_module2:
        is_bl, bl_entry = check_blacklist_module2(
            applicant.full_name,
            applicant.phone_number or None,
            applicant_id=applicant.id,
            last_name=applicant.last_name,
            first_name=applicant.first_name,
            date_of_birth=applicant.date_of_birth,
            barangay_id=applicant.barangay_id,
        )
        if is_bl:
            reason_label = bl_entry.get_reason_display() if bl_entry else 'Blacklist match'
            registry_applicant = None
            if bl_entry is not None and getattr(bl_entry, '_entry', None) is not None:
                registry_applicant = getattr(bl_entry._entry, 'applicant', None)
            registry_name = (registry_applicant.full_name if registry_applicant else applicant.full_name) or ''
            registry_ref = (registry_applicant.reference_number if registry_applicant else applicant.reference_number) or ''
            return JsonResponse({
                'success': False,
                'blacklist_blocked': True,
                'blacklist_reason': reason_label,
                'blacklist_registry_name': registry_name,
                'blacklist_registry_ref': registry_ref,
                'applicant_name': applicant.full_name or '',
                'applicant_reference': applicant.reference_number or '',
                'error': (
                    f'{applicant.full_name or "This applicant"} cannot proceed to '
                    'Applicant Evaluation and Eligibility because they are on the '
                    'Blacklisted Beneficiaries registry. Resolve the blacklist entry first.'
                ),
            }, status=400)

    if applicant.status == 'disqualified':
        return JsonResponse({'success': False, 'error': 'Disqualified records cannot be archived.'}, status=400)

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
        # If the record was previously restored, clear the flag so it appears
        # in the REGISTERED APPLICANTS table (and later in archive_list when
        # not restored).
        if not created and archive_record.is_restored:
            archive_record.is_restored = False
            archive_record.save(update_fields=['is_restored'])
        # Optional promotion path used by the archive checklist CTA:
        # once baseline required scans (R01–R07) are complete, mark as handed off for Module 2 list visibility.
        # Set formally_archived only when explicitly requested ("ARCHIVE record" button
        # or formal Module 2 handoff via promote_to_module2).
        # Plain "Proceed" from the active list does NOT set formally_archived —
        # those applicants should appear in the mini-table first.
        formally_archive = request.POST.get('formally_archive') == 'true'
        if archive_record is not None and (formally_archive or promote_to_module2):
            if not archive_record.formally_archived:
                archive_record.formally_archived = True
                archive_record.save(update_fields=['formally_archived'])

        # Formal Module 2 handoff: set module2_handoff_at for evaluation pipeline visibility.
        handoff_just_set = False
        if promote_to_module2 and applicant.module2_handoff_at is None:
            applicant.module2_handoff_at = timezone.now()
            applicant.module2_handoff_by = request.user
            applicant.save(update_fields=['module2_handoff_at', 'module2_handoff_by', 'updated_at'])
            handoff_just_set = True

        # Module 2 handoff: evaluation-stage SMS (document checklist path with promote_to_module2).
        should_send_proceed_sms = bool(applicant.phone_number) and handoff_just_set

        if not should_send_proceed_sms and promote_to_module2:
            logger.warning(
                'proceed_to_applications: skipped proceed SMS (has_phone=%s handoff_just_set=%s archive_created=%s registration_sms_sent=%s ref=%s)',
                bool(applicant.phone_number),
                handoff_just_set,
                created,
                applicant.registration_sms_sent,
                applicant.reference_number,
            )
        if should_send_proceed_sms:
            applicant_id = applicant.id
            archive_id = archive_record.id
            phone_number = applicant.phone_number
            sms_message = sms_workflow.message_proceed_to_evaluation(applicant)

            def _send_proceed_sms_after_commit():
                sms_ok = send_sms(
                    phone_number,
                    sms_message,
                    sms_workflow.PROCEED_TO_EVALUATION,
                    applicant=applicant,
                    module='intake',
                )
                if sms_ok:
                    Applicant.objects.filter(id=applicant_id).update(registration_sms_sent=True)
                    Archive.objects.filter(id=archive_id).update(
                        sms_sent=True,
                        sms_sent_at=timezone.now(),
                    )

            transaction.on_commit(_send_proceed_sms_after_commit)

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


def _build_intake_applicant_review_payload(
    app,
    *,
    requirements_group_a,
    vault_types,
    date_registered_override=None,
    module2_handed_off=False,
    is_archived=False,
):
    """Full applicant dict for the intake Review modal (registration + archive list)."""
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

    queue_type = 'None'
    queue_position = None
    active_queue = getattr(app, 'active_queue', None)
    if active_queue:
        queue_entry = active_queue[0]
        qraw = (getattr(queue_entry, 'queue_type', None) or '').lower()
        if qraw == 'walk_in' or qraw == 'walk-in':
            queue_type = 'Walk-in'
        else:
            queue_type = 'Priority'
        queue_position = queue_entry.position

    cdrrmo_status = None
    cdrrmo_status_value = None
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
        cdrrmo_status = 'Not Requested'
        cdrrmo_status_value = None
        cdrrmo_disposition_source = 'pending'

    local_created_at = timezone.localtime(app.created_at)
    doc_scanned_count, doc_required_total = _required_requirement_counts(
        vault_types or set(),
        app.displacement_reason,
        requirements_group_a,
    )
    date_registered = date_registered_override or local_created_at.strftime('%Y-%m-%d')
    return {
        'id': str(app.id),
        'fullName': app.full_name,
        'referenceNumber': app.reference_number,
        'dateRegistered': date_registered,
        'dateTime': local_created_at.strftime('%b %d, %Y | %I:%M %p'),
        'dateTimeDatePart': local_created_at.strftime('%b %d, %Y') + ' |',
        'dateTimeTimePart': local_created_at.strftime('%I:%M %p'),
        'registeredAgo': _relative_time_ago(app.created_at),
        'dateOfBirthDisplay': app.date_of_birth.strftime('%m/%d/%Y') if app.date_of_birth else '',
        'channel': 'B' if app.channel == 'danger_zone' else 'C',
        'submissionId': None,
        'applicantId': str(app.id),
        'lastName': app.last_name or '',
        'firstName': app.first_name or '',
        'middleName': app.middle_name or '',
        'extensionName': app.extension_name or '',
        'sex': app.sex or '',
        'civilStatus': app.get_civil_status_display() if app.civil_status else '',
        'isRegisteredVoterTalisay': bool(app.is_registered_voter_talisay),
        'hasPropertyInTalisay': bool(app.has_property_in_talisay),
        'age': app.age,
        'dateOfBirth': app.date_of_birth.isoformat() if app.date_of_birth else '',
        'barangay': app.barangay.name if app.barangay else 'Unknown',
        'phoneNumber': app.phone_number or '',
        'currentAddress': app.current_address or '',
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
        'monthlyIncome': float(app.monthly_income),
        'incomeEligible': app.is_income_eligible,
        'incomeCeilingPeso': MODULE1_MONTHLY_INCOME_CEILING_PESO,
        'yearsResiding': app.years_residing,
        'residencyEligible': _is_residency_eligible(app.years_residing),
        'minYearsResidingTalisay': MODULE1_MIN_YEARS_RESIDING_TALISAY,
        'occupation': app.occupation or '',
        'employmentStatus': app.get_employment_status_display() if app.employment_status else '',
        'isInDangerZone': app.channel == 'danger_zone' and bool(app.danger_zone_type),
        'dangerZoneType': app.danger_zone_type if hasattr(app, 'danger_zone_type') and app.danger_zone_type else '',
        'dangerZoneLocation': app.danger_zone_location if hasattr(app, 'danger_zone_location') and app.danger_zone_location else (danger_zone_type or ''),
        'displacementReason': (app.displacement_reason or '').strip(),
        'ejectionType': (app.ejection_type or '').strip() if hasattr(app, 'ejection_type') else '',
        'ejectionDate': app.ejection_date.isoformat() if hasattr(app, 'ejection_date') and app.ejection_date else '',
        'projectName': (app.project_name or '').strip() if hasattr(app, 'project_name') else '',
        'eligibilityStatus': eligibility_status,
        'applicantStatus': app.status,
        'readyForModule2': app.status != 'disqualified',
        'module2HandedOff': bool(module2_handed_off),
        'isArchived': bool(is_archived),
        'queueType': queue_type,
        'queuePosition': queue_position,
        'cdrrmoStatus': cdrrmo_status,
        'cdrrmo_status': cdrrmo_status_value,
        'cdrrmo_disposition_source': cdrrmo_disposition_source,
        'office_intake_notes': office_intake_notes,
        'result_recorded_by_name': result_recorded_by_name,
        'certified_at': certified_at,
        'certification_notes': certification_notes,
        'ronda_evidence_photos': ronda_evidence_photos,
        'isCdrrmoFlagged': is_cdrrmo_flagged,
        'cdrrmoDaysPending': cdrrmo_days_pending,
        'signatoryRoutingDelayed': False,
        'disqualificationReason': app.disqualification_reason or None,
        'handledBy': app.registered_by.get_full_name() if app.registered_by else 'Unknown',
        'handledByPosition': app.registered_by.get_position_display_short() if app.registered_by else '',
        'handledByInitials': (app.registered_by.first_name[:1] + app.registered_by.last_name[:1]).upper() if app.registered_by else '??',
        'docsCount': doc_scanned_count,
        'docsTotal': doc_required_total,
        'vaultDocumentTypes': sorted(vault_types or set()),
        'docBrgyResidency': app.doc_brgy_residency,
        'docBrgyIndigency': app.doc_brgy_indigency,
        'docCedula': app.doc_cedula,
        'docPoliceClearance': app.doc_police_clearance,
        'docNoProperty': app.doc_no_property,
        'doc2x2Picture': app.doc_2x2_picture,
        'docSketchLocation': app.doc_sketch_location,
        'docVoterCert': app.doc_voter_cert,
        'registrationSmsSent': app.registration_sms_sent,
        'eligibilitySmsSent': app.eligibility_sms_sent,
        'hasPhone': bool(app.phone_number),
    }


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
    allowed_positions = ['second_member', 'fourth_member', 'field', 'ronda']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. This module is for authorized staff only.')
        return redirect('accounts:dashboard')

    # Determine if user has full access (can modify) or read-only (field/oversight)
    can_modify = request.user.position in ['second_member', 'fourth_member']
    # Build applicants list from danger zone channel only
    applicants = []

    # ====== CHANNEL B: Danger Zone Applicants + ALL OTHER APPLICANTS ======
    # Active list: only applicants with NO archive record at all (brand new registrations).
    # Restored applicants have is_restored=True archives, so they route to the
    # mini-table below instead of back to the active list.
    walk_in_applicants = list(
        Applicant.objects.exclude(
            Exists(
                Archive.objects.filter(
                    applicant=OuterRef('pk'),
                )
            )
        ).exclude(
            intake_registration_exclude_q(),
        ).exclude(
            application__isnull=False,
        ).distinct().select_related(
            'barangay', 'eligibility_checked_by', 'registered_by'
        ).prefetch_related(
            Prefetch(
                'queue_entries',
                queryset=QueueEntry.objects.filter(status='active'),
                to_attr='active_queue',
            ),
        ).order_by('created_at')
    )
    walk_in_ids = [a.id for a in walk_in_applicants]
    walk_in_vault_types_by_applicant = defaultdict(set)
    walk_in_extra_doc_types_by_applicant = defaultdict(set)
    requirements_group_a = list(Requirement.objects.filter(group='A').order_by('order', 'code'))
    if walk_in_ids:
        for aid, doc_type in Document.objects.filter(
            applicant_id__in=walk_in_ids,
        ).exclude(document_type='').values_list('applicant_id', 'document_type'):
            walk_in_vault_types_by_applicant[aid].add(doc_type)
            if doc_type in (ISF_EXTRA_VAULT_DOC_TYPE, CDRRMO_EXTRA_VAULT_DOC_TYPE):
                walk_in_extra_doc_types_by_applicant[aid].add(doc_type)

    for app in walk_in_applicants:
        applicants.append(_build_intake_applicant_review_payload(
            app,
            requirements_group_a=requirements_group_a,
            vault_types=walk_in_vault_types_by_applicant.get(app.id, set()),
        ))

    # Mini-table (REGISTERED APPLICANTS): shows all archives that have NOT been
    # formally closed via "ARCHIVE record" (formally_archived=False).
    # This includes both:
    #   - Newly proceeded applicants (is_restored=False, formally_archived=False)
    #   - Restored applicants (is_restored=True, formally_archived=False)
    # Once "ARCHIVE record" is clicked (sets formally_archived=True), they leave
    # this table and appear only in archive_list.html with RESTORE button enabled.
    archive_records = []
    archives = list(
        Archive.objects.filter(
            formally_archived=False,
        ).exclude(
            # Exclude restored archives — they belong to applicants who have already
            # been processed through a previous cycle and don't need to show here.
            # Exception: keep is_restored=True archives that are back in the working
            # list (module2_handoff_at=None is already filtered above, so this is safe).
            Q(is_restored=True) & Q(applicant__application__isnull=False),
        ).exclude(
            intake_registration_exclude_q(prefix='applicant__'),
        ).exclude(
            applicant__application__isnull=False,
        ).select_related(
            'archived_by',
            'applicant',
            'applicant__barangay',
            'applicant__registered_by',
            'applicant__application__form_generated_by',
        ).prefetch_related(
            'applicant__household_members',
            Prefetch(
                'applicant__queue_entries',
                queryset=QueueEntry.objects.filter(status='active'),
                to_attr='active_queue',
            ),
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
            .with_file_payload()
            .select_related('blob_record')
            .order_by('applicant_id', 'document_type', '-uploaded_at')
        )
        for doc in latest_docs:
            dtype = (doc.document_type or '').strip()
            if not dtype:
                continue
            slot = latest_doc_meta_by_applicant_id[doc.applicant_id]
            if dtype in slot:
                continue
            slot[dtype] = {
                'url': doc.absolute_download_url(request),
                'name': (doc.file_name or doc.title or doc.get_document_type_display() or '').strip(),
            }

    channel_display_map = {
        'channel_a': ('A', 'Channel A — Walk-in'),
        'channel_b_no_hazard': ('B', 'Channel B — No hazard (No)'),
        'channel_b_hazard': ('B', 'Channel B — Hazard (Yes)'),
        'channel_c': ('C', 'Channel C — Landowner'),
    }

    for archive in archives:
        channel_code, channel_label = channel_display_map.get(archive.channel, ('?', archive.channel))
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
        scanned_required, required_total = _required_requirement_counts(
            scanned_types,
            disp_snapshot,
            requirements_group_a,
        )
        bl_gate = (
            _intake_module2_blacklist_check_payload(archive.applicant)
            if archive.applicant_id and archive.applicant
            else _intake_module2_blacklist_check_payload(None)
        )
        _req_status_label, _req_status_tier = _archive_list_status_label_and_tier(
            scanned_required,
            required_total,
            blacklist_blocked=bool(bl_gate.get('blacklistBlocked')),
        )
        archive_records.append({
            'id': str(archive.id),
            'dateTime': local_archived_at.strftime('%b %d, %Y | %I:%M %p') if local_archived_at else '',
            'proceededAgo': _relative_time_ago(archive.archived_at) if archive.archived_at else '—',
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
            'requiredScannedCount': scanned_required,
            'requiredTotal': required_total,
            'requirementsStatusLabel': _req_status_label,
            'requirementsStatusTier': _req_status_tier,
            'applicantId': str(archive.applicant_id) if archive.applicant_id else '',
            'displacementReason': disp_snapshot,
            'archiveDispNameClass': _archive_list_name_class_for_displacement(disp_snapshot),
            **bl_gate,
        })

    archive_review_modal = {}
    for archive in archives:
        ref = archive.reference_number_snapshot or ''
        applicant = getattr(archive, 'applicant', None)
        if not ref or not applicant:
            continue
        local_archived_at = timezone.localtime(archive.archived_at) if archive.archived_at else None
        archive_review_modal[ref] = _build_intake_applicant_review_payload(
            applicant,
            requirements_group_a=requirements_group_a,
            vault_types=docs_by_applicant_id.get(applicant.id, set()),
            date_registered_override=local_archived_at.strftime('%Y-%m-%d') if local_archived_at else None,
            module2_handed_off=True,
            is_archived=True,
        )

    archive_documents_modal = {
        r['referenceNumber']: {
            'referenceNumber': r['referenceNumber'],
            'fullName': r['fullName'],
            'applicantId': r.get('applicantId', ''),
            'displacementReason': r.get('displacementReason', ''),
            'rows': r['requirementScanRows'],
            'blacklistBlocked': bool(r.get('blacklistBlocked')),
            'blacklistReason': r.get('blacklistReason', ''),
            'blacklistRegistryName': r.get('blacklistRegistryName', ''),
            'blacklistRegistryRef': r.get('blacklistRegistryRef', ''),
        }
        for r in archive_records
    }

    active_list_q = (request.GET.get('q') or '').strip()
    archive_list_q = (request.GET.get('archive_q') or '').strip()
    archive_list_barangay = (request.GET.get('archive_barangay') or 'all').strip()

    def _intake_table_row_matches_search(row, query, text_keys, blacklist_flag_key=None):
        if not query:
            return True
        ql = query.lower()
        if 'blacklist' in ql and blacklist_flag_key and row.get(blacklist_flag_key):
            return True
        for key in text_keys:
            if ql in str(row.get(key) or '').lower():
                return True
        row_id = str(row.get('id') or '').lower()
        if row_id and ql.lstrip('#') in row_id:
            return True
        return False

    if active_list_q:
        applicants = [
            a for a in applicants
            if _intake_table_row_matches_search(
                a,
                active_list_q,
                ('fullName', 'referenceNumber', 'barangay'),
            )
        ]

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
    
    archive_complete_count = len([r for r in archive_records if r.get('requirementsStatusTier') == 'complete'])
    archive_incomplete_count = len([r for r in archive_records if r.get('requirementsStatusTier') == 'incomplete'])
    archive_pending_count = len([r for r in archive_records if r.get('requirementsStatusTier') == 'pending'])
    
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
        'archive_records_total': len(archive_records),
        'archive_complete_count': archive_complete_count,
        'archive_incomplete_count': archive_incomplete_count,
        'archive_pending_count': archive_pending_count,
        'archive_documents_modal': archive_documents_modal,
        'archive_review_modal': json.dumps(archive_review_modal),
        'active_list_q': active_list_q,
        'archive_list_q': archive_list_q,
        'archive_list_barangay': archive_list_barangay,
    }
    return render(request, 'staff/applicants.html', context)


@login_required
@verify_position
def walkin_register(request, position):
    """
    Module 1: Register & Record Walk-in Applicant

    PURPOSE: Encode applicant identity, household, income, danger zone claim (if any).
    - Staff enters all required information
    - System generates reference number
    - Record saved to database — ready for Module 2 processing
    - No SMS on registration (first applicant SMS is on proceed / handoff)

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

    date_of_birth = form.cleaned_data.get('date_of_birth')
    computed_age = None
    if date_of_birth:
        today = timezone.localdate()
        computed_age = today.year - date_of_birth.year - (
            (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
        )

    # Get barangay instance
    barangay_name = form.cleaned_data['barangay']
    barangay, _ = Barangay.objects.get_or_create(name=barangay_name)

    # Duplicate guard: same DOB + barangay + last name + first name (only when DOB provided).
    duplicate_last_name = (form.cleaned_data.get('last_name') or '').strip()
    duplicate_first_name = (form.cleaned_data.get('first_name') or '').strip()
    duplicate_applicant = None
    if date_of_birth:
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
    full_name = (form.cleaned_data.get('full_name') or '').strip()[:30]
    if not full_name:
        last_name = (form.cleaned_data.get('last_name') or '').strip()
        first_name = (form.cleaned_data.get('first_name') or '').strip()
        middle_name = (form.cleaned_data.get('middle_name') or '').strip()
        if last_name and first_name:
            full_name = (
                f"{last_name}, {first_name}{(' ' + middle_name) if middle_name else ''}"
            )[:30]
        else:
            full_name = "Unnamed Applicant"[:30]
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
        extension_name=form.cleaned_data.get('extension_name', '') or '',
        full_name=full_name,
        sex=form.cleaned_data.get('sex', ''),
        civil_status=form.cleaned_data.get('civil_status', ''),
        age=computed_age,
        date_of_birth=date_of_birth,
        place_of_birth=(form.cleaned_data.get('place_of_birth') or '')[:30],
        phone_number=phone_number,
        spouse_name=(form.cleaned_data.get('spouse_name') or '')[:30],
        spouse_phone=form.cleaned_data.get('spouse_phone') or '',
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
        doc_voter_cert=request.POST.get('doc_voter_cert') == 'true',
    )

    # Process household members from form
    for i in range(1, 51):  # Support up to 50 household members
        name = request.POST.get(f'hh_member_{i}_name', '').strip().upper()
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

    # Automatically proceed applicant to LIST OF APPLICANTS (IntakeArchive)
    with transaction.atomic():
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
        # If the record was previously restored, clear the flag so it appears
        # correctly in the REGISTERED APPLICANTS table.
        if not created and archive_record.is_restored:
            archive_record.is_restored = False
            archive_record.save(update_fields=['is_restored'])

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
            'doc_voter_cert': 'Voter Certification',
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
                'sex': applicant.sex or '',
                'civilStatus': applicant.get_civil_status_display() if applicant.civil_status else '',
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
@verify_position
def archive_list(request, position):
    """
    Display Intake Archive receipts (records proceeded from the registration list).
    URL: /intake/staff/<position>/archives/
    """
    if request.user.position not in ('second_member', 'fourth_member'):
        messages.error(request, 'Access denied. Archives are for Second and Fourth Member staff only.')
        return redirect('accounts:dashboard')

    from django.core.paginator import Paginator

    selected_stage = (request.GET.get('stage') or '').strip()
    valid_stage_keys = {key for key, _ in ARCHIVE_STAGE_FILTER_CHOICES}
    if selected_stage and selected_stage not in valid_stage_keys:
        selected_stage = ''
    search_query = (request.GET.get('q') or '').strip()

    archives_qs = (
        Archive.objects.exclude(
            intake_registration_exclude_q(prefix='applicant__'),
        ).exclude(
            applicant__application__isnull=False,
        ).select_related(
            'applicant',
            'archived_by',
            'applicant__module2_handoff_by',
            'applicant__application__form_generated_by',
        )
        .prefetch_related(
            Prefetch(
                'applicant__application__lot_awards',
                queryset=LotAward.objects.select_related('unit', 'construction_progress'),
            ),
        )
        .order_by('archived_at')
    )

    if search_query:
        txn_fragment = search_query.lstrip('#').strip()
        search_q = (
            Q(full_name_snapshot__icontains=search_query) |
            Q(reference_number_snapshot__icontains=search_query) |
            Q(barangay_name_snapshot__icontains=search_query)
        )
        if txn_fragment:
            search_q |= Q(id__icontains=txn_fragment)
        if 'blacklist' in search_query.lower():
            search_q |= Q(applicant__blacklist_record__isnull=False)
        archives_qs = archives_qs.filter(search_q).distinct()

    channel_choices = {
        'channel_a': 'Channel A — Walk-in',
        'channel_b_no_hazard': 'Channel B — No hazard',
        'channel_b_hazard': 'Channel B — Hazard',
        'channel_c': 'Channel C — Landowner',
    }

    applicant_ids_for_blacklist = list(
        archives_qs.exclude(applicant_id__isnull=True).values_list('applicant_id', flat=True).distinct()
    )
    blacklist_map = {
        str(b.applicant_id): b
        for b in Blacklist.objects.filter(applicant_id__in=applicant_ids_for_blacklist).only('applicant_id')
    }

    applicant_ids_for_docs = list(
        archives_qs.exclude(applicant_id__isnull=True).values_list('applicant_id', flat=True)
    )
    docs_by_applicant_id = defaultdict(set)
    if applicant_ids_for_docs:
        for aid, doc_type in Document.objects.filter(
            applicant_id__in=applicant_ids_for_docs,
        ).values_list('applicant_id', 'document_type'):
            docs_by_applicant_id[aid].add(doc_type)
    signed_doc_by_applicant_id = {}
    if applicant_ids_for_docs:
        for doc in Document.objects.filter(
            applicant_id__in=applicant_ids_for_docs,
            document_type='signed_application',
        ).order_by('-uploaded_at', '-id'):
            if doc.applicant_id not in signed_doc_by_applicant_id:
                signed_doc_by_applicant_id[doc.applicant_id] = doc
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

        applicant_live = archive.applicant if archive.applicant_id else None
        bl_row = blacklist_map.get(str(applicant_live.pk)) if applicant_live else None
        applicant_status_primary, applicant_status_detail = archive_applicant_status(applicant_live, bl_row)

        app_obj = None
        if archive.applicant_id and archive.applicant:
            app_obj = getattr(archive.applicant, 'application', None)
        application_stage_key = archive_stage_filter_key(applicant_live, app_obj, bl_row)

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

        form_gen_summary = 'Application form not generated yet'
        form_gen_at = ''
        form_gen_by = ''
        if app_obj and app_obj.form_generated_at:
            local_form_generated_at = timezone.localtime(app_obj.form_generated_at)
            form_gen_at = local_form_generated_at.strftime('%Y-%m-%d %I:%M %p')
            form_gen_by = app_obj.form_generated_by.get_full_name() if app_obj.form_generated_by else 'Unknown'
            form_gen_summary = f"{app_obj.application_number or '—'} • Form generated {form_gen_at}"

        m2_handoff_at = ''
        m2_handoff_by = ''
        if archive.applicant_id and archive.applicant:
            ap = archive.applicant
            if getattr(ap, 'module2_handoff_at', None):
                m2_handoff_at = timezone.localtime(ap.module2_handoff_at).strftime('%Y-%m-%d %I:%M %p')
                hb = getattr(ap, 'module2_handoff_by', None)
                m2_handoff_by = hb.get_full_name() if hb else '—'
            else:
                m2_handoff_at = ''
                m2_handoff_by = ''

        sms_text = 'No Phone'
        if bool(archive.applicant.phone_number if archive.applicant else False):
            sms_text = 'Sent' if archive.sms_sent else 'Not Sent'

        applicant_id_str = str(archive.applicant_id) if archive.applicant_id else ''
        documents_vault_url = ''
        ready_for_form_url = ''
        signed_form_view_url = ''
        generated_form_pdf_url = ''
        form_preview_url = ''
        form_preview_kind = 'none'
        if archive.applicant_id:
            vault_path = reverse('documents:management', kwargs={'position': position})
            documents_vault_url = f"{vault_path}?{urlencode({'open_vault': '1', 'applicant_id': applicant_id_str})}"
            ready_for_form_path = reverse('applications:ready_for_form_queue', kwargs={'position': position})
            ready_for_form_url = f"{ready_for_form_path}?{urlencode({'applicant_id': applicant_id_str, 'from': 'archives'})}"
            sa_doc = signed_doc_by_applicant_id.get(archive.applicant_id)
            if sa_doc and applicant_live and applicant_has_signed_application_payload(applicant_live):
                signed_form_view_url = reverse(
                    'documents:blob_download',
                    kwargs={'position': position, 'doc_id': sa_doc.pk},
                )
                form_preview_url = signed_form_view_url
                form_preview_kind = 'signed'
            elif app_obj and app_obj.form_generated_at:
                generated_form_pdf_url = reverse(
                    'applications:application_form_pdf',
                    kwargs={'position': position, 'applicant_id': archive.applicant_id},
                )
                form_preview_url = generated_form_pdf_url
                form_preview_kind = 'generated'

        records.append({
            'id': str(archive.id),
            'dateTime': date_time_display,
            'archivedDateOnly': local_archived_at.strftime('%b %d, %Y') if archive.archived_at else '—',
            'archivedTimeOnly': local_archived_at.strftime('%I:%M %p') if archive.archived_at else '',
            'proceededAgo': _relative_time_ago(archive.archived_at) if archive.archived_at else '—',
            'handoffAt': handoff_at_detail,
            'referenceNumber': archive.reference_number_snapshot,
            'fullName': archive.full_name_snapshot,
            'displacementReason': disp_snapshot,
            'archiveDispNameClass': _archive_list_name_class_for_displacement(disp_snapshot),
            'lastName': archive.last_name_snapshot,
            'firstName': archive.first_name_snapshot,
            'middleName': archive.middle_name_snapshot,
            'extensionName': archive.extension_name_snapshot,
            'channel': archive.channel,
            'channelLabel': channel_display,
            'applicantStatusLabel': applicant_status_primary,
            'applicantStatusDetail': applicant_status_detail or '',
            'applicationStageKey': application_stage_key,
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
            'archiveSnapshotLine': f"{archive.reference_number_snapshot} • {archive.full_name_snapshot}",
            'module2HandoffAt': m2_handoff_at,
            'module2HandoffBy': m2_handoff_by,
            'formGenSummary': form_gen_summary,
            'formGenAt': form_gen_at,
            'formGenBy': form_gen_by,
            'readOnlyState': 'Read-only historical record',
            'applicantId': applicant_id_str,
            'documentsVaultUrl': documents_vault_url,
            'readyForFormUrl': ready_for_form_url,
            'signedFormViewUrl': signed_form_view_url,
            'generatedFormPdfUrl': generated_form_pdf_url,
            'formPreviewUrl': form_preview_url,
            'formPreviewKind': form_preview_kind,
            # Restorable only when:
            # 1. The archive IS formally_archived (staff clicked "ARCHIVE record")
            # 2. The archive is NOT already restored (is_restored=True = back in working list)
            # 3. Has not yet received an Application (Evaluation/Form/Awarding/Housing
            #    applicants have Applications and are excluded from this page entirely).
            'isRestorable': (
                archive.formally_archived
                and not archive.is_restored
                and not bool(getattr(archive.applicant, 'application', None))
            ),
        })

    if selected_stage:
        records = [r for r in records if r.get('applicationStageKey') == selected_stage]

    # Pagination
    paginator = Paginator(records, 10)  # 10 records per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    _q = request.GET.copy()
    _q.pop('page', None)
    pagination_query = _q.urlencode()

    selected_stage_label = ''
    if selected_stage:
        selected_stage_label = dict(ARCHIVE_STAGE_FILTER_CHOICES).get(selected_stage, selected_stage)

    # Context: stage + search only (channel/reason/staff/date filters removed from UI).
    context = {
        'page_title': 'Archive Records',
        'staff_position': position,
        'position': position,
        'user_position': request.user.position,
        'can_modify': request.user.position in ['second_member', 'fourth_member'],
        'total_archived': paginator.count,
        'selected_stage': selected_stage,
        'selected_stage_label': selected_stage_label,
        'stage_choices': ARCHIVE_STAGE_FILTER_CHOICES,
        'search_query': search_query,
        'archive_records': page_obj.object_list,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
    }

    return render(request, 'staff/archive_list.html', context)


# =============================================================================
# PUBLIC — Applicant Status Tracker (no login required)
# Linked from SMS deep-links:  /status/<ref>/
# =============================================================================

# Stage pipeline definition — order matters.
_STATUS_PIPELINE = [
    {
        'key': 'registration',
        'label': 'Rehistrasyon',
        'label_en': 'Registration',
        'statuses': [],  # reached by anyone who has a record
        'description': 'Ang imo aplikasyon narehistro na sa Talisay Housing Authority.',
        'description_en': 'Your application has been registered with the Talisay Housing Authority.',
    },
    {
        'key': 'document_review',
        'label': 'Pagsumiter sang Dokumento',
        'label_en': 'Document Submission',
        'statuses': ['pending', 'pending_cdrrmo', 'pending_followup', 'requirements'],
        'description': 'Ang imo mga dokumento yara pa sa proseso sang pagsurob-suroy. Palihog maghulat.',
        'description_en': 'Your documents are currently being reviewed. Please wait for further updates.',
    },
    {
        'key': 'evaluation',
        'label': 'Evaluation',
        'label_en': 'Evaluation & Eligibility',
        'statuses': ['eligible', 'application'],
        'description': 'Ang imo aplikasyon yara na sa evaluation stage. Ang imo eligibility ginasulit sang mga opisyales.',
        'description_en': 'Your application is now under evaluation. Your eligibility is being assessed by the officers.',
    },
    {
        'key': 'form_generation',
        'label': 'Porma',
        'label_en': 'Form Generation',
        'statuses': ['standby'],
        'description': 'Ang imo porma gina-proseso na. Maghulat sang imbitasyon para sa imo orientasyon.',
        'description_en': 'Your forms are being processed. Wait for an invitation to your orientation.',
    },
    {
        'key': 'lot_awarding',
        'label': 'Lot Awarding',
        'label_en': 'Lot Awarding',
        'statuses': ['awarded'],
        'description': 'Congratulations! Ikaw na ang assignan sang lote. Palihog magdu-aw sa amon opisina para sa mga detalye.',
        'description_en': 'Congratulations! You have been assigned a lot. Please visit our office for details.',
    },
]

_DISQUALIFIED_STAGE = {
    'key': 'disqualified',
    'label': 'Nasarado',
    'label_en': 'Application Closed',
    'description': 'Ang imo aplikasyon indi ma-proseso pa. Palihog magdu-aw sa amon opisina para sa katarungan.',
    'description_en': 'Your application could not be processed. Please visit our office for more information.',
}


def _resolve_pipeline_stage(status: str):
    """
    Returns (active_index, stages_list) based on the applicant status.
    For disqualified, returns (-1, None) and the caller uses _DISQUALIFIED_STAGE.
    """
    if status == 'disqualified':
        return -1, None

    # Registration is always step 0 (completed if any record exists)
    for idx, stage in enumerate(_STATUS_PIPELINE):
        if status in stage['statuses']:
            return idx, _STATUS_PIPELINE
    # Unknown / default: show as document review
    return 1, _STATUS_PIPELINE


def applicant_status_tracker(request, ref):
    """
    Public (no-login) applicant status tracker page.
    URL: /status/<ref>/

    Resolves the applicant by reference number. If not found in active applicants,
    checks the Archive table (applicants who were moved to Module 2+).
    Renders a mobile-friendly status card — safe fields only (name + ref + stage).
    """
    ref = (ref or '').strip().upper()

    applicant = None
    archive = None
    applicant_name = ''
    applicant_status = ''
    updated_at = None

    # 1. Try active applicant first
    try:
        applicant = Applicant.objects.get(reference_number=ref)
        applicant_name = applicant.full_name or ''
        applicant_status = applicant.status or 'pending'
        updated_at = applicant.updated_at
    except Applicant.DoesNotExist:
        pass

    # 2. If not found in active, check Archive (forwarded to Module 2+)
    if applicant is None:
        try:
            archive = Archive.objects.filter(
                reference_number_snapshot=ref
            ).order_by('-archived_at').first()
            if archive:
                applicant_name = archive.full_name_snapshot or ''
                # Archived means they were forwarded — treat as evaluation/application stage
                applicant_status = 'application'
                updated_at = archive.archived_at
        except Exception:
            pass

    # 3. If still not found, render a clean "not found" page
    if applicant is None and archive is None:
        return render(request, 'public/status_tracker.html', {
            'not_found': True,
            'ref': ref,
        })

    # Resolve pipeline stage
    active_index, pipeline = _resolve_pipeline_stage(applicant_status)
    is_disqualified = (active_index == -1)

    # Build stage list with state flags for the template
    stages = []
    if pipeline:
        for idx, stage in enumerate(pipeline):
            if idx == 0:
                state = 'done'  # Registration is always done if record exists
            elif idx < active_index:
                state = 'done'
            elif idx == active_index:
                state = 'active'
            else:
                state = 'pending'
            stages.append({**stage, 'state': state})

    context = {
        'not_found': False,
        'ref': ref,
        'applicant_name': applicant_name,
        'applicant_status': applicant_status,
        'updated_at': updated_at,
        'stages': stages,
        'is_disqualified': is_disqualified,
        'disqualified_stage': _DISQUALIFIED_STAGE if is_disqualified else None,
        'active_stage': stages[active_index] if (stages and not is_disqualified) else None,
    }
    return render(request, 'public/status_tracker.html', context)
