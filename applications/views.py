from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
import io

from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Exists, OuterRef, Q, Prefetch, Max
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from functools import wraps
from urllib.parse import urlencode
import logging
from accounts.models import FIELD_DESK_POSITIONS
from intake.models import Applicant, Archive, SMSLog as IntakeSMSLog
from intake import sms_workflow
from documents.models import (
    Document,
    LotAwarding,
    Requirement,
    RequirementSubmission,
    document_filed_via_display,
)
from .models import (
    Application,
    QueueEntry,
    CDRRMOCertificationProxy,
    CDRRMOCertification,
    FieldVerificationPhoto,
    EligibilityCheckDecision,
    SMSLog as ApplicationSMSLog,
)
from units.models import (
    HousingUnit,
    LotAward,
    RelocationSite,
    ConstructionProgress,
)
from units.block_lot_sort import block_lot_sort_key
from units.historical_beneficiary import document_vault_applicant_q
from .form_pipeline import applicant_has_signed_application_payload
from .utils import check_blacklist_module2, send_sms_for_applications
from .application_form_pdf import build_filled_application_pdf

MODULE1_MONTHLY_INCOME_CEILING_PESO = 10000
# Application & Evaluation ledger and Ready for Form queue: records per page
MODULE2_EVALUATIONS_LIST_PER_PAGE = 10
MODULE2_READY_FOR_FORM_QUEUE_PER_PAGE = 10
MODULE2_LOT_AWARDING_QUEUE_PER_PAGE = 10
MODULE2_LIST_PER_PAGE = 20
# Routed "Proceed to Form" applicants stay on Ready for Form until Application leaves this pipeline.
_MODULE2_FORM_PIPELINE_STATUSES = frozenset({'draft', 'completed'})
# Minimum years of residence in Talisay City for Module 2 Layer 2 (2.6) eligibility.
# Mirror of `MODULE1_MIN_YEARS_RESIDING_TALISAY` in intake/views.py - keep in sync.
MODULE1_MIN_YEARS_RESIDING_TALISAY = 5
ELIGIBILITY_CHECK_KEYS = frozenset({'property', 'age_residency', 'income', 'household', 'voter'})
# Short labels for readiness hints (Application & Evaluation table).
ELIGIBILITY_CHECK_LABELS = {
    'property': 'Property ownership',
    'age_residency': 'Age and residency',
    'income': 'Income details',
    'household': 'Household composition',
    'voter': 'Registered voters',
}

logger = logging.getLogger(__name__)


def _relative_time_ago(dt):
    """
    Short relative labels from datetime to now (e.g. Just now, 2 hours ago, 1 day ago).

    NOTE: Duplicated from `intake/views.py` to avoid a circular import
    (intake imports applications models).
    """
    if dt is None:
        return '-'
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


def send_sms(recipient_phone, message_content, trigger_event, applicant=None, module='applications'):
    """
    Applications-module SMS: ``send_sms_for_applications`` -> ``intake.utils.send_sms``
    (``SMS_SERVICE=console`` or ``semaphore`` in settings).
    """
    if module != 'applications':
        return False
    return send_sms_for_applications(
        recipient_phone,
        message_content,
        trigger_event,
        applicant=applicant,
    )


# =============================================================================
# POSITION VERIFICATION DECORATOR
# =============================================================================

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


# =============================================================================
# ACCESS CONTROL HELPERS
# =============================================================================

def get_module2_permissions(user):
    """
    Return permissions dict based on user position.
    
    Module 2 Staff Roles:
    - Jocel (4th Member): Verify documents, generate forms, record lot awarding
    - Joie (2nd Member): Supervisor, routing backup, lot awarding backup
    """
    position = user.position

    permissions = {
        'can_view': False,
        'can_verify_documents': False,
        'can_generate_form': False,
        'can_receive_routing': False,
        'can_forward_routing': False,
        'can_award_lot': False,
        'role_description': '',
    }
    
    if position == 'fourth_member':
        # Jocel - Primary processor
        permissions.update({
            'can_view': True,
            'can_verify_documents': True,
            'can_generate_form': True,
            'can_award_lot': True,
            'role_description': 'Document Verification & Lot Awarding',
        })
    elif position == 'second_member':
        # Joie - Supervisor + lot awarding backup (same as award_lot view)
        permissions.update({
            'can_view': True,
            'can_verify_documents': True,  # Supervisor can also verify
            'can_generate_form': True,
            'can_receive_routing': True,  # Supervisor backup for signatory handoff
            'can_forward_routing': True,  # Supervisor backup for signatory handoff
            'can_award_lot': True,
            'role_description': 'Supervisor & Routing Backup',
        })

    return permissions


def _ensure_cdrrmo_pending_after_module2_handoff(applicant):
    """
    Self-heal hazard-declared rows after Intake Archives proceed.

    If a Channel B hazard claim exists and the applicant has an Intake Archive row,
    ensure there is a pending CDRRMO record and that applicant status is
    moved from generic `pending` -> `pending_cdrrmo`.
    """
    if applicant.channel != 'danger_zone':
        return
    if not applicant.archives.exists():
        return
    has_hazard_claim = bool((applicant.danger_zone_type or '').strip() or (applicant.danger_zone_location or '').strip())
    if not has_hazard_claim:
        # Self-heal rows incorrectly forced into pending_cdrrmo.
        if applicant.status == 'pending_cdrrmo':
            applicant.status = 'pending'
            applicant.save(update_fields=['status', 'updated_at'])
        return

    try:
        applicant.cdrrmo_certification
    except CDRRMOCertification.DoesNotExist:
        arch = applicant.archives.order_by('-archived_at').first()
        requested_by = (
            (arch.archived_by if arch else None)
            or getattr(applicant, 'module2_handoff_by', None)
            or applicant.registered_by
            or applicant.eligibility_checked_by
        )
        CDRRMOCertification.objects.create(
            applicant=applicant,
            declared_location=(applicant.danger_zone_location or applicant.danger_zone_type or '').strip() or 'Declared hazard area',
            requested_by=requested_by,
            status='pending',
            disposition_source='pending',
        )

    if applicant.status == 'pending':
        applicant.status = 'pending_cdrrmo'
        applicant.save(update_fields=['status', 'updated_at'])


def _auto_finalize_non_hazard_walkin(applicant, acted_by=None):
    """
    Auto-heal non-hazard handoff rows that should already be queued as Walk-in.

    Applies only when:
    - Applicant has an Intake Archive row (proceeded from Module 1 list)
    - No hazard claim is declared (2.6 is skipped)
    - Record is rule-eligible in Module 2
    - No active queue entry exists yet
    """
    if not applicant.archives.exists():
        return False
    has_hazard_claim = bool((applicant.danger_zone_type or '').strip() or (applicant.danger_zone_location or '').strip())
    if has_hazard_claim:
        return False
    if applicant.queue_entries.filter(status='active').exists():
        return False
    if applicant.status in {'disqualified', 'awarded'}:
        return False

    rules = _module2_eligibility_snapshot(applicant, checked_by=acted_by)
    # Eligibility checks are advisory-only (red indicator); auto-finalize proceeds regardless.

    applicant.status = 'eligible'
    applicant.disqualification_reason = ''
    applicant.eligibility_checked_at = timezone.now()
    update_fields = ['status', 'disqualification_reason', 'eligibility_checked_at', 'updated_at']
    if acted_by and applicant.eligibility_checked_by_id != acted_by.id:
        applicant.eligibility_checked_by = acted_by
        update_fields.append('eligibility_checked_by')
    applicant.save(update_fields=update_fields)
    _ensure_module2_queue_entry(applicant, 'walk_in', added_by=acted_by)
    return True


def _require_intake_archive(applicant):
    """Module 2 gate: applicant must have been proceeded in Intake (Intake Archive row exists)."""
    if applicant.module2_handoff_at:
        return None
    return JsonResponse(
        {
            'success': False,
            'error': (
                'Process 2.1 gate: this applicant has not been proceeded from Module 1 yet. '
                'Use "Proceed to Application" in Intake before running Module 2 actions.'
            ),
        },
        status=400,
    )


def _blacklist_source_label(bl_entry):
    source_map = {
        'units_blacklist': 'Blacklisted Beneficiaries',
    }
    return source_map.get(getattr(bl_entry, 'source', ''), 'Blacklisted Beneficiaries')


def _build_module2_blacklist_disqualification_reason(bl_entry):
    reason = bl_entry.get_reason_display() if bl_entry else 'Blacklist match'
    source_label = _blacklist_source_label(bl_entry)
    policy_note = (getattr(bl_entry, 'policy_note', '') or '').strip()
    notes = (getattr(bl_entry, 'notes', '') or '').strip()
    text = f'On blacklist [{source_label}] ({reason}).'
    if notes:
        text += f' Remarks: {notes[:400]}'
    if policy_note:
        text += f' Policy note: {policy_note}'
    return text


def _auto_disqualify_if_blacklisted(applicant, bl_entry, checked_by=None):
    """
    Persist Module 2 policy: blacklist match immediately disqualifies record.

    NOTE:
    This intentionally writes `Applicant.status = 'disqualified'` and
    `Applicant.disqualification_reason` in intake.models. Keep those fields
    unless this workflow is fully migrated.
    """
    if not bl_entry:
        return False

    reason_text = _build_module2_blacklist_disqualification_reason(bl_entry)
    should_update_reason = (applicant.disqualification_reason or '').strip() != reason_text
    should_update_status = applicant.status != 'disqualified'
    should_update_checker = bool(checked_by) and applicant.eligibility_checked_by_id != checked_by.id
    has_active_queue = applicant.queue_entries.filter(status='active').exists()
    changed = should_update_reason or should_update_status or should_update_checker

    if changed:
        applicant.status = 'disqualified'
        applicant.disqualification_reason = reason_text
        applicant.eligibility_checked_at = timezone.now()
        update_fields = ['status', 'disqualification_reason', 'eligibility_checked_at', 'updated_at']
        if checked_by:
            applicant.eligibility_checked_by = checked_by
            update_fields.append('eligibility_checked_by')
        applicant.save(update_fields=update_fields)

    if has_active_queue:
        _deactivate_active_queue_entries(applicant)
        changed = True

    return changed


def _require_module2_blacklist_clear(applicant):
    """
    Module 2 workflow step 2.1: blacklist check is a hard gate.
    If matched, auto-disqualify and block further Module 2 actions.
    """
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
        return None

    _auto_disqualify_if_blacklisted(applicant, bl_entry)
    reason_text = _build_module2_blacklist_disqualification_reason(bl_entry)
    return JsonResponse({
        'success': False,
        'error': (
            'Applicant is blacklisted and has been automatically disqualified. '
            f'{reason_text}'
        ),
    }, status=400)


def _deactivate_active_queue_entries(applicant):
    applicant.queue_entries.filter(status='active').update(
        status='removed',
        completed_at=timezone.now(),
    )


def _ensure_module2_queue_entry(applicant, queue_type, added_by=None):
    """
    Ensure one active queue entry for the selected Module 2 queue type.
    """
    queue_type = (queue_type or '').strip().lower()
    if queue_type not in {'priority', 'walk_in'}:
        raise ValueError('Invalid queue type')

    active_entries = list(
        applicant.queue_entries.filter(status='active').order_by('entered_at', 'position')
    )
    if active_entries and active_entries[0].queue_type == queue_type:
        return active_entries[0], False

    if active_entries:
        _deactivate_active_queue_entries(applicant)

    for _ in range(3):
        last_position = QueueEntry.objects.filter(
            queue_type=queue_type,
            status='active',
        ).order_by('-position').values_list('position', flat=True).first() or 0
        try:
            with transaction.atomic():
                entry = QueueEntry.objects.create(
                    applicant=applicant,
                    queue_type=queue_type,
                    position=last_position + 1,
                    status='active',
                    added_by=added_by,
                )
            return entry, True
        except IntegrityError:
            continue

    existing = applicant.queue_entries.filter(status='active', queue_type=queue_type).order_by('entered_at').first()
    if existing:
        return existing, False
    raise RuntimeError('Unable to allocate queue position')


def _module2_eligibility_snapshot(applicant, checked_by=None):
    """
    Single rule engine for Module 2 eligibility and queue recommendation.
    """
    blockers = []
    advisories = []
    is_bl, bl_entry = check_blacklist_module2(
        applicant.full_name,
        applicant.phone_number or None,
        applicant_id=applicant.id,
        last_name=applicant.last_name,
        first_name=applicant.first_name,
        date_of_birth=applicant.date_of_birth,
        barangay_id=applicant.barangay_id,
    )
    blacklist_detail = ''
    blacklist_source = ''
    blacklist_policy_note = ''
    if is_bl and bl_entry:
        blacklist_source = _blacklist_source_label(bl_entry)
        blacklist_policy_note = (getattr(bl_entry, 'policy_note', '') or '').strip()
        blacklist_detail = bl_entry.get_reason_display()
        if bl_entry.notes:
            blacklist_detail += f' - {bl_entry.notes[:200]}'
        advisories.append(f'Blacklist match [{blacklist_source}] ({blacklist_detail}).')
        if blacklist_policy_note:
            advisories.append(blacklist_policy_note)

    # Layer 2 profile checks - kept for API / Evaluate modal (passed vs failed).
    # Policy: these do NOT restrict Priority vs Walk-in queue placement.
    income_ok = bool(applicant.is_income_eligible)

    property_ok = not bool(applicant.has_property_in_talisay)

    declared_household = int(applicant.household_size or 0)
    listed_household = applicant.household_members.count() + 1
    has_min_household = declared_household >= 1
    if not has_min_household:
        advisories.append('Declared household size must be at least 1.')

    live_in_partner_count = applicant.household_members.filter(
        relationship='live_in_partner'
    ).count()
    household_has_live_in_partner = live_in_partner_count > 0
    household_ok = has_min_household and not household_has_live_in_partner

    voter_ok = bool(applicant.is_registered_voter_talisay)

    try:
        years_residing_int = int(applicant.years_residing or 0)
    except (TypeError, ValueError):
        years_residing_int = 0
    residency_ok = years_residing_int >= MODULE1_MIN_YEARS_RESIDING_TALISAY

    # Retained for any legacy templates/consumers; queue policy no longer
    # depends on size mismatch.
    household_mismatch = declared_household > 0 and declared_household != listed_household

    displacement_reason = (applicant.displacement_reason or '').strip()
    # Layer 3 complete when any of A / B / C / D (not_abc) is recorded.
    displacement_reasons_all = ('danger_zone', 'ejected', 'relocated', 'not_abc')
    # Priority queue only for A, B, or C; Option D (not_abc) is always walk-in.
    displacement_reasons_priority = ('danger_zone', 'ejected', 'relocated')
    displacement_classified = displacement_reason in displacement_reasons_all
    if not displacement_classified:
        advisories.append('Module 2 Layer 3 displacement classification has not been recorded yet.')
    if displacement_reason == 'not_abc':
        advisories.append(
            'Option D (none of A, B, or C): hazard-area, ejection, and government-project situations do not apply.'
        )

    requires_cdrrmo = bool((applicant.danger_zone_type or '').strip() or (applicant.danger_zone_location or '').strip())
    cdrrmo_status = None
    if requires_cdrrmo:
        try:
            cdrrmo_status = applicant.cdrrmo_certification.status
        except CDRRMOCertification.DoesNotExist:
            cdrrmo_status = None

    # Informational: all Layer 2 profile checks pass (for dashboards / detail API).
    layer2_clear = bool(
        property_ok and income_ok and household_ok and voter_ok and residency_ok
    )
    layer3_clear = bool(displacement_classified)

    # Queue mapping policy (Module 2):
    # - Layer 1 (blacklist): advisory for staff; see blockers in API.
    # - Layer 2: does NOT determine Priority vs Walk-in (income, property, voter,
    #   residency, live-in partner are not routing constraints).
    # - Applicant Situation (A/B/C vs D) drives queue: A/B/C may use Priority
    #   (recommended) or Walk-in; Option D is Walk-in only.
    qualifies_for_priority = bool(displacement_reason in displacement_reasons_priority)

    if displacement_reason in displacement_reasons_priority:
        allowed_queue_types = ['priority', 'walk_in']
        recommended_queue_type = 'priority'
    else:
        allowed_queue_types = ['walk_in']
        recommended_queue_type = 'walk_in'

    # Readiness checks that combine Applicant Profile + Documents + Queue/Application context.
    required_group_a_doc_types = list(
        Requirement.objects.filter(
            group='A',
            is_active=True,
            is_required_for_form=True,
        ).exclude(
            vault_document_type='',
        ).values_list('vault_document_type', flat=True)
    )
    required_docs_total = len(required_group_a_doc_types)
    scanned_required_docs = 0
    if required_docs_total > 0:
        scanned_required_docs = applicant.documents.filter(
            document_type__in=required_group_a_doc_types,
        ).values('document_type').distinct().count()
    required_docs_complete = (required_docs_total == 0) or (scanned_required_docs >= required_docs_total)

    if requires_cdrrmo:
        if cdrrmo_status == 'pending':
            certification_status = 'pending'
        elif cdrrmo_status == 'certified':
            certification_status = 'certified'
        elif cdrrmo_status == 'not_certified':
            certification_status = 'not_certified'
        else:
            certification_status = 'missing'
    else:
        certification_status = 'not_required'

    disposition_source = ''
    if requires_cdrrmo and hasattr(applicant, 'cdrrmo_certification'):
        disposition_source = (applicant.cdrrmo_certification.disposition_source or '').strip()
    field_evidence_required = bool(requires_cdrrmo and disposition_source == 'field_unit')
    field_photos_count = 0
    if field_evidence_required and hasattr(applicant, 'cdrrmo_certification'):
        field_photos_count = applicant.cdrrmo_certification.field_photos.count()
    if not field_evidence_required:
        field_evidence_status = 'not_required'
    elif field_photos_count > 0:
        field_evidence_status = 'available'
    elif certification_status == 'pending':
        field_evidence_status = 'pending'
    else:
        field_evidence_status = 'missing'

    active_queue = applicant.queue_entries.filter(status='active').exists()
    queue_ready = bool(active_queue or applicant.status != 'eligible')
    # Layer 2 no longer gates "readiness" for queue / workflow handoffs.
    basic_eligibility_ok = True
    certification_ready = certification_status in ('not_required', 'certified', 'not_certified')
    field_evidence_ready = field_evidence_status in ('not_required', 'available', 'pending')
    # Applicant Situation documentary evidence:
    # Option A uses CDRRMO + field verification gates (not ISF situational uploads).
    # Options B/C require at least one ISF situational supporting document.
    situation_docs_required = displacement_reason in ('ejected', 'relocated')
    situation_docs_count = applicant.documents.filter(document_type='isf_situational_docs').count() if situation_docs_required else 0
    situation_docs_ready = (not situation_docs_required) or (situation_docs_count > 0)

    # Module 2 eligibility checklist aggregation.
    # The 5 reviewer checks each persist as an EligibilityCheckDecision row.
    # Any row with status='failed' puts the applicant in Pending Follow-up;
    # form generation is blocked until all 5 are decided AND none are failed.
    check_decisions = list(applicant.eligibility_check_decisions.all())
    decided_check_keys = {d.check_key for d in check_decisions}
    failed_check_decisions = [d for d in check_decisions if d.status == 'failed']
    has_failed_checks = bool(failed_check_decisions)
    all_checks_decided = decided_check_keys.issuperset(ELIGIBILITY_CHECK_KEYS)
    failed_check_keys = sorted(d.check_key for d in failed_check_decisions)

    form_generation_ready = bool(
        required_docs_complete
        and not is_bl
        and displacement_classified
        and certification_ready
        and field_evidence_ready
        and situation_docs_ready
        and queue_ready
        and all_checks_decided
        and not has_failed_checks
    )

    # Subtitle under Eligibility status chip - mirrors template branch order.
    readiness_hint = ''
    if not is_bl:
        if not required_docs_complete:
            readiness_hint = (
                f'Compliance: finish baseline scans ({scanned_required_docs}/{required_docs_total} required document types in vault).'
            )
        elif situation_docs_required and not situation_docs_ready:
            readiness_hint = (
                'Compliance: upload ISF situational documentation for this applicant situation (Options B or C).'
            )
        elif certification_status == 'pending':
            readiness_hint = (
                'Compliance: complete or await CDRRMO certification for hazard-area applicants.'
            )
        elif field_evidence_required and field_evidence_status == 'missing':
            readiness_hint = (
                'Compliance: attach at least one Ronda / field verification photo on the CDRRMO record.'
            )
        elif has_failed_checks:
            labels = [ELIGIBILITY_CHECK_LABELS.get(k, k.replace('_', ' ')) for k in failed_check_keys]
            readiness_hint = (
                'Compliance: failed checklist - '
                + ', '.join(labels)
                + '. Correct records or documents, then re-mark each as Passed to reach Ready for Form.'
            )
        elif form_generation_ready:
            readiness_hint = ''
        else:
            if not displacement_classified:
                readiness_hint = (
                    'Compliance: record Applicant Situation (Option A/B/C/D) before readiness can finalize.'
                )
            elif not queue_ready:
                readiness_hint = (
                    'Compliance: finish the Applicant Situation step from Evaluate '
                    '(checklist -> situation modal -> Continue / certify).'
                )
            elif not all_checks_decided:
                pending_n = len(ELIGIBILITY_CHECK_KEYS - decided_check_keys)
                readiness_hint = (
                    f'Compliance: decide all five eligibility checks ({pending_n} still not marked Passed or Failed).'
                )
            elif not certification_ready:
                readiness_hint = (
                    'Compliance: resolve CDRRMO certification status for this applicant.'
                )
            elif not field_evidence_ready:
                readiness_hint = (
                    'Compliance: complete required field verification evidence.'
                )
            else:
                readiness_hint = (
                    'Compliance: finish remaining Module 2 evaluation steps before Ready for Form.'
                )

    return {
        'eligible': len(blockers) == 0,
        'blockers': blockers,
        'advisories': advisories,
        'blacklist_blocked': is_bl,
        'blacklist_detail': blacklist_detail,
        'blacklist_source': blacklist_source,
        'blacklist_policy_note': blacklist_policy_note,
        'income_ok': income_ok,
        'property_ok': property_ok,
        'household_ok': household_ok,
        'household_mismatch': household_mismatch,
        'household_has_live_in_partner': household_has_live_in_partner,
        'live_in_partner_count': live_in_partner_count,
        'declared_household_size': declared_household,
        'listed_household_size': listed_household,
        'voter_ok': voter_ok,
        'is_registered_voter_talisay': bool(applicant.is_registered_voter_talisay),
        'residency_ok': residency_ok,
        'years_residing': years_residing_int,
        'min_years_residing_talisay': MODULE1_MIN_YEARS_RESIDING_TALISAY,
        'requires_cdrrmo': requires_cdrrmo,
        'cdrrmo_status': cdrrmo_status,
        'layer2_clear': layer2_clear,
        'layer3_clear': layer3_clear,
        'qualifies_for_priority': qualifies_for_priority,
        'allowed_queue_types': allowed_queue_types,
        'recommended_queue_type': recommended_queue_type,
        'displacement_reason': displacement_reason,
        'displacement_classified': displacement_classified,
        # Extended evaluator payload for "Evaluate Eligibility and Application Readiness"
        'basic_eligibility_ok': basic_eligibility_ok,
        'certification_required': bool(requires_cdrrmo),
        'certification_status': certification_status,
        'field_evidence_required': field_evidence_required,
        'field_evidence_status': field_evidence_status,
        'field_photos_count': field_photos_count,
        'required_docs_total': required_docs_total,
        'required_docs_scanned': scanned_required_docs,
        'required_docs_complete': required_docs_complete,
        'situation_docs_required': situation_docs_required,
        'situation_docs_count': situation_docs_count,
        'situation_docs_ready': situation_docs_ready,
        'queue_ready': queue_ready,
        'has_failed_checks': has_failed_checks,
        'failed_check_keys': failed_check_keys,
        'all_checks_decided': all_checks_decided,
        'decided_check_count': len(decided_check_keys),
        'required_check_count': len(ELIGIBILITY_CHECK_KEYS),
        'form_generation_ready': form_generation_ready,
        'readiness_hint': readiness_hint,
    }


def _module2_run_handoff_preflight(request_user):
    """Self-heal handoff/CDRRMO/queue rows before Module 2 list views."""
    Applicant.objects.filter(
        channel='danger_zone',
        status='pending_cdrrmo',
        danger_zone_type='',
        danger_zone_location='',
    ).update(status='pending', updated_at=timezone.now())

    hazard_handoff_candidates = Applicant.objects.filter(
        channel='danger_zone',
        module2_handoff_at__isnull=False,
        status__in=['pending', 'pending_cdrrmo'],
    ).select_related(
        'registered_by',
        'module2_handoff_by',
        'eligibility_checked_by',
    )
    for candidate in hazard_handoff_candidates:
        _ensure_cdrrmo_pending_after_module2_handoff(candidate)

    non_hazard_handoff_candidates = Applicant.objects.filter(
        module2_handoff_at__isnull=False,
        status__in=['pending', 'eligible'],
    ).filter(
        Q(danger_zone_type__isnull=True) | Q(danger_zone_type=''),
        Q(danger_zone_location__isnull=True) | Q(danger_zone_location=''),
    ).exclude(
        queue_entries__status='active',
    ).distinct().select_related('eligibility_checked_by')
    for candidate in non_hazard_handoff_candidates:
        _auto_finalize_non_hazard_walkin(candidate, acted_by=request_user)


_MODULE2_EVALUATION_ACTIVE_STATUSES = (
    'pending',
    'pending_cdrrmo',
    'pending_followup',
    'eligible',
    'requirements',
    'application',
    'standby',
    'awarded',
)


def _module1_staff_handled_user(applicant):
    """Staff who proceeded from Module 1 (handoff), else encoder."""
    return getattr(applicant, 'module2_handoff_by', None) or applicant.registered_by


def _staff_handled_display(user):
    """Initials + labels for Staff column (matches intake / field desk)."""
    if not user:
        return {
            'staff_user': None,
            'staff_initials': '',
            'staff_name': '',
            'staff_role': '',
            'staff_position_key': '',
        }
    first = (user.first_name or '')[:1]
    last = (user.last_name or '')[:1]
    initials = (first + last).upper() or '??'
    position_key = getattr(user, 'position', '') or ''
    role = (
        user.get_position_display_short()
        if hasattr(user, 'get_position_display_short')
        else (user.get_position_display() if position_key else '')
    )
    return {
        'staff_user': user,
        'staff_initials': initials,
        'staff_name': user.get_full_name(),
        'staff_role': role,
        'staff_position_key': position_key,
    }


def _module2_evaluations_applicants_queryset():
    """
    Applicants shown on Application & Evaluation (Module 2 handoff + baseline Group A scans).

    Handed-off applicants who were auto-disqualified (e.g. blacklist) remain visible so staff
    see the same record they promoted from Intake - not a silent drop after proceed SMS.
    """
    applicants = Applicant.objects.filter(
        Q(status__in=_MODULE2_EVALUATION_ACTIVE_STATUSES)
        | Q(status='disqualified', module2_handoff_at__isnull=False)
    ).filter(
        Q(module2_handoff_at__isnull=False) | Q(application__isnull=False)
    ).exclude(
        document_vault_applicant_q()
    ).exclude(
        evaluation_approval_status='approved'
    )

    required_group_a_doc_types = list(
        Requirement.objects.filter(
            group='A',
            is_active=True,
            is_required_for_form=True,
        ).exclude(
            vault_document_type='',
        ).values_list('vault_document_type', flat=True)
    )
    required_group_a_total = len(required_group_a_doc_types)
    if required_group_a_total > 0:
        applicants = applicants.annotate(
            scanned_required_group_a=Count(
                'documents',
                filter=Q(documents__document_type__in=required_group_a_doc_types),
                distinct=True,
            )
        ).filter(
            Q(module2_handoff_at__isnull=False)
            | Q(scanned_required_group_a__gte=required_group_a_total)
        )

    return applicants.select_related(
        'application',
        'cdrrmo_certification',
        'registered_by',
        'module2_handoff_by',
    ).prefetch_related(
        'requirement_submissions',
        'requirement_submissions__requirement',
    ).order_by('module2_handoff_at', 'created_at', 'id')


def _module2_application_overall_snapshot(application):
    """Fields merged into eligibility_snapshot ``overall`` for ledger / polling parity."""
    if not application:
        return {
            'has_application': False,
            'application_number': '',
            'application_status': '',
            'application_stage_label': '',
        }
    st = (application.status or '').strip()
    num = (application.application_number or '').strip()
    if st == 'awarded':
        stage = 'Lot Awarded'
    elif st == 'standby':
        stage = 'Fully Approved'
    elif st in ('draft', 'completed'):
        stage = 'Form Released'
    else:
        stage = 'Form Released'
    return {
        'has_application': True,
        'application_number': num,
        'application_status': st,
        'application_stage_label': stage,
    }


def _ready_for_form_situation_priority(displacement_reason) -> int:
    """
    Applicant Situation tier for queue ordering (lower = served first).

    Used by Ready for Form and Lot Awarding queues: Option A (danger zone), then C, B, D.
    Unknown/unset values sort after D.
    """
    dr = (displacement_reason or '').strip()
    return {
        'danger_zone': 0,
        'relocated': 1,
        'ejected': 2,
        'not_abc': 3,
    }.get(dr, 99)


def _module2_on_ready_for_form_queue_track(applicant, application):
    """True while the applicant belongs on Ready for Form (hidden from the main ledger)."""
    if not getattr(applicant, 'form_queue_routed_at', None):
        return False
    if application is None:
        return True
    return application.status in _MODULE2_FORM_PIPELINE_STATUSES


def _module2_applicant_row_payload(applicant, permissions, required_group_a_submission_total, acted_by_user):
    """
    Build one Application & Evaluation row dict.
    Returns None if the applicant is blacklist-gated out of the payload.
    """
    rules = _module2_eligibility_snapshot(applicant, checked_by=acted_by_user)
    blacklist_blocked = rules['blacklist_blocked']
    blacklist_detail = rules['blacklist_detail']
    blacklist_source = rules['blacklist_source']
    blacklist_policy_note = rules['blacklist_policy_note']

    if blacklist_blocked:
        _, bl_entry = check_blacklist_module2(
            applicant.full_name,
            applicant.phone_number or None,
            applicant_id=applicant.id,
            last_name=applicant.last_name,
            first_name=applicant.first_name,
            date_of_birth=applicant.date_of_birth,
            barangay_id=applicant.barangay_id,
        )
        _auto_disqualify_if_blacklisted(applicant, bl_entry, checked_by=acted_by_user)

    application = getattr(applicant, 'application', None)

    # RequirementSubmission counts reflect Module 1 "List of Applicants" only - informational on this screen.
    group_a_verified = RequirementSubmission.objects.filter(
        applicant_id=applicant.id,
        requirement__group='A',
        status='verified',
    ).count()

    can_generate_form = (
        permissions['can_generate_form']
        and application is None
        and rules.get('form_generation_ready')
        and (applicant.displacement_reason or '').strip() in {'danger_zone', 'ejected', 'relocated', 'not_abc'}
    )

    if application and application.status == 'awarded':
        current_stage = 'Lot Awarded'
    elif application and application.status == 'standby':
        current_stage = 'Fully Approved'
    elif application and application.status == 'draft':
        current_stage = 'Form Released · awaiting signed scan'
    elif application and application.status == 'completed':
        current_stage = 'Awaiting final approval'
    elif rules.get('form_generation_ready'):
        current_stage = 'Document Gathering'
    elif applicant.module2_handoff_at:
        current_stage = 'Document Gathering'
    else:
        current_stage = 'Eligibility'

    user_actions = []
    if permissions['can_verify_documents'] and not application:
        user_actions.append('verify_docs')
    if can_generate_form:
        user_actions.append('generate_form')
    if permissions['can_award_lot'] and application and application.status == 'standby':
        user_actions.append('award_lot')

    signed_scan_present = (
        applicant_has_signed_application_payload(applicant)
        if application is not None
        else False
    )

    signed_application_view_url = ''
    signed_application_existing_file_label = ''
    if signed_scan_present:
        _sa_doc = (
            Document.objects.filter(applicant=applicant, document_type='signed_application')
            .order_by('-uploaded_at', '-id')
            .first()
        )
        if _sa_doc:
            signed_application_view_url = reverse(
                'documents:blob_download',
                kwargs={'position': acted_by_user.position, 'doc_id': _sa_doc.pk},
            )
            signed_application_existing_file_label = (
                (_sa_doc.file_name or '').strip()
                or (_sa_doc.title or '').strip()
                or 'Signed application'
            )

    signed_form_vault_url = ''
    signed_form_vault_url_scan = ''
    signed_form_vault_url_upload = ''
    if application is not None and application.status == 'draft':
        _vault_base = {
            'search': ((applicant.reference_number or '').strip() or str(applicant.pk)),
            'applicant_id': str(applicant.pk),
            'open_upload': '1',
            'document_type': 'signed_application',
        }
        _path = reverse('documents:management', kwargs={'position': acted_by_user.position})
        signed_form_vault_url_scan = f"{_path}?{urlencode({**_vault_base, 'intent': 'scan'})}"
        signed_form_vault_url_upload = f"{_path}?{urlencode({**_vault_base, 'intent': 'upload'})}"
        signed_form_vault_url = signed_form_vault_url_upload

    proceeded_dt = applicant.module2_handoff_at or applicant.created_at
    proceeded_ago = _relative_time_ago(proceeded_dt) if proceeded_dt else '-'
    routed_dt = applicant.form_queue_routed_at or proceeded_dt
    routed_ago = _relative_time_ago(routed_dt) if routed_dt else '-'
    staff_display = _staff_handled_display(_module1_staff_handled_user(applicant))

    return {
        'applicant': applicant,
        **staff_display,
        'application': application,
        'proceededAgo': proceeded_ago,
        'routedAgo': routed_ago,
        'routed_sort_at': routed_dt,
        'form_queue_routed_at': applicant.form_queue_routed_at,
        'form_queue_routed_by': applicant.form_queue_routed_by,
        'applicant_status': applicant.status,
        'applicant_status_display': applicant.get_status_display(),
        'cdrrmo_status': getattr(getattr(applicant, 'cdrrmo_certification', None), 'status', None),
        'group_a_verified': group_a_verified,
        'can_generate_form': can_generate_form and application is None,
        'form_generated': application is not None,
        'current_stage': current_stage,
        'user_actions': user_actions,
        'blacklist_blocked': blacklist_blocked,
        'blacklist_detail': blacklist_detail,
        'blacklist_source': blacklist_source,
        'blacklist_policy_note': blacklist_policy_note,
        'm1_income_eligible': applicant.is_income_eligible,
        'm1_declares_no_property': not applicant.has_property_in_talisay,
        'm1_voter_eligible': bool(applicant.is_registered_voter_talisay),
        'm1_residency_eligible': bool(rules.get('residency_ok')),
        'household_size': applicant.household_size,
        'm2_rules': rules,
        'm2_evaluator': rules,
        'signed_application_scan_present': signed_scan_present,
        'signed_application_existing_file_label': signed_application_existing_file_label,
        'signed_application_view_url': signed_application_view_url,
        'signed_form_vault_url': signed_form_vault_url,
        'signed_form_vault_url_scan': signed_form_vault_url_scan,
        'signed_form_vault_url_upload': signed_form_vault_url_upload,
    }


# =============================================================================
# MAIN APPLICATIONS LIST VIEW
# =============================================================================

@login_required
@verify_position
def applications_list(request, position):
    """
    Module 2 - Housing Application & Eligibility
    Shows eligible applicants with document checklist progress and application workflow stages.

    URL: /applications/<position>/list/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Full access: verify docs, generate forms, award lots
    ✅ Joie (2nd Member) - Supervisor: verify docs and routing
    """
    # Check access
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. Module 2 is for authorized staff only.')
        return redirect('accounts:dashboard')
    
    # Get user permissions
    permissions = get_module2_permissions(request.user)

    _module2_run_handoff_preflight(request.user)

    applicants = _module2_evaluations_applicants_queryset()

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
        ).exclude(
            form_queue_routed_at__isnull=False,
            application__status__in=['draft', 'completed'],
        ).count(),
        'awaiting_final_approval': applicants.filter(application__status='completed').distinct().count(),
        'fully_approved': applicants.filter(
            application__status='standby'
        ).count(),
        'lot_awarded': applicants.filter(
            application__status='awarded'
        ).count(),
    }
    
    required_group_a_submission_total = Requirement.objects.filter(
        group='A',
        is_active=True,
        is_required_for_form=True,
    ).count()

    # Prepare applicant data with document counts
    applicants_data = []
    ready_for_form_queue_count = 0
    for applicant in applicants:
        row = _module2_applicant_row_payload(
            applicant,
            permissions,
            required_group_a_submission_total,
            request.user,
        )
        if row is None:
            continue
        on_rfq_track = _module2_on_ready_for_form_queue_track(applicant, row['application'])
        if on_rfq_track:
            ready_for_form_queue_count += 1
        # Routed Proceed-to-Form applicants stay on Ready for Form until Application advances past draft/completed.
        if on_rfq_track:
            continue
        # Once the same routed record is pushed to lot-awarding track (and later awarded),
        # keep it out of the main Application & Evaluation ledger.
        app_status = (getattr(row.get('application'), 'status', '') or '').strip()
        if getattr(applicant, 'form_queue_routed_at', None) and app_status in {'standby', 'awarded'}:
            continue
        applicants_data.append(row)
    
    # Filter by stage if requested
    filter_stage = request.GET.get('stage', 'all')
    if filter_stage != 'all':
        stage_map = {
            'eligibility': 'Eligibility',
            'document_gathering': 'Document Gathering',
            'form_released': 'Form Released',
            'awaiting_final_approval': 'Awaiting final approval',
            'fully_approved': 'Fully Approved',
            'lot_awarded': 'Lot Awarded',
        }
        target_stage = stage_map.get(filter_stage)
        if target_stage:
            applicants_data = [a for a in applicants_data if a['current_stage'] == target_stage]

    # Search filter (server-side across full list before pagination)
    search = request.GET.get('search', '').strip()
    if search:
        search_lower = search.lower()
        txn_fragment = search_lower.lstrip('#')

        def _evaluation_row_matches(row):
            applicant = row['applicant']
            barangay_name = (
                applicant.barangay.name if getattr(applicant, 'barangay', None) else ''
            )
            if (
                search_lower in (applicant.full_name or '').lower()
                or search_lower in (applicant.reference_number or '').lower()
                or search_lower in barangay_name.lower()
                or txn_fragment in str(applicant.id).lower()
            ):
                return True
            if 'blacklist' in search_lower and row.get('blacklist_blocked'):
                return True
            return False

        applicants_data = [a for a in applicants_data if _evaluation_row_matches(a)]

    paginator = Paginator(applicants_data, MODULE2_EVALUATIONS_LIST_PER_PAGE)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    # Preserve filter query string for pagination links (exclude `page`)
    _q = request.GET.copy()
    _q.pop('page', None)
    pagination_query = _q.urlencode()

    from_intake_handoff = request.GET.get('from') == 'intake_scan_checklist'
    intake_handoff_ref = (request.GET.get('ref') or '').strip()[:120]

    context = {
        'applicants_data': list(page_obj),
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'stage_counts': stage_counts,
        'requirements': requirements,
        'group_a_requirements': group_a_requirements,
        'group_b_requirements': group_b_requirements,
        'filter_stage': filter_stage,
        'search': search,
        'total_eligible': applicants.count(),
        'permissions': permissions,
        'user_position': request.user.position,
        'from_intake_handoff': from_intake_handoff,
        'intake_handoff_ref': intake_handoff_ref,
        'ready_for_form_queue_count': ready_for_form_queue_count,
        'vacant_units_by_site': (
            vacant_units_grouped_for_award_select() if permissions.get('can_award_lot') else []
        ),
    }
    
    return render(request, 'staff/applications_list.html', context)


def module2_ready_for_form_queue_rows(acting_user):
    """
    Ready for Form queue rows (same filter/sort as ready_for_form_queue view).
    Returns list of _module2_applicant_row_payload dicts.
    """
    permissions = get_module2_permissions(acting_user)
    _module2_run_handoff_preflight(acting_user)
    applicants = _module2_evaluations_applicants_queryset()
    required_group_a_submission_total = Requirement.objects.filter(
        group='A',
        is_active=True,
        is_required_for_form=True,
    ).count()

    applicants_data = []
    for applicant in applicants:
        row = _module2_applicant_row_payload(
            applicant,
            permissions,
            required_group_a_submission_total,
            acting_user,
        )
        if row is None:
            continue
        if _module2_on_ready_for_form_queue_track(applicant, row['application']):
            applicants_data.append(row)

    applicants_data.sort(
        key=lambda r: (
            _ready_for_form_situation_priority(getattr(r['applicant'], 'displacement_reason', None)),
            r.get('routed_sort_at') is None,
            r.get('routed_sort_at') or timezone.now(),
            str(r['applicant'].pk),
        ),
    )
    return applicants_data


@login_required
@verify_position
def ready_for_form_queue(request, position):
    """
    Routed Proceed-to-Form queue: pending Generate Form, then Form Released pipeline (draft/completed)
    until fully approved - hidden from the main Application & Evaluation ledger during that window.
    URL: /applications/<position>/ready-for-form/
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. Module 2 is for authorized staff only.')
        return redirect('accounts:dashboard')

    permissions = get_module2_permissions(request.user)

    requirements = Requirement.objects.filter(is_active=True).order_by('group', 'order')
    group_a_requirements = requirements.filter(group='A')
    group_b_requirements = requirements.filter(group='B')

    required_group_a_submission_total = Requirement.objects.filter(
        group='A',
        is_active=True,
        is_required_for_form=True,
    ).count()

    applicants_data = module2_ready_for_form_queue_rows(request.user)

    ready_queue_total = len(applicants_data)

    selected_applicant_id = (request.GET.get('applicant_id') or '').strip()
    from_source = (request.GET.get('from') or '').strip()
    search = request.GET.get('search', '').strip()
    if search:
        search_lower = search.lower()
        applicants_data = [
            a for a in applicants_data
            if search_lower in a['applicant'].full_name.lower()
            or search_lower in (a['applicant'].reference_number or '').lower()
        ]

    selected_row_included = False
    selected_not_ready_reason = ''
    selected_queue_index = None
    if selected_applicant_id:
        selected_idx = next(
            (i for i, row in enumerate(applicants_data) if str(getattr(row['applicant'], 'id', '')) == selected_applicant_id),
            None,
        )
        if selected_idx is not None:
            selected_row_included = True
            selected_queue_index = selected_idx
        else:
            selected_candidate = Applicant.objects.filter(id=selected_applicant_id).first()
            if selected_candidate is not None:
                selected_payload = _module2_applicant_row_payload(
                    selected_candidate,
                    permissions,
                    required_group_a_submission_total,
                    request.user,
                )
                if selected_payload is not None:
                    selected_not_ready_reason = (
                        selected_payload.get('m2_evaluator', {}).get('readiness_hint')
                        or 'Selected applicant is not currently ready for form generation.'
                    )

    paginator = Paginator(applicants_data, MODULE2_READY_FOR_FORM_QUEUE_PER_PAGE)
    requested_page = request.GET.get('page')
    page_number = requested_page or 1
    if (
        selected_queue_index is not None
        and from_source == 'applications_list'
        and not requested_page
        and not search
    ):
        page_number = (selected_queue_index // MODULE2_READY_FOR_FORM_QUEUE_PER_PAGE) + 1
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    _q = request.GET.copy()
    _q.pop('page', None)
    pagination_query = _q.urlencode()

    context = {
        'applicants_data': list(page_obj),
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'search': search,
        'permissions': permissions,
        'user_position': request.user.position,
        'queue_total': ready_queue_total,
        'requirements': requirements,
        'group_a_requirements': group_a_requirements,
        'group_b_requirements': group_b_requirements,
        'selected_applicant_id': selected_applicant_id,
        'from_source': from_source,
        'selected_row_included': selected_row_included,
        'selected_not_ready_reason': selected_not_ready_reason,
    }
    return render(request, 'staff/ready_for_form_list.html', context)


def _lot_awarding_queue_sms_filter(qs):
    """SMSLog rows that count as lot-awarding queue coordination SMS."""
    marker_q = Q()
    for phrase in sms_workflow.LOT_AWARDING_SMS_BODY_MARKERS:
        marker_q |= Q(message_content__icontains=phrase)
    return qs.filter(
        Q(trigger_event=sms_workflow.PROCEED_TO_LOT_AWARDING)
        | (Q(trigger_event='Applicant Notification') & marker_q),
        status='sent',
    )


def _lot_awarding_queue_sms_stats_by_applicant(applicant_ids):
    """Return {applicant_id: {'count': int, 'last_at': datetime|None}} for queue SMS column."""
    ids = [aid for aid in applicant_ids if aid]
    if not ids:
        return {}
    stats = {aid: {'count': 0, 'last_at': None} for aid in ids}
    for model in (ApplicationSMSLog, IntakeSMSLog):
        rows = (
            _lot_awarding_queue_sms_filter(model.objects.all())
            .filter(applicant_id__in=ids)
            .values('applicant_id')
            .annotate(n=Count('id'), last_at=Max('sent_at'))
        )
        for row in rows:
            aid = row['applicant_id']
            if aid not in stats:
                continue
            stats[aid]['count'] += row['n'] or 0
            last_at = row['last_at']
            if last_at and (
                stats[aid]['last_at'] is None or last_at > stats[aid]['last_at']
            ):
                stats[aid]['last_at'] = last_at
    return stats


@login_required
@verify_position
def lot_awarding_queue(request, position):
    """
    Dedicated lot-awarding queue fed by Ready for Form routing.
    Shows applications on awarding track (standby / fully-approved legacy rows).
    URL: /applications/<position>/lot-awarding-queue/
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. Module 2 is for authorized staff only.')
        return redirect('accounts:dashboard')

    permissions = get_module2_permissions(request.user)

    applications_qs = (
        Application.objects
        .filter(status='standby')
        .exclude(applicant__status='disqualified')
        .select_related('applicant')
        .order_by('standby_position', 'standby_entered_at', '-updated_at')
    )

    queue_rows = []
    for app in applications_qs:
        applicant = app.applicant
        signed_form_on_file = applicant_has_signed_application_payload(applicant)
        vault_base = {
            'applicant_id': str(applicant.pk),
            'document_type': 'signed_application',
            'open_vault': '1',
        }
        vault_path = reverse('documents:management', kwargs={'position': request.user.position})
        routed_dt = app.standby_entered_at or app.updated_at
        queue_rows.append({
            'application': app,
            'applicant': applicant,
            'status_label': 'Ready for awarding',
            'situation_label': applicant.get_displacement_reason_display() if applicant.displacement_reason else '-',
            'routed_at': routed_dt,
            'routedAgo': _relative_time_ago(routed_dt),
            'can_award_lot': bool(permissions.get('can_award_lot')),
            'signed_form_on_file': signed_form_on_file,
            'signed_form_vault_url': f"{vault_path}?{urlencode(vault_base)}",
        })

    # Same Applicant Situation tier order as Ready for Form; FIFO by standby / queue entry time within tier.
    queue_rows.sort(
        key=lambda r: (
            _ready_for_form_situation_priority(getattr(r['applicant'], 'displacement_reason', None)),
            r.get('routed_at') is None,
            r.get('routed_at') or timezone.now(),
            str(r['applicant'].pk),
        ),
    )

    sms_stats = _lot_awarding_queue_sms_stats_by_applicant(
        [r['applicant'].pk for r in queue_rows]
    )
    for row in queue_rows:
        s = sms_stats.get(row['applicant'].pk, {'count': 0, 'last_at': None})
        row['lot_awarding_sms_count'] = s['count']
        row['lot_awarding_sms_last_at'] = s['last_at']

    search = request.GET.get('search', '').strip()
    if search:
        search_lower = search.lower()
        queue_rows = [
            row for row in queue_rows
            if search_lower in (row['applicant'].full_name or '').lower()
            or search_lower in (row['applicant'].reference_number or '').lower()
            or search_lower in (row['application'].application_number or '').lower()
        ]

    queue_total = len(queue_rows)

    paginator = Paginator(queue_rows, MODULE2_LOT_AWARDING_QUEUE_PER_PAGE)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    _q = request.GET.copy()
    _q.pop('page', None)
    pagination_query = _q.urlencode()

    context = {
        'queue_rows': list(page_obj),
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'search': search,
        'permissions': permissions,
        'queue_total': queue_total,
        'vacant_units_by_site': (
            vacant_units_grouped_for_award_select() if permissions.get('can_award_lot') else []
        ),
    }
    return render(request, 'staff/lot_awarding_queue.html', context)


# =============================================================================
# READY FOR FORM QUEUE ROUTING
# =============================================================================

def _applicant_already_received_ready_for_form_reminder_sms(applicant) -> bool:
    """True if the Ready-for-Form reminder SMS was already sent (Proceed to Ready for Form queue)."""
    ev = sms_workflow.READY_FOR_FORM_QUEUE_REMINDER
    if ApplicationSMSLog.objects.filter(applicant=applicant, trigger_event=ev, status='sent').exists():
        return True
    return IntakeSMSLog.objects.filter(applicant=applicant, trigger_event=ev, status='sent').exists()


@login_required
@verify_position
@require_POST
def proceed_to_form_queue(request, position):
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error
    blacklist_error = _require_module2_blacklist_clear(applicant)
    if blacklist_error:
        return blacklist_error
    if hasattr(applicant, 'application'):
        return JsonResponse({'success': False, 'error': 'Application form already generated.'}, status=400)
    if (applicant.displacement_reason or '').strip() not in {'danger_zone', 'ejected', 'relocated', 'not_abc'}:
        return JsonResponse({
            'success': False,
            'error': 'Proceed to Form is available only when Applicant Situation is set (Option A, B, C, or D).',
        }, status=400)

    rules = _module2_eligibility_snapshot(applicant, checked_by=request.user)
    if not rules.get('form_generation_ready'):
        hint = (rules.get('readiness_hint') or '').strip()
        return JsonResponse({
            'success': False,
            'error': hint or 'Applicant is not ready for form generation yet.',
        }, status=400)

    applicant.form_queue_routed_at = timezone.now()
    applicant.form_queue_routed_by = request.user
    applicant.save(update_fields=['form_queue_routed_at', 'form_queue_routed_by', 'updated_at'])

    has_phone = bool((applicant.phone_number or '').strip())
    sms_deduped = has_phone and _applicant_already_received_ready_for_form_reminder_sms(applicant)
    sms_dispatched = False
    if has_phone and not sms_deduped:
        message = sms_workflow.message_ready_for_form_queue_reminder(applicant)
        sms_dispatched = bool(
            send_sms(
                applicant.phone_number,
                message,
                sms_workflow.READY_FOR_FORM_QUEUE_REMINDER,
                applicant=applicant,
                module='applications',
            )
        )

    sms_plan_payload = {
        'active': has_phone,
        'deduped': sms_deduped,
        'dispatched': sms_dispatched,
        'has_phone': has_phone,
        'note': (
            'ready_for_form_queue_reminder SMS already sent for this applicant; not sent again.'
            if sms_deduped
            else (
                'Check runserver or SMSLog (SMS_SERVICE=console simulates delivery).'
                if sms_dispatched
                else (
                    'No phone on applicant.'
                    if not has_phone
                    else 'SMS not logged (invalid number format or send_sms returned false).'
                )
            )
        ),
    }
    logger.info(
        'proceed_to_form_queue ref=%s sms_plan=%s',
        applicant.reference_number,
        sms_plan_payload,
    )
    # Runserver only prints the big SMS banner when send_sms runs; if deduped/no phone, explain here.
    if getattr(settings, 'DEBUG', False):
        print(
            f"\n[proceed_to_form_queue] ref={applicant.reference_number} "
            f"dispatched={sms_dispatched} deduped={sms_deduped} has_phone={has_phone}\n"
            f"  {sms_plan_payload['note']}\n"
        )

    return JsonResponse({
        'success': True,
        'message': 'Applicant moved to Ready for Form queue.',
        'sms_plan': sms_plan_payload,
    })


# =============================================================================
# APPLICATION DETAIL (AJAX)
# =============================================================================

@login_required
@verify_position
def application_detail(request, position, application_id):
    """
    Get applicant/application detail for modal (AJAX).

    URL: /applications/staff/<position>/<application_id>/ (applicant or application UUID)

    Accepts either an Applicant ID or Application ID and returns
    the relevant information for the modal display.
    """
    # Try to find as Applicant first (for pre-application stage)
    applicant = None
    application = None
    
    try:
        applicant = Applicant.objects.prefetch_related(
            Prefetch(
                'archives',
                queryset=Archive.objects.select_related('archived_by').order_by('archived_at'),
            ),
            'requirement_submissions',
            'requirement_submissions__requirement',
            Prefetch(
                'queue_entries',
                queryset=QueueEntry.objects.filter(status='active').order_by('position'),
                to_attr='active_queue_entries',
            ),
            Prefetch(
                'cdrrmo_certification__field_photos',
                queryset=FieldVerificationPhoto.objects.order_by('uploaded_at'),
            ),
        ).get(id=application_id)
        # Check if this applicant has an application
        application = getattr(applicant, 'application', None)
    except Applicant.DoesNotExist:
        # Try as Application ID
        application = get_object_or_404(
            Application.objects.select_related('applicant').prefetch_related(
                Prefetch(
                    'applicant__archives',
                    queryset=Archive.objects.select_related('archived_by').order_by('archived_at'),
                ),
                'applicant__requirement_submissions',
                'applicant__requirement_submissions__requirement',
                Prefetch(
                    'applicant__queue_entries',
                    queryset=QueueEntry.objects.filter(status='active').order_by('position'),
                    to_attr='active_queue_entries',
                ),
                Prefetch(
                    'applicant__cdrrmo_certification__field_photos',
                    queryset=FieldVerificationPhoto.objects.order_by('uploaded_at'),
                ),
            ),
            id=application_id
        )
        applicant = application.applicant
    
    # Get user permissions
    permissions = get_module2_permissions(request.user)

    # Ensure modal reflects hazard workflow after Intake Archives proceed.
    _ensure_cdrrmo_pending_after_module2_handoff(applicant)
    _auto_finalize_non_hazard_walkin(applicant, acted_by=request.user)
    applicant.refresh_from_db()
    # Build response data
    rules = _module2_eligibility_snapshot(applicant, checked_by=request.user)

    data = {
        'applicant_id': str(applicant.id),
        'applicant_name': applicant.full_name,
        'applicant_phone': applicant.phone_number,
        'reference_number': applicant.reference_number,
        'applicant_profile': {
            'last_name': applicant.last_name or '',
            'first_name': applicant.first_name or '',
            'middle_name': applicant.middle_name or '',
            'extension_name': applicant.extension_name or '',
            'sex': applicant.get_sex_display() if applicant.sex else '',
            'years_residing': applicant.years_residing,
            'is_registered_voter_talisay': bool(applicant.is_registered_voter_talisay),
            'date_of_birth': applicant.date_of_birth.isoformat() if applicant.date_of_birth else None,
            'age': applicant.age,
            'place_of_birth': applicant.place_of_birth or '',
            'current_address': applicant.current_address or '',
            'barangay': applicant.barangay.name if applicant.barangay else '',
            'phone_number': applicant.phone_number or '',
            'spouse_name': applicant.spouse_name or '',
            'spouse_phone': applicant.spouse_phone or '',
            'household_size': applicant.household_size,
            'occupation': applicant.occupation or '',
            'employment_status': applicant.get_employment_status_display() if applicant.employment_status else '',
            'monthly_income': float(applicant.monthly_income) if applicant.monthly_income is not None else 0,
            'has_property_in_talisay': bool(applicant.has_property_in_talisay),
            'hazard_declared': bool((applicant.danger_zone_type or '').strip() or (applicant.danger_zone_location or '').strip()),
            'danger_zone_type': applicant.danger_zone_type or '',
            'danger_zone_location': applicant.danger_zone_location or '',
            'displacement_reason': applicant.displacement_reason or '',
            'displacement_reason_display': applicant.get_displacement_reason_display() if applicant.displacement_reason else '',
            'ejection_type': applicant.ejection_type or '',
            'ejection_type_display': applicant.get_ejection_type_display() if applicant.ejection_type else '',
            'ejection_date': applicant.ejection_date.isoformat() if applicant.ejection_date else None,
            'project_name': applicant.project_name or '',
        },
        'requirements': [],
        'has_application': application is not None,
        'permissions': permissions,
        'blacklist_blocked': rules['blacklist_blocked'],
        'blacklist_detail': rules['blacklist_detail'],
        'blacklist_source': rules['blacklist_source'],
        'blacklist_policy_note': rules['blacklist_policy_note'],
        'm1_income_eligible': applicant.is_income_eligible,
        'm1_declares_no_property': not applicant.has_property_in_talisay,
        'm1_voter_eligible': bool(applicant.is_registered_voter_talisay),
        'm1_residency_eligible': bool(rules.get('residency_ok')),
        'household_size': applicant.household_size,
        'm2_rules': rules,
        'cdrrmo': None,
        'applicant_status': applicant.status,
        'applicant_status_display': applicant.get_status_display(),
        'channel': applicant.channel,
        'evaluation_approval_status': applicant.evaluation_approval_status or '',
        'evaluation_approval_status_display': applicant.get_evaluation_approval_status_display() if applicant.evaluation_approval_status else '',
        'evaluation_approval_notes': applicant.evaluation_approval_notes or '',
        'evaluation_approval_by': applicant.evaluation_approval_by.get_full_name() if applicant.evaluation_approval_by else '',
        'evaluation_approval_at': applicant.evaluation_approval_at.isoformat() if applicant.evaluation_approval_at else None,
    }

    # Module 1 CDRRMO snapshot (read-only in Module 2 modal)
    if applicant.channel == 'danger_zone':
        try:
            cert = applicant.cdrrmo_certification
            photo_urls = []
            for ph in cert.field_photos.all():
                if ph.image and ph.image.name:
                    try:
                        photo_urls.append(ph.image.url)
                    except (ValueError, AttributeError):
                        pass
            data['cdrrmo'] = {
                'status': cert.status,  # pending/certified/not_certified
                'status_display': cert.get_status_display(),
                'disposition_source': cert.disposition_source,
                'disposition_source_display': cert.get_disposition_source_display(),
                'declared_location': cert.declared_location or '',
                'recorded_by': cert.result_recorded_by.get_full_name() if cert.result_recorded_by else '',
                'recorded_at': cert.certified_at.isoformat() if cert.certified_at else None,
                'office_intake_notes': cert.office_intake_notes or '',
                'field_notes': cert.certification_notes or '',
                'field_photos': photo_urls,
            }
        except CDRRMOCertification.DoesNotExist:
            data['cdrrmo'] = {
                'status': None,
                'status_display': 'Not Requested',
                'disposition_source': 'pending',
                'disposition_source_display': 'No disposition recorded',
                'declared_location': '',
                'recorded_by': '',
                'recorded_at': None,
                'office_intake_notes': '',
                'field_notes': '',
                'field_photos': [],
            }
    
    if application:
        data.update({
            'id': str(application.id),
            'application_number': application.application_number,
            'status': application.status,
            'status_display': application.get_status_display(),
        })

    # Add requirements status
    for submission in applicant.requirement_submissions.all():
        data['requirements'].append({
            'code': submission.requirement.code,
            'name': submission.requirement.name,
            'group': submission.requirement.group,
            'status': submission.status,
            'verified': submission.status == 'verified',
        })
    
    return JsonResponse(data)


@login_required
@verify_position
@require_POST
def update_cdrrmo_certification(request, position):
    """
    Module 2 endpoint for official CDRRMO disposition recording.
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        decision = request.POST.get('decision')  # certified / not_certified
        notes = request.POST.get('notes', '').strip()
        office_receipt = request.POST.get('office_receipt', '').strip().lower() in ('1', 'true', 'yes', 'on')

        if not applicant_id or not decision:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id or decision'})
        if decision not in ['certified', 'not_certified']:
            return JsonResponse({'success': False, 'error': 'Invalid decision. Must be "certified" or "not_certified"'})

        applicant = Applicant.objects.get(id=applicant_id)
        handoff_error = _require_intake_archive(applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(applicant)
        if blacklist_error:
            return blacklist_error
        if applicant.status != 'pending_cdrrmo':
            return JsonResponse({
                'success': False,
                'error': f'This record is not pending CDRRMO staff finalization (current status: {applicant.get_status_display()}).',
            })

        if not hasattr(applicant, 'cdrrmo_certification'):
            return JsonResponse({'success': False, 'error': 'This applicant is not awaiting CDRRMO certification (not Channel B)'})

        cert = applicant.cdrrmo_certification
        if cert.status != 'pending':
            return JsonResponse({'success': False, 'error': f'CDRRMO decision already made: {cert.get_status_display()}'})

        cert.status = decision
        cert.result_recorded_by = request.user
        cert.certified_at = timezone.now()
        cert.disposition_source = 'office_intake'
        cert.office_intake_notes = notes if notes else ''
        cert.certification_notes = ''
        cert.save()

        applicant.status = 'eligible'
        applicant.disqualification_reason = ''
        applicant.eligibility_checked_by = request.user
        applicant.eligibility_checked_at = timezone.now()
        applicant.save(update_fields=['status', 'disqualification_reason', 'eligibility_checked_by', 'eligibility_checked_at', 'updated_at'])

        if decision == 'certified':
            queue_entry, _ = _ensure_module2_queue_entry(applicant, 'priority', added_by=request.user)

            if applicant.phone_number:
                if office_receipt:
                    sms_msg = (
                        f'THA: Official CDRRMO certification was received and filed at our intake office. '
                        f'Priority queue no. {queue_entry.position}. Ref {applicant.reference_number}. '
                        f'Please visit the Talisay Housing Authority when instructed for next steps.'
                    )
                    sms_event = 'cdrrmo_office_certified'
                else:
                    sms_msg = (
                        f'THA: Your hazard-area certification is on file. Priority queue no. {queue_entry.position}. '
                        f'Ref {applicant.reference_number}. Please visit the Talisay Housing Authority for next steps.'
                    )
                    sms_event = 'cdrrmo_certified'
                sent = send_sms(applicant.phone_number, sms_msg, sms_event, applicant=applicant, module='applications')
                if sent and not applicant.eligibility_sms_sent:
                    applicant.eligibility_sms_sent = True
                    applicant.save(update_fields=['eligibility_sms_sent', 'updated_at'])

            return JsonResponse({
                'success': True,
                'message': f'✅ {applicant.full_name} CERTIFIED as danger zone. Added to Priority Queue (Position {queue_entry.position}).',
                'decision': decision,
                'queue_position': queue_entry.position,
            })

        queue_entry, _ = _ensure_module2_queue_entry(applicant, 'walk_in', added_by=request.user)
        if applicant.phone_number:
            sms_msg = (
                "CDRRMO certification was not provided/verified in Module 2. "
                f"You are currently placed in Walk-in Queue position #{queue_entry.position}. "
                f"Reference: {applicant.reference_number}. Final eligibility processing remains under regular processing rules."
            )
            sent = send_sms(applicant.phone_number, sms_msg, 'cdrrmo_not_certified', applicant=applicant, module='applications')
            if sent and not applicant.eligibility_sms_sent:
                applicant.eligibility_sms_sent = True
                applicant.save(update_fields=['eligibility_sms_sent', 'updated_at'])
        return JsonResponse({
            'success': True,
            'message': (
                f'ℹ️ {applicant.full_name} marked as NOT CERTIFIED and placed in Walk-in Queue '
                f'(Position {queue_entry.position}).'
            ),
            'decision': decision,
            'queue_type': 'walk_in',
            'queue_position': queue_entry.position,
        })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error updating CDRRMO certification: {str(e)}'})


def _layer3_queue_placement_bundle(applicant, acting_user):
    """
    Module 2 Layer 3 follows registration-time displacement encoding; this only
    adjusts queue placement once staff proceed past the acknowledgement step.
    """
    try:
        rules = _module2_eligibility_snapshot(applicant, checked_by=acting_user)
        target_queue = rules.get('recommended_queue_type') or 'walk_in'
        if target_queue not in ('priority', 'walk_in'):
            target_queue = 'walk_in'
        queue_entry, queue_changed = _ensure_module2_queue_entry(
            applicant, target_queue, added_by=acting_user,
        )
        return {
            'queue_type': queue_entry.queue_type,
            'queue_position': queue_entry.position,
            'queue_changed': bool(queue_changed),
            'qualifies_for_priority': bool(rules.get('qualifies_for_priority')),
            'layer2_clear': bool(rules.get('layer2_clear')),
            'layer3_clear': bool(rules.get('layer3_clear')),
            'requires_cdrrmo': bool(rules.get('requires_cdrrmo')),
            'cdrrmo_status': rules.get('cdrrmo_status'),
            'advisories': list(rules.get('advisories') or []),
        }
    except Exception:
        return None


@login_required
@verify_position
@require_POST
def record_displacement_classification(request, position):
    """
    Module 2 - Layer 3 acknowledgement (particulars are captured at Module 1 registration).

    For new applicants, ``review_only=1`` runs queue placement using the
    displacement reason and details already stored on the Applicant record.

    The full POST body (``displacement_reason``, ``hazard_type``, etc.) remains
    supported as a legacy/administrative override when needed.
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        if not applicant_id:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id'})

        applicant = Applicant.objects.get(id=applicant_id)
        handoff_error = _require_intake_archive(applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(applicant)
        if blacklist_error:
            return blacklist_error

        review_only = request.POST.get('review_only') == '1'
        if review_only:
            reason = (applicant.displacement_reason or '').strip()
            if reason not in ('danger_zone', 'ejected', 'relocated', 'not_abc'):
                return JsonResponse({
                    'success': False,
                    'error': (
                        'Displacement classification is not on file. Complete Applicant Situation '
                        'and particulars during Module 1 (Intake registration) first.'
                    ),
                }, status=400)
            queue_placement = _layer3_queue_placement_bundle(applicant, request.user)
            return JsonResponse({
                'success': True,
                'message': 'Layer 3 acknowledged - particulars are on file from Module 1 intake.',
                'displacement_reason': reason,
                'displacement_reason_display': applicant.get_displacement_reason_display(),
                'queue_placement': queue_placement,
                'review_only': True,
            })

        reason = (request.POST.get('displacement_reason') or '').strip()
        if reason not in ('danger_zone', 'ejected', 'relocated', 'not_abc'):
            return JsonResponse({'success': False, 'error': 'Select a valid displacement reason.'})

        applicant.displacement_reason = reason
        update_fields = {'displacement_reason'}

        if reason == 'danger_zone':
            hazard_type = (request.POST.get('hazard_type') or '').strip()
            hazard_location = (request.POST.get('hazard_location') or '').strip()
            if not hazard_type:
                return JsonResponse({'success': False, 'error': 'Hazard Type is required.'})
            if not hazard_location:
                return JsonResponse({'success': False, 'error': 'Hazard Location Details is required.'})
            applicant.danger_zone_type = hazard_type
            applicant.danger_zone_location = hazard_location
            applicant.ejection_type = ''
            applicant.ejection_date = None
            applicant.project_name = ''
            update_fields.update({
                'danger_zone_type', 'danger_zone_location',
                'ejection_type', 'ejection_date', 'project_name',
            })
        elif reason == 'not_abc':
            # Option D: clear A/B/C-specific particulars; no CDRRMO track from this choice.
            applicant.danger_zone_type = ''
            applicant.danger_zone_location = ''
            applicant.ejection_type = ''
            applicant.ejection_date = None
            applicant.project_name = ''
            update_fields.update({
                'danger_zone_type', 'danger_zone_location',
                'ejection_type', 'ejection_date', 'project_name',
            })
        elif reason == 'ejected':
            ej_type = (request.POST.get('ejection_type') or '').strip()
            ej_date_raw = (request.POST.get('ejection_date') or '').strip()
            valid_ejection_types = {
                key for key, _ in Applicant.EJECTION_TYPE_CHOICES if key
            }
            if ej_type not in valid_ejection_types:
                return JsonResponse({'success': False, 'error': 'Select a valid Ejection Type.'})
            ej_date = None
            if ej_date_raw:
                try:
                    from datetime import date as _date
                    ej_date = _date.fromisoformat(ej_date_raw)
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid date of notice or ejection.'})
            applicant.ejection_type = ej_type
            applicant.ejection_date = ej_date
            applicant.danger_zone_type = ''
            applicant.danger_zone_location = ''
            applicant.project_name = ''
            update_fields.update({
                'ejection_type', 'ejection_date',
                'danger_zone_type', 'danger_zone_location', 'project_name',
            })
        else:  # relocated
            project_name = (request.POST.get('project_name') or '').strip()
            if not project_name:
                return JsonResponse({'success': False, 'error': 'Project Name is required.'})
            applicant.project_name = project_name
            applicant.danger_zone_type = ''
            applicant.danger_zone_location = ''
            applicant.ejection_type = ''
            applicant.ejection_date = None
            update_fields.update({
                'project_name',
                'danger_zone_type', 'danger_zone_location',
                'ejection_type', 'ejection_date',
            })

        update_fields.add('updated_at')
        applicant.save(update_fields=list(update_fields))

        # Auto-create a pending CDRRMO certification record when staff classifies
        # the applicant as living in a danger zone, so Module 3 has a record to
        # verify against. Existing certifications are left untouched.
        if reason == 'danger_zone' and not hasattr(applicant, 'cdrrmo_certification'):
            try:
                CDRRMOCertification.objects.create(
                    applicant=applicant,
                    requested_by=request.user,
                    status='pending',
                    declared_location=(applicant.danger_zone_location or applicant.danger_zone_type or '').strip() or 'Declared hazard area',
                    disposition_source='pending',
                )
            except Exception:
                # Non-fatal: Module 3 will still pick up the pending state from
                # the displacement_reason field even if the auxiliary record is
                # missing.
                pass

        # Auto-promote queue placement now that Layer 3 has been classified.
        # Policy: once a displacement reason is recorded AND Layer 2 is clean,
        # the applicant is moved to the Priority Queue immediately - regardless
        # of CDRRMO certification state for danger-zone cases. CDRRMO finalization
        # (`update_cdrrmo_certification` / `update_cdrrmo_status`) still owns the
        # demotion path: a `not_certified` outcome will move the applicant back
        # to Walk-in. If Layer 2 has any flag, the applicant stays on Walk-in.
        queue_placement = _layer3_queue_placement_bundle(applicant, request.user)

        return JsonResponse({
            'success': True,
            'message': f'Layer 3 classification saved: {applicant.get_displacement_reason_display()}.',
            'displacement_reason': reason,
            'displacement_reason_display': applicant.get_displacement_reason_display(),
            'queue_placement': queue_placement,
        })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error recording displacement classification: {str(e)}'})


@login_required
@verify_position
@require_POST
def field_verify_cdrrmo(request, position):
    """
    Module 2 endpoint for field desk on-site verification findings (ronda and field).
    """
    if request.user.position not in FIELD_DESK_POSITIONS:
        return JsonResponse(
            {'success': False, 'error': 'Permission denied. Only field desk staff can verify.'},
            status=403,
        )

    try:
        applicant_id = request.POST.get('applicant_id')
        verification_decision = request.POST.get('verification_decision')  # certified / not_certified
        verification_notes = request.POST.get('verification_notes', '').strip()

        if not applicant_id or not verification_decision:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id or verification_decision'})
        if verification_decision not in ['certified', 'not_certified']:
            return JsonResponse({'success': False, 'error': 'Invalid decision. Must be "certified" or "not_certified"'})

        applicant = Applicant.objects.get(id=applicant_id)
        handoff_error = _require_intake_archive(applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(applicant)
        if blacklist_error:
            return blacklist_error
        if not hasattr(applicant, 'cdrrmo_certification'):
            return JsonResponse({'success': False, 'error': 'This applicant is not awaiting CDRRMO verification'})

        cert = applicant.cdrrmo_certification
        cert_already_decided = (cert.status != 'pending')

        # Evidence photos stored as FieldVerificationPhoto rows only.
        photos = request.FILES.getlist('evidence_photos')
        if not photos:
            return JsonResponse({
                'success': False,
                'error': (
                    'At least one site photograph is required. '
                    'Capture from the device camera or pick from storage before submitting.'
                ),
            })

        max_photos = 4
        max_bytes = 6 * 1024 * 1024
        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
        valid_uploads = []
        rejected = 0
        for upload in photos[:max_photos]:
            if upload.size > max_bytes:
                rejected += 1
                continue
            ct = (upload.content_type or '').lower()
            name = (upload.name or '').lower()
            if ct not in allowed_types and not name.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                rejected += 1
                continue
            valid_uploads.append(upload)

        if not valid_uploads:
            return JsonResponse({
                'success': False,
                'error': (
                    f'No valid site photographs accepted ({rejected} rejected). '
                    'Allowed types: JPEG, PNG, or WebP. Maximum 6 MB each.'
                ),
            })

        # If cert already decided, append photos only - do NOT change decision/source/notes.
        # If cert pending, flip status + persist decision metadata.
        if not cert_already_decided:
            cert.status = verification_decision
            cert.certified_at = timezone.now()
            cert.result_recorded_by = request.user
            cert.disposition_source = 'field_unit'
            cert.office_intake_notes = ''
            cert.certification_notes = verification_notes if verification_notes else ''
            cert.save()

        photos_saved = 0
        for upload in valid_uploads:
            FieldVerificationPhoto.objects.create(
                certification=cert,
                image=upload,
                uploaded_by=request.user,
            )
            photos_saved += 1

        sms_dispatched = None

        if cert_already_decided:
            existing_label = '✓ Certified' if cert.status == 'certified' else '✗ Not Certified'
            message = f'Certification already on file ({existing_label}). {photos_saved} photo(s) appended to the field record.'
        else:
            message = f'Verification recorded as {"✓ Certified" if verification_decision == "certified" else "✗ Not Certified"}'

        return JsonResponse({
            'success': True,
            'message': message,
            'certification_status': cert.status,
            'recorded_by': f'{request.user.first_name} {request.user.last_name}',
            'recorded_at': timezone.now().isoformat(),
            'photos_saved': photos_saved,
            'sms_dispatched': sms_dispatched,
            'moved_to_module2': True,
            'append_only': cert_already_decided,
        })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error recording verification: {str(e)}'})


@login_required
@verify_position
@require_POST
def update_cdrrmo_status(request, position):
    """
    Module 2 endpoint for staff approval/rejection of field verification findings.
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Jocel or Joie can approve CDRRMO.'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        decision = request.POST.get('decision')  # approved / rejected
        if not applicant_id or not decision:
            return JsonResponse({'success': False, 'error': 'Missing applicant_id or decision'})
        if decision not in ['approved', 'rejected']:
            return JsonResponse({'success': False, 'error': 'Invalid decision. Must be "approved" or "rejected"'})

        applicant = Applicant.objects.get(id=applicant_id)
        handoff_error = _require_intake_archive(applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(applicant)
        if blacklist_error:
            return blacklist_error
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

        ronda_finding = cert.status
        if decision == 'approved':
            applicant.eligibility_checked_by = request.user
            applicant.eligibility_checked_at = timezone.now()
            if ronda_finding == 'certified':
                applicant.status = 'eligible'
                queue_entry, _ = _ensure_module2_queue_entry(applicant, 'priority', added_by=request.user)
                queue_type = 'Priority'
                msg_outcome = 'moved to Priority Queue'
                applicant.disqualification_reason = ''
            else:
                # Not certified finding approved by staff - assign to Walk-in queue.
                applicant.status = 'eligible'
                queue_entry, _ = _ensure_module2_queue_entry(applicant, 'walk_in', added_by=request.user)
                queue_type = 'Walk-in'
                msg_outcome = 'moved to Walk-in Queue (CDRRMO not certified)'
                applicant.disqualification_reason = ''

            applicant.save()
            cert.save()
            if applicant.phone_number:
                eligible_msg = (
                    "✅ Great news! Your housing application passed eligibility. "
                    f"You are assigned {queue_type} Queue Position {queue_entry.position}. "
                    f"Reference: {applicant.reference_number}. Please visit THA office for next steps."
                )
                sent = send_sms(applicant.phone_number, eligible_msg, 'eligibility_passed', applicant=applicant, module='applications')
                if sent and not applicant.eligibility_sms_sent:
                    applicant.eligibility_sms_sent = True
                    applicant.save(update_fields=['eligibility_sms_sent', 'updated_at'])

            return JsonResponse({
                'success': True,
                'message': f'CDRRMO approval confirmed! Applicant {msg_outcome}.',
                'status': 'approved',
                'queue_type': queue_type
            })

        # Staff rejected CDRRMO finding - assign to Walk-in queue instead of disqualifying.
        applicant.status = 'eligible'
        applicant.disqualification_reason = ''
        applicant.eligibility_checked_by = request.user
        applicant.eligibility_checked_at = timezone.now()
        applicant.save()
        queue_entry, _ = _ensure_module2_queue_entry(applicant, 'walk_in', added_by=request.user)
        cert.save()
        if applicant.phone_number:
            walk_in_msg = (
                f"Your housing application has been assigned to Walk-in Queue position #{queue_entry.position}. "
                f"Reference: {applicant.reference_number}. Please visit THA office for next steps."
            )
            sent = send_sms(applicant.phone_number, walk_in_msg, 'eligibility_passed', applicant=applicant, module='applications')

        return JsonResponse({
            'success': True,
            'message': f'CDRRMO verification result noted. Applicant assigned to Walk-in Queue position #{queue_entry.position}.',
            'status': 'rejected',
            'queue_type': 'Walk-in',
            'queue_position': queue_entry.position,
        })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing approval: {str(e)}'})


@login_required
@verify_position
@require_POST
def evaluate_precheck(request, position):
    """
    Process 2 - First checklist precheck.
    Runs blacklist gate before deeper evaluation steps.
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error

    blacklist_error = _require_module2_blacklist_clear(applicant)
    if blacklist_error:
        return blacklist_error

    return JsonResponse({
        'success': True,
        'message': 'Precheck passed: applicant is not blacklisted and may proceed to Eligibility Evaluation Checklist.',
    })


def _situation_certification_gate(applicant):
    # Required uploads/evidence before Module 2 staff finish the situation step.
    # Option D: informational only - no situation-specific vault uploads
    # Option A: (1) vault CDRRMO Certification; (2) site photographs on CDRRMO field record
    # Options B/C: at least one ISF situational supporting document
    dr = (applicant.displacement_reason or '').strip()
    unknown = dr not in ('danger_zone', 'ejected', 'relocated', 'not_abc')
    base = {
        'option_code': dr,
        'requires_documents': False,
        'ready': False,
        'option_d_auto': False,
        'checks': [],
        'blocking_summary': '',
    }
    if unknown:
        base['blocking_summary'] = 'Applicant Situation must be declared before situation certification.'
        return base

    if dr == 'not_abc':
        base['requires_documents'] = False
        base['ready'] = True
        base['option_d_auto'] = True
        base['walk_in_informational'] = True
        base['checks'] = [{
            'key': 'option_d_walk_in',
            'label': 'Option D review',
            'detail': (
                'Applicant Situation is Option D - none of A, B, or C. '
                'No situation-specific supporting uploads apply.'
            ),
            'done': True,
        }]
        return base

    if dr == 'danger_zone':
        base['requires_documents'] = True
        has_cdrrmo_doc = applicant.documents.filter(document_type='cdrrmo_cert').exists()
        field_photo_count = 0
        try:
            field_photo_count = applicant.cdrrmo_certification.field_photos.count()
        except CDRRMOCertification.DoesNotExist:
            field_photo_count = 0
        checks = [
            {
                'key': 'cdrrmo_cert_document',
                'label': 'CDRRMO certification',
                'detail': (
                    'Separate vault slot: upload or scan as document type "CDRRMO Certification".'
                ),
                'done': bool(has_cdrrmo_doc),
                'vault_document_type': 'cdrrmo_cert',
            },
            {
                'key': 'field_site_photos',
                'label': 'Site photographs',
                'detail': (
                    f"{field_photo_count} photo(s) on the applicant's CDRRMO field record. "
                    'Field inspectors attach images when submitting field certification.'
                ),
                'done': field_photo_count >= 1,
            },
        ]
        base['checks'] = checks
        base['ready'] = all(c['done'] for c in checks)
        if not base['ready']:
            missing = [c['label'] for c in checks if not c['done']]
            base['blocking_summary'] = 'Complete before certifying: ' + '; '.join(missing) + '.'
        return base

    if dr == 'ejected':
        base['requires_documents'] = True
        n = applicant.documents.filter(document_type='isf_situational_docs').count()
        done = n >= 1
        base['checks'] = [{
            'key': 'option_b_supporting',
            'label': 'Supporting documentation',
            'detail': (
                f'{n} file(s) on record under ISF situational documentation '
                '(Court Order).'
            ),
            'done': done,
            'files_count': n,
            'vault_document_type': 'isf_situational_docs',
        }]
        base['ready'] = done
        if not done:
            base['blocking_summary'] = (
                'Upload at least one supporting document (Court Order) as ISF situational documentation.'
            )
        return base

    if dr == 'relocated':
        base['requires_documents'] = True
        n = applicant.documents.filter(document_type='isf_situational_docs').count()
        done = n >= 1
        base['checks'] = [{
            'key': 'option_c_supporting',
            'label': 'Supporting documentation',
            'detail': (
                f'{n} file(s) on record under ISF situational documentation '
                '(Demand letter from legal office).'
            ),
            'done': done,
            'files_count': n,
            'vault_document_type': 'isf_situational_docs',
        }]
        base['ready'] = done
        if not done:
            base['blocking_summary'] = (
                'Upload at least one supporting document (Demand letter from legal office) as ISF situational documentation.'
            )
        return base

    return base


# Eligibility evidence copy - vault row counts whether staff used Upload or Scan.
M2_REQUIREMENT_ON_FILE_LABEL = 'On file (scan or upload)'
M2_REQUIREMENT_MISSING_LABEL = 'Missing - scan or upload'


@login_required
@verify_position
@require_POST
def eligibility_snapshot(request, position):
    """
    Process 2 checklist snapshot.
    Eligibility = profile checks + document completeness gates.
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error

    rules = _module2_eligibility_snapshot(applicant, checked_by=request.user)
    auto_disqualified = False
    if rules.get('blacklist_blocked'):
        _, bl_entry = check_blacklist_module2(
            applicant.full_name,
            applicant.phone_number or None,
            applicant_id=applicant.id,
            last_name=applicant.last_name,
            first_name=applicant.first_name,
            date_of_birth=applicant.date_of_birth,
            barangay_id=applicant.barangay_id,
        )
        auto_disqualified = _auto_disqualify_if_blacklisted(applicant, bl_entry, checked_by=request.user)

    # Build requirement scan evidence (same baseline source as Document Scan Checklist).
    required_row_defs = list(
        Requirement.objects.filter(
            group='A',
            is_active=True,
            is_required_for_form=True,
        ).exclude(
            vault_document_type='',
        ).order_by('order', 'code').values('code', 'name', 'vault_document_type', 'is_required_for_form')
    )
    optional_row_defs = list(
        Requirement.objects.filter(
            group='A',
            is_active=True,
            is_required_for_form=False,
        ).exclude(
            vault_document_type='',
        ).exclude(
            code='ISF-SIT',
        ).order_by('order', 'code').values('code', 'name', 'vault_document_type', 'is_required_for_form')
    )
    checklist_row_defs = list(required_row_defs) + list(optional_row_defs)
    req_scan_by_code = {}
    requirement_rows = []
    # Latest vault payload per document_type (upload vs scan label for checklist UI).
    doc_type_to_latest_meta = {}
    for doc in applicant.documents.select_related('blob_record').order_by('-uploaded_at'):
        if doc.document_type in doc_type_to_latest_meta:
            continue
        try:
            doc_url = doc.absolute_download_url(request)
        except (ValueError, AttributeError):
            doc_url = ''
        capture_method = (doc.capture_method or '').strip()
        doc_type_to_latest_meta[doc.document_type] = {
            'url': doc_url,
            'name': (doc.file_name or doc.title or doc.get_document_type_display() or '').strip(),
            'capture_method': capture_method,
            'filed_via_label': document_filed_via_display(capture_method),
        }
    for row in checklist_row_defs:
        files_count = applicant.documents.filter(document_type=row['vault_document_type']).count()
        scanned = files_count > 0
        meta = doc_type_to_latest_meta.get(row['vault_document_type'], {})
        req_scan_by_code[row['code']] = {
            'scanned': scanned,
            'files_count': files_count,
        }
        requirement_rows.append({
            'code': row['code'],
            'name': row['name'],
            'document_type': row['vault_document_type'],
            'is_required_for_form': bool(row.get('is_required_for_form')),
            'scanned': scanned,
            'files_count': files_count,
            'filed_via': meta.get('capture_method', '') if scanned else '',
            'filed_via_label': meta.get('filed_via_label', '') if scanned else '',
        })

    def _req_scanned(code):
        return bool((req_scan_by_code.get(code) or {}).get('scanned'))

    def _latest_doc_for_req(code):
        row = next((item for item in checklist_row_defs if item['code'] == code), None)
        if not row:
            return {'url': '', 'name': ''}
        return doc_type_to_latest_meta.get(row['vault_document_type'], {'url': '', 'name': ''})

    def _req_evidence_doc_label(code):
        if not _req_scanned(code):
            return M2_REQUIREMENT_MISSING_LABEL
        row_def = next((item for item in checklist_row_defs if item['code'] == code), None)
        if not row_def:
            return M2_REQUIREMENT_MISSING_LABEL
        label = doc_type_to_latest_meta.get(row_def['vault_document_type'], {}).get('filed_via_label', '')
        return label or M2_REQUIREMENT_ON_FILE_LABEL

    # Per-check statuses (profile checks + evidence gates)
    age_value = int(applicant.age or 0)
    age_known = age_value > 0
    age_ok = age_value >= 18 if age_known else False
    age_residency_ok = bool(age_ok and rules.get('residency_ok'))

    def _status(ok, pending=False):
        if pending:
            return 'pending'
        return 'passed' if ok else 'failed'

    property_evidence_ready = _req_scanned('R05')
    residency_evidence_ready = _req_scanned('R01')
    income_evidence_ready = _req_scanned('R02')
    household_evidence_ready = _req_scanned('R03')
    voter_value_known = applicant.is_registered_voter_talisay is not None
    voter_doc_latest = _latest_doc_for_req('RVT')

    checks = {
        'property': {
            'title': 'Check Property Ownership',
            'status': _status(bool(rules.get('property_ok')), pending=not property_evidence_ready),
            'reason': (
                'No property in Talisay City.'
                if rules.get('property_ok')
                else 'Property ownership in Talisay City is flagged.'
            ),
            'evidence': [
                f'Profile declaration: {"No property in Talisay City" if not applicant.has_property_in_talisay else "Has property in Talisay City"}',
                f'Certificate of No Property: {_req_evidence_doc_label("R05")}',
            ],
            'view_document': _latest_doc_for_req('R05'),
        },
        'age_residency': {
            'title': 'Check Age and Residency Requirements',
            'status': _status(age_residency_ok, pending=(not age_known or not residency_evidence_ready)),
            'reason': (
                f'Age {age_value}, Residency {rules.get("years_residing", 0)} years.'
                if age_known
                else 'Age is missing in profile.'
            ),
            'evidence': [
                f'Profile age: {age_value if age_known else "Missing"}',
                f'Profile years residing: {rules.get("years_residing", 0)}',
                f'Brgy. Certificate of Residency: {_req_evidence_doc_label("R01")}',
            ],
            'view_document': _latest_doc_for_req('R01'),
        },
        'income': {
            'title': 'Check Income Details',
            'status': _status(bool(rules.get('income_ok')), pending=not income_evidence_ready),
            'reason': (
                f'Declared income ₱{applicant.monthly_income:,.2f}.'
                if applicant.monthly_income is not None
                else 'Monthly income not provided.'
            ),
            'evidence': [
                f'Profile monthly income: {"₱" + format(applicant.monthly_income, ",.2f") if applicant.monthly_income is not None else "Missing"}',
                f'Brgy. Certificate of Indigency: {_req_evidence_doc_label("R02")}',
            ],
            'view_document': _latest_doc_for_req('R02'),
        },
        'household': {
            'title': 'Check Household Composition',
            'status': _status(bool(rules.get('household_ok')), pending=not household_evidence_ready),
            'reason': (
                'Household composition passes policy checks.'
                if rules.get('household_ok')
                else 'Household composition has a policy flag (e.g., live-in partner).'
            ),
            'evidence': [
                f'Profile household size: {applicant.household_size if applicant.household_size is not None else "Missing"}',
                f'Listed household size (computed): {rules.get("listed_household_size", "N/A")}',
                f'Cedula: {_req_evidence_doc_label("R03")}',
            ],
            'view_document': _latest_doc_for_req('R03'),
        },
        'voter': {
            'title': 'Check Registered voters',
            'status': _status(bool(rules.get('voter_ok')), pending=(not voter_value_known)),
            'reason': (
                'Registered voter in Talisay City.'
                if rules.get('voter_ok')
                else 'Not a registered voter in Talisay City.'
            ),
            'evidence': [
                f'Voter certification (optional): {_req_evidence_doc_label("RVT")}',
            ],
            'view_document': voter_doc_latest,
        },
    }

    # Deep links to Document Vault upload modal (prefilled applicant + document type).
    _eligibility_check_vault_types = {
        'property': 'no_property',
        'age_residency': 'barangay_residency',
        'income': 'barangay_indigency',
        'household': 'cedula',
        'voter': 'voter_certification',
    }
    _vault_mgmt_elig = reverse('documents:management', kwargs={'position': request.user.position})
    _vault_search_elig = ((applicant.reference_number or '').strip() or str(applicant.pk)).strip()
    for _ck, _dt in _eligibility_check_vault_types.items():
        if _ck in checks:
            _base_elig_q = {
                'search': _vault_search_elig,
                'applicant_id': str(applicant.pk),
                'open_upload': '1',
                'document_type': _dt,
            }
            checks[_ck]['vault_upload_url'] = (
                f'{_vault_mgmt_elig}?{urlencode({**_base_elig_q, "intent": "upload"})}'
            )
            checks[_ck]['vault_scan_url'] = (
                f'{_vault_mgmt_elig}?{urlencode({**_base_elig_q, "intent": "scan"})}'
            )

    saved_decisions = {}
    for decision in EligibilityCheckDecision.objects.filter(applicant=applicant):
        saved_decisions[decision.check_key] = {
            'status': decision.status,
            'failure_reason': decision.failure_reason or '',
            'reviewed_by': decision.reviewed_by.get_full_name() if decision.reviewed_by else '',
            'reviewed_at': decision.reviewed_at.isoformat() if decision.reviewed_at else '',
        }

    gates = {
        'required_docs': {
            'title': 'Required baseline scans (Group A, R01–R07)',
            'status': 'passed' if rules.get('required_docs_complete') else 'pending',
            'reason': f'{rules.get("required_docs_scanned", 0)}/{rules.get("required_docs_total", 0)} scanned.',
        },
        'situation_docs': {
            'title': 'Applicant Situation supporting documents',
            'status': (
                'not_required'
                if not rules.get('situation_docs_required')
                else ('passed' if rules.get('situation_docs_ready') else 'pending')
            ),
            'reason': (
                'Not required for Option D.'
                if not rules.get('situation_docs_required')
                else f'{rules.get("situation_docs_count", 0)} file(s) uploaded.'
            ),
        },
    }

    displacement_reason = (applicant.displacement_reason or '').strip()
    situation_map = {
        'danger_zone': {
            'option': 'Option A',
            'title': 'Resident of Danger Zone or Hazard Area',
            'description': 'Applicant resides in a flood-prone, landslide, storm-surge, riverbank, cliff-edge, or coastal hazard area requiring relocation for safety.',
        },
        'ejected': {
            'option': 'Option B',
            'title': 'Ejected or Evicted from Prior Residence',
            'description': 'Applicant has been evicted or displaced through private land eviction, court order, landowner recovery, or analogous proceedings.',
        },
        'relocated': {
            'option': 'Option C',
            'title': 'Displaced by Government Project or Infrastructure',
            'description': 'Applicant is required to relocate due to a road-widening, drainage, infrastructure, or other government-initiated project.',
        },
        'not_abc': {
            'option': 'Option D',
            'title': 'None of A, B, or C (Other / not listed)',
            'description': (
                'The situation does not fall under a hazard area, private eviction/ejection, '
                'or a government infrastructure project.'
            ),
        },
    }
    situation_payload = situation_map.get(displacement_reason, {
        'option': 'Not set',
        'title': 'Applicant Situation is not yet declared',
        'description': 'No applicant situation has been recorded for this applicant.',
    })

    situation_cert_gate = _situation_certification_gate(applicant)
    vault_mgmt_path = reverse('documents:management', kwargs={'position': request.user.position})
    vault_search_term = ((applicant.reference_number or '').strip() or str(applicant.pk)).strip()
    for _cert_row in situation_cert_gate.get('checks') or []:
        dt = (_cert_row.get('vault_document_type') or '').strip()
        if dt:
            _base_cert_q = {
                'search': vault_search_term,
                'applicant_id': str(applicant.pk),
                'open_upload': '1',
                'document_type': dt,
            }
            _cert_row['vault_upload_url'] = (
                f'{vault_mgmt_path}?{urlencode({**_base_cert_q, "intent": "upload"})}'
            )
            _cert_row['vault_scan_url'] = (
                f'{vault_mgmt_path}?{urlencode({**_base_cert_q, "intent": "scan"})}'
            )
            doc = applicant.documents.filter(document_type=dt).order_by('-uploaded_at').first()
            if doc:
                try:
                    doc_url = doc.absolute_download_url(request)
                except (ValueError, AttributeError):
                    doc_url = ''
                if doc_url:
                    _cert_row['view_document'] = {
                        'url': doc_url,
                        'name': (doc.file_name or doc.title or doc.get_document_type_display() or '').strip(),
                    }
        sit_key = (_cert_row.get('key') or '').strip()
        if sit_key == 'field_site_photos':
            _cert_row['field_portal_url'] = reverse('accounts:dashboard_field')
            photo_urls = []
            try:
                cert = applicant.cdrrmo_certification
                for ph in cert.field_photos.exclude(image='').filter(
                    image__isnull=False
                ).order_by('uploaded_at', 'id'):
                    try:
                        photo_urls.append(ph.image.url)
                    except (ValueError, AttributeError):
                        pass
            except CDRRMOCertification.DoesNotExist:
                pass
            _cert_row['field_photo_urls'] = photo_urls

    return JsonResponse({
        'success': True,
        'applicant_id': str(applicant.id),
        'reference_number': ((applicant.reference_number or '').strip() or str(applicant.pk)),
        'auto_disqualified': bool(auto_disqualified),
        'checks': checks,
        'saved_decisions': saved_decisions,
        'gates': gates,
        'situation': {
            'code': displacement_reason,
            **situation_payload,
        },
        'situation_certification': situation_cert_gate,
        'document_scan_checklist': {
            'required_scanned': int(rules.get('required_docs_scanned', 0)),
            'required_total': int(rules.get('required_docs_total', 0)),
            'rows': requirement_rows,
        },
        'overall': {
            'blacklist_blocked': bool(rules.get('blacklist_blocked')),
            'form_generation_ready': bool(rules.get('form_generation_ready')),
            'required_docs_complete': bool(rules.get('required_docs_complete')),
            'certification_status': rules.get('certification_status'),
            'field_evidence_status': rules.get('field_evidence_status'),
            'situation_docs_ready': bool(rules.get('situation_docs_ready')),
            'readiness_hint': rules.get('readiness_hint') or '',
            'has_failed_checks': bool(rules.get('has_failed_checks')),
            **_module2_application_overall_snapshot(getattr(applicant, 'application', None)),
        },
        'blockers': list(rules.get('blockers') or []),
        'advisories': list(rules.get('advisories') or []),
    })


@login_required
@verify_position
@require_POST
def save_eligibility_check_decision(request, position):
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    check_key = (request.POST.get('check_key') or '').strip()
    status = (request.POST.get('status') or '').strip().lower()
    failure_reason = (request.POST.get('failure_reason') or '').strip()
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)
    if check_key not in ELIGIBILITY_CHECK_KEYS:
        return JsonResponse({'success': False, 'error': 'Invalid checklist key.'}, status=400)
    if status not in ('passed', 'failed'):
        return JsonResponse({'success': False, 'error': 'Invalid decision status.'}, status=400)
    if status == 'failed' and len(failure_reason) < 5:
        return JsonResponse({'success': False, 'error': 'Please provide a clear failure reason.'}, status=400)
    if status == 'passed':
        failure_reason = ''

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error

    decision, _created = EligibilityCheckDecision.objects.update_or_create(
        applicant=applicant,
        check_key=check_key,
        defaults={
            'status': status,
            'failure_reason': failure_reason,
            'reviewed_by': request.user,
        },
    )

    sms_sent = False
    sms_detail = ''
    notify_flag = str(request.POST.get('notify_applicant_sms') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    if status == 'failed' and notify_flag:
        phone = (applicant.phone_number or '').strip()
        if not phone:
            sms_detail = 'No mobile number on file; SMS not sent.'
        else:
            ref = ((applicant.reference_number or '').strip() or str(applicant.pk))
            applicant_name = (applicant.full_name or '').strip() or 'Applicant'
            check_label = ELIGIBILITY_CHECK_LABELS.get(check_key, check_key.replace('_', ' '))
            body = (
                f'Applicant: {applicant_name} [{ref}] Eligibility ({check_label}): {failure_reason}'.strip()
            )
            if len(body) > 480:
                body = body[:477].rstrip() + '...'
            sms_sent = bool(send_sms(phone, body, 'eligibility_check_failed', applicant=applicant))
            sms_detail = (
                'SMS sent to applicant.'
                if sms_sent
                else 'SMS could not be sent (invalid number format or gateway error).'
            )

    # Keep Applicant.status in sync once the applicant has already been through
    # situation certification. Pre-certification applicants stay 'pending' until
    # the reviewer hits Mark Situation Certified.
    status_synced_to = None
    if applicant.status in ('eligible', 'pending_followup'):
        has_failed_checks_now = applicant.eligibility_check_decisions.filter(status='failed').exists()
        new_status = 'pending_followup' if has_failed_checks_now else 'eligible'
        if new_status != applicant.status:
            applicant.status = new_status
            applicant.save(update_fields=['status', 'updated_at'])
            status_synced_to = new_status

    response_payload = {
        'success': True,
        'decision': {
            'check_key': decision.check_key,
            'status': decision.status,
            'failure_reason': decision.failure_reason or '',
            'reviewed_by': decision.reviewed_by.get_full_name() if decision.reviewed_by else '',
            'reviewed_at': decision.reviewed_at.isoformat() if decision.reviewed_at else '',
        },
        'applicant_status_synced_to': status_synced_to,
    }
    if status == 'failed':
        response_payload['sms_sent'] = sms_sent
        response_payload['sms_detail'] = sms_detail
        response_payload['sms_requested'] = notify_flag
    return JsonResponse(response_payload)


@login_required
@verify_position
@require_POST
def notify_ronda_for_situation(request, position):
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error

    displacement_reason = (applicant.displacement_reason or '').strip()
    if displacement_reason != 'danger_zone':
        return JsonResponse({'success': False, 'error': 'Notify Ronda is only available for Option A (danger zone).'}, status=400)

    cert = getattr(applicant, 'cdrrmo_certification', None)
    if cert is None:
        cert = CDRRMOCertification.objects.create(
            applicant=applicant,
            requested_by=request.user,
            status='pending',
            declared_location=(applicant.danger_zone_location or applicant.danger_zone_type or '').strip() or 'Declared hazard area',
            disposition_source='pending',
        )
    elif cert.status != 'pending':
        cert.status = 'pending'
        cert.disposition_source = 'pending'
        cert.result_recorded_by = None
        cert.certified_at = None
        cert.certification_notes = ''
        cert.office_intake_notes = ''
        cert.save(update_fields=['status', 'disposition_source', 'result_recorded_by', 'certified_at', 'certification_notes', 'office_intake_notes'])

    applicant.status = 'pending_cdrrmo'
    applicant.save(update_fields=['status', 'updated_at'])
    return JsonResponse({
        'success': True,
        'message': 'Ronda has been notified. Applicant is now pending CDRRMO field verification.',
    })


@login_required
@verify_position
@require_POST
def mark_situation_certified(request, position):
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    notes = (request.POST.get('notes') or '').strip()
    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error

    displacement_reason = (applicant.displacement_reason or '').strip()
    if displacement_reason not in ('danger_zone', 'ejected', 'relocated', 'not_abc'):
        return JsonResponse({'success': False, 'error': 'Applicant Situation is not set yet.'}, status=400)

    situation_gate = _situation_certification_gate(applicant)
    if situation_gate.get('requires_documents') and not situation_gate.get('ready'):
        return JsonResponse({
            'success': False,
            'error': situation_gate.get('blocking_summary') or 'Situation certification requirements are not complete.',
        }, status=400)

    queue_placement = _layer3_queue_placement_bundle(applicant, request.user)

    # If any reviewer check is marked failed, the applicant moves to Pending
    # Follow-up instead of Eligible. They keep their queue placement so they can
    # resume once the failed check(s) are resolved by re-marking Passed.
    has_failed_checks = applicant.eligibility_check_decisions.filter(status='failed').exists()
    applicant.status = 'pending_followup' if has_failed_checks else 'eligible'
    applicant.eligibility_checked_by = request.user
    applicant.eligibility_checked_at = timezone.now()
    if notes:
        applicant.evaluation_approval_notes = notes
    applicant.save(update_fields=['status', 'eligibility_checked_by', 'eligibility_checked_at', 'evaluation_approval_notes', 'updated_at'])

    if has_failed_checks:
        if displacement_reason == 'not_abc':
            message = 'Applicant Situation step noted. Marked Pending Follow-up due to failed eligibility check(s).'
        else:
            message = 'Applicant Situation certified. Marked Pending Follow-up due to failed eligibility check(s).'
    elif displacement_reason == 'not_abc':
        message = 'Applicant Situation step completed and eligibility recorded.'
    else:
        message = 'Applicant Situation certified and queue placement updated.'

    return JsonResponse({
        'success': True,
        'message': message,
        'pending_followup': has_failed_checks,
        'queue_placement': queue_placement,
    })


@login_required
@verify_position
@require_POST
def evaluate_applicant(request, position):
    """
    Module 2 eligibility evaluation and queue assignment endpoint.
    Evaluates applicant and assigns to Priority or Walk-in queue.
    Disqualification is handled in Module 3 (Documents).
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    action = request.POST.get('action')
    reason = request.POST.get('reason', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not applicant_id or action not in ['mark_eligible', 'mark_eligible_priority', 'mark_eligible_walk_in']:
        return JsonResponse({'success': False, 'error': 'Missing or invalid parameters.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error

    if applicant.status not in ['pending', 'pending_cdrrmo', 'eligible']:
        return JsonResponse({
            'success': False,
            'error': f'Cannot evaluate record with current status: {applicant.get_status_display()}',
        }, status=400)

    blacklist_error = _require_module2_blacklist_clear(applicant)
    if blacklist_error:
        return blacklist_error

    if action in ['mark_eligible', 'mark_eligible_priority', 'mark_eligible_walk_in']:
        rules = _module2_eligibility_snapshot(applicant)
        # Eligibility checks are advisory-only (red indicator); they do not block marking eligible.

        forced_queue_type = None
        if action == 'mark_eligible_priority':
            forced_queue_type = 'priority'
        elif action == 'mark_eligible_walk_in':
            forced_queue_type = 'walk_in'

        queue_type = forced_queue_type or rules['recommended_queue_type']
        if queue_type not in rules['allowed_queue_types']:
            allowed_txt = ', '.join(q.replace('_', '-').title() for q in rules['allowed_queue_types'])
            return JsonResponse({
                'success': False,
                'error': f'Selected queue type is not allowed for this applicant. Allowed: {allowed_txt}.',
            }, status=400)

        current_active = applicant.queue_entries.filter(status='active').order_by('entered_at').first()
        same_assignment = (
            applicant.status == 'eligible'
            and current_active is not None
            and current_active.queue_type == queue_type
        )
        if same_assignment:
            return JsonResponse({
                'success': True,
                'message': f'Applicant is already eligible and assigned to {current_active.get_queue_type_display()} position #{current_active.position}.',
                'new_status': applicant.status,
            })

        applicant.status = 'eligible'
        applicant.disqualification_reason = ''
        applicant.eligibility_checked_by = request.user
        applicant.eligibility_checked_at = timezone.now()
        applicant.save()

        queue_entry, _ = _ensure_module2_queue_entry(applicant, queue_type, added_by=request.user)
        queue_label = 'Priority Queue' if queue_type == 'priority' else 'Walk-in Queue'
        if applicant.phone_number:
            msg = (
                "Congratulations! You are eligible for housing assistance. "
                f"You are now in {queue_label} position #{queue_entry.position}. "
                f"Reference: {applicant.reference_number}."
            )
            sent = send_sms(applicant.phone_number, msg, 'eligibility_passed', applicant=applicant, module='applications')
            if sent and not applicant.eligibility_sms_sent:
                applicant.eligibility_sms_sent = True
                applicant.save(update_fields=['eligibility_sms_sent', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': f'Applicant marked eligible and queued in {queue_label} at position #{queue_entry.position}.',
            'new_status': applicant.status,
            'queue_type': queue_type,
            'queue_position': queue_entry.position,
        })

    # Disqualification is handled in Module 3 (Documents), not here.
    return JsonResponse({
        'success': False,
        'error': 'Module 2 handles eligibility determination and queue assignment only. Disqualification is processed in Module 3.',
    }, status=400)


@login_required
@verify_position
@require_POST
def record_evaluation_approval(request, position):
    """
    Module 2 step 2.8 endpoint.
    Auto-confirms eligibility approval / step 2.8 (only 'approved' status) based on Layer 3 CDRRMO completion.
    Stores eligibility approval marker only (separate from Module 3 routing).
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant_id = request.POST.get('applicant_id')
    approval_status = request.POST.get('approval_status', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not applicant_id:
        return JsonResponse({'success': False, 'error': 'Missing applicant_id.'}, status=400)

    if approval_status != 'approved':
        return JsonResponse({'success': False, 'error': 'Module 2 step 2.8 only supports approval. Disqualification is handled in Module 3.'}, status=400)

    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error
    blacklist_error = _require_module2_blacklist_clear(applicant)
    if blacklist_error:
        return blacklist_error

    # Validate base Module 2 state for 2.8 action.
    if applicant.status != 'eligible':
        return JsonResponse({
            'success': False,
            'error': 'Record 2.8 approval only after Module 2 marks the applicant eligible and queued.',
        }, status=400)
    active_queue = applicant.queue_entries.filter(status='active').order_by('entered_at').first()
    if active_queue is None:
        return JsonResponse({
            'success': False,
            'error': 'Record 2.8 approval only after queue assignment (Priority or Walk-in) is active.',
        }, status=400)

    # NOTE: Layer 3 CDRRMO completion gate temporarily disabled - 2.8 approval can
    # be recorded while CDRRMO certification is still Pending. Re-enable later if
    # the policy needs to require Certified/Denied before final 2.8 approval.

    applicant.evaluation_approval_status = approval_status
    applicant.evaluation_approval_notes = notes
    applicant.evaluation_approval_by = request.user
    applicant.evaluation_approval_at = timezone.now()
    update_fields = [
        'evaluation_approval_status',
        'evaluation_approval_notes',
        'evaluation_approval_by',
        'evaluation_approval_at',
        'updated_at',
    ]

    applicant.save(update_fields=update_fields)

    # No applicant SMS from this 2.8 save path (see other views for eligibility / proceed SMS).
    sms_dispatched = False

    return JsonResponse({
        'success': True,
        'message': f'2.8 saved as {applicant.get_evaluation_approval_status_display()}.',
        'approval_status': applicant.evaluation_approval_status,
        'approval_status_display': applicant.get_evaluation_approval_status_display(),
        'approval_by': applicant.evaluation_approval_by.get_full_name() if applicant.evaluation_approval_by else '',
        'approval_at': applicant.evaluation_approval_at.isoformat() if applicant.evaluation_approval_at else None,
        'sms_dispatched': sms_dispatched,
    })


# =============================================================================
# FORM GENERATION (Jocel, Joie)
# =============================================================================

@login_required
@verify_position
def generate_form(request, position, applicant_id):
    """
    Generate application form for applicant.

    URL: /applications/<position>/form/generate/<applicant_id>/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary
    ✅ Joie (2nd Member) - Supervisor backup
    """
    # Check permission
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Jocel or Joie can generate forms.'
        }, status=403)
    
    applicant = get_object_or_404(
        Applicant.objects.select_related('barangay').prefetch_related('household_members'),
        id=applicant_id,
    )
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error
    blacklist_error = _require_module2_blacklist_clear(applicant)
    if blacklist_error:
        return blacklist_error

    rules = _module2_eligibility_snapshot(applicant, checked_by=request.user)
    # Eligibility checks are advisory-only (red indicator); they do not block form generation.

    # Module 1 should have placed every eligible applicant into FIFO queue.
    # Self-heal older records so Module 2 can proceed without manual queue fixes.
    if applicant.status in ['eligible', 'requirements', 'application']:
        queue_entry, queue_created = _ensure_module2_queue_entry(
            applicant,
            rules['recommended_queue_type'],
            added_by=request.user,
        )
        if queue_created and applicant.phone_number:
            queue_label = 'Priority Queue' if queue_entry.queue_type == 'priority' else 'Walk-in Queue'
            msg = (
                "Great news! Your housing application is now queued for processing. "
                f"{queue_label} Position #{queue_entry.position}. "
                f"Reference: {applicant.reference_number}"
            )
            send_sms(applicant.phone_number, msg, 'eligibility_passed', applicant=applicant, module='applications')

    if not rules.get('form_generation_ready'):
        hint = (rules.get('readiness_hint') or '').strip()
        return JsonResponse({
            'success': False,
            'error': hint
            or (
                'Applicant is not ready for form generation yet. '
                'Complete Module 2 evaluation (required documents vault, eligibility checks, and certification) first.'
            ),
        })

    # Check if application already exists
    if hasattr(applicant, 'application'):
        return JsonResponse({
            'success': False,
            'error': 'Application form already generated.'
        })

    try:
        with transaction.atomic():
            application = Application.objects.create(
                applicant=applicant,
                form_generated_by=request.user,
                status='draft'
            )
            applicant.status = 'application'
            applicant.save(update_fields=['status'])
            build_filled_application_pdf(applicant, application)
    except FileNotFoundError as exc:
        logger.error('generate_form missing PDF template: %s', exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)
    except Exception as exc:
        logger.exception('generate_form PDF build failed')
        return JsonResponse(
            {'success': False, 'error': f'Could not produce application PDF: {exc}'},
            status=500,
        )

    pdf_url = reverse(
        'applications:application_form_pdf',
        kwargs={'position': request.user.position, 'applicant_id': applicant.id},
    )
    return JsonResponse({
        'success': True,
        'application_number': application.application_number,
        'pdf_url': pdf_url,
        'message': f'Application form {application.application_number} generated successfully.',
    })


@login_required
@verify_position
def application_form_pdf(request, position, applicant_id):
    """
    Stream filled APPLICATION-FORM-THA.pdf for viewing or printing.

    Requires an existing Application row (after Generate Form).
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    applicant = get_object_or_404(
        Applicant.objects.select_related('barangay').prefetch_related('household_members'),
        id=applicant_id,
    )
    application = getattr(applicant, 'application', None)
    if application is None:
        return JsonResponse(
            {'success': False, 'error': 'Application form has not been generated for this applicant.'},
            status=404,
        )

    try:
        pdf_bytes = build_filled_application_pdf(applicant, application)
    except FileNotFoundError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)
    except Exception as exc:
        logger.exception('application_form_pdf')
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    filename = f'THA-Application-{application.application_number}.pdf'
    response = FileResponse(io.BytesIO(pdf_bytes), as_attachment=False, filename=filename)
    response['Content-Type'] = 'application/pdf'
    return response


@login_required
@verify_position
@require_POST
def proceed_to_lot_awarding_queue(request, position):
    """
    From Ready for Form queue, move a completed (applicant-signed) form directly
    to the lot-awarding track (standby queue).
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Jocel or Joie can route to lot awarding.'
        }, status=403)

    application_id = request.POST.get('application_id')
    if not application_id:
        return JsonResponse({'success': False, 'error': 'Missing application_id.'}, status=400)

    try:
        application = Application.objects.select_related('applicant').get(id=application_id)
        handoff_error = _require_intake_archive(application.applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(application.applicant)
        if blacklist_error:
            return blacklist_error

        from applications.form_pipeline import (
            applicant_has_signed_application_payload,
            apply_signed_application_scan_if_ready,
        )

        apply_signed_application_scan_if_ready(str(application.applicant_id))
        application.refresh_from_db()

        if not applicant_has_signed_application_payload(application.applicant):
            return JsonResponse({
                'success': False,
                'error': (
                    'Upload or scan a signed application first. Proceed to Awarding stays disabled '
                    'until the signed form is on file.'
                ),
            }, status=400)

        if application.status != 'completed':
            return JsonResponse({
                'success': False,
                'error': (
                    'Application must show as Completed (signed scan on file) before proceeding '
                    'to lot awarding.'
                ),
            }, status=400)

        application.status = 'standby'
        application.standby_entered_at = timezone.now()

        last_position = Application.objects.filter(
            status='standby'
        ).exclude(id=application.id).aggregate(
            max_pos=Max('standby_position')
        )['max_pos'] or 0
        application.standby_position = last_position + 1
        application.save(update_fields=['status', 'standby_entered_at', 'standby_position', 'updated_at'])

        return JsonResponse({
            'success': True,
            'standby_position': application.standby_position,
            'message': (
                f'Application routed to lot-awarding queue '
                f'(Standby position #{application.standby_position}).'
            ),
        })
    except Application.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Application not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# LOT AWARDING (Jocel)
# =============================================================================


def vacant_units_grouped_for_award_select():
    """
    Vacant housing units for the Award Lot picker (Module 4 inventory).
    Matches Module 4: status Vacant — available and no active LotAward on the unit.
    """
    active_lot = LotAward.objects.filter(unit_id=OuterRef('pk'), status='active')
    units = (
        HousingUnit.objects.filter(
            HousingUnit.vacant_available_status_filter(),
            site__is_active=True,
        )
        .annotate(_has_active=Exists(active_lot))
        .filter(_has_active=False)
        .select_related('site')
    )
    units_list = sorted(
        units,
        key=lambda u: (
            (u.site.name or '').lower(),
            *block_lot_sort_key(u.block_number, u.lot_number),
        ),
    )
    groups = []
    index_by_site = {}
    for u in units_list:
        sid = u.site_id
        if sid not in index_by_site:
            index_by_site[sid] = len(groups)
            groups.append({'site': u.site, 'units': []})
        groups[index_by_site[sid]]['units'].append(u)
    return groups


def _resolve_relocation_site_for_award(site_name_raw):
    """
    Map free-text site from the Award Lot modal to a RelocationSite row (Module 4).
    """
    name = (site_name_raw or '').strip()
    qs = RelocationSite.objects.filter(is_active=True).order_by('name')
    if not qs.exists():
        return None
    if not name:
        return qs.first()
    site = qs.filter(name__iexact=name).first()
    if site:
        return site
    site = qs.filter(name__icontains=name).first()
    if site:
        return site
    site = qs.filter(code__iexact=name).first()
    if site:
        return site
    compact = name.replace(' ', '').lower()
    if compact:
        for candidate in qs:
            if compact in candidate.name.replace(' ', '').lower():
                return candidate
    if qs.count() == 1:
        return qs.first()
    return None


def _assign_housing_unit_after_lot_award(application, unit, awarded_by_user):
    """
    Create units.LotAward and mark HousingUnit occupied. ``unit`` must be vacant.
    """
    if not HousingUnit.is_vacant_available_status(unit.status):
        raise ValueError(
            f'This housing unit is not available for awarding (current status: {unit.status!r}). '
            'Choose a unit listed as Vacant — available in Housing Unit & Occupancy Monitoring.'
        )

    block = unit.block_number
    lot = unit.lot_number
    site_name = unit.site.name

    other_active = (
        LotAward.objects.filter(unit=unit, status='active')
        .exclude(application_id=application.id)
        .select_related('application__applicant')
        .first()
    )
    if other_active:
        occ = (
            other_active.application.applicant.full_name
            if getattr(other_active.application, 'applicant', None)
            else 'another applicant'
        )
        raise ValueError(
            f'Block {block} Lot {lot} at {site_name} is already assigned ({occ}). '
            f'Pick a vacant unit or resolve the existing assignment in Module 4.'
        )

    award = LotAward.objects.create(
        application=application,
        unit=unit,
        status='active',
        awarded_at=timezone.now(),
        awarded_by=awarded_by_user,
        via_draw_lots=False,
    )

    # Start construction monitoring snapshot (Module 4) for this awarded unit.
    ConstructionProgress.objects.get_or_create(
        lot_award=award,
        defaults={
            'stage': 'not_started',
            'percent_complete': 0,
            'updated_by': awarded_by_user,
        },
    )

    # Module 4: Create occupancy monitoring workflow
    try:
        from datetime import timedelta
        from units.models import OccupancyMonitoringCycle, MonitoringTask

        award_date = award.awarded_at.date()
        monitoring_start_date = award_date + timedelta(days=30)

        # Create monitoring cycle for 30-day period
        monitoring_cycle = OccupancyMonitoringCycle.objects.create(
            lot_award=award,
            cycle_stage='original_30_day',
            stage_start_date=award_date,
            stage_end_date=award_date + timedelta(days=30),
            days_allowed=30,
            is_active=True,
        )

        # Determine caretaker for task assignment
        assigned_caretaker = unit.site.caretaker if unit.site else None

        # Office policy: 30-day possession grace, then monitoring. First field visit is at
        # monitoring day 90; the final (120 Day) visit is 120 calendar days after that due date.
        from units.monitoring_policy import (
            TASK_TYPE_FINAL_INSPECTION,
            TASK_TYPE_INITIAL_INSPECTION,
            final_inspection_days_from_award,
            final_inspection_due,
            initial_inspection_days_from_award,
            initial_inspection_due,
        )

        initial_due = initial_inspection_due(award_date)
        final_due = final_inspection_due(award_date)
        MonitoringTask.objects.create(
            unit=unit,
            lot_award=award,
            task_type=TASK_TYPE_INITIAL_INSPECTION,
            scheduled_date=initial_due,
            due_date=initial_due,
            days_from_award=initial_inspection_days_from_award(),
            status='pending',
            assigned_to=assigned_caretaker,
        )

        MonitoringTask.objects.create(
            unit=unit,
            lot_award=award,
            task_type=TASK_TYPE_FINAL_INSPECTION,
            scheduled_date=final_due,
            due_date=final_due,
            days_from_award=final_inspection_days_from_award(),
            status='pending',
            assigned_to=assigned_caretaker,
        )
    except Exception as e:
        # Log the error but don't fail the entire award process
        import sys
        sys.stderr.write(
            f"\n[WARNING] Module 4 monitoring setup failed for {unit}: {str(e)}\n"
        )
        sys.stderr.flush()

    applicant = application.applicant
    unit.status = 'Occupied'
    unit.occupant_name = applicant.full_name if applicant else ''
    ref = (applicant.reference_number or '') if applicant else ''
    unit.occupant_id = ref[:100] if ref else None
    unit.save(update_fields=['status', 'occupant_name', 'occupant_id', 'updated_at'])


def _sync_housing_unit_after_lot_award(application, site_name_raw, block_number, lot_number, awarded_by_user):
    """
    Legacy path: resolve site + block/lot, get_or_create HousingUnit, then assign.
    Prefer selecting an existing vacant unit (housing_unit_id) from Module 4.
    """
    site = _resolve_relocation_site_for_award(site_name_raw)
    if not site:
        raise ValueError(
            'Unknown relocation site. Enter the site name as configured in Module 4 (Housing Units), '
            'for example "GK Cabatangan Relocation Site", or ask an administrator to create the site.'
        )

    block = (block_number or '').strip()
    lot = (lot_number or '').strip()
    if not lot:
        raise ValueError('Lot number is required to sync the housing unit map.')

    unit, _created = HousingUnit.objects.get_or_create(
        site=site,
        block_number=block,
        lot_number=lot,
        defaults={'status': HousingUnit.STATUS_VACANT_AVAILABLE},
    )
    _assign_housing_unit_after_lot_award(application, unit, awarded_by_user)


def _parse_orientation_at(raw):
    """Parse datetime-local / ISO value from the lot-awarding SMS modal."""
    from datetime import datetime
    from django.utils.dateparse import parse_datetime

    raw = (raw or '').strip()
    if not raw:
        return None
    if 'T' in raw and len(raw) >= 16:
        try:
            naive = datetime.fromisoformat(raw[:16])
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            pass
    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@login_required
@verify_position
@require_POST
def lot_awarding_bulk_notify_sms(request, position):
    """
    Send a coordination SMS to selected applicants still on the lot-awarding queue.
    Orientation date/time is required and woven into the message body.
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({'success': False, 'error': 'Access denied.'}, status=403)

    raw_ids = request.POST.getlist('application_ids')
    if not raw_ids:
        single = (request.POST.get('application_ids') or '').strip()
        if single:
            raw_ids = [x.strip() for x in single.split(',') if x.strip()]

    if not raw_ids:
        return JsonResponse({'success': False, 'error': 'No applicants selected.'}, status=400)

    orientation_at = _parse_orientation_at(request.POST.get('orientation_at'))
    if not orientation_at:
        return JsonResponse(
            {'success': False, 'error': 'Orientation date and time are required.'},
            status=400,
        )

    # Staff may edit the textarea; default body includes the orientation schedule.
    message_body = (request.POST.get('message') or '').strip()
    if not message_body:
        message_body = sms_workflow.lot_awarding_notify_body(orientation_at=orientation_at)
    message_body = message_body[:900]

    sent = 0
    skipped_no_phone = 0
    failed = 0
    errors = []

    import sys
    sys.stderr.write(f"\n[lot_awarding_bulk_notify_sms] Sending to {len(raw_ids[:100])} applicant(s)...\n")
    sys.stderr.flush()

    for aid in raw_ids[:100]:
        try:
            app = Application.objects.select_related('applicant').get(id=aid)
        except (Application.DoesNotExist, ValueError):
            failed += 1
            errors.append(f'{aid}: not found')
            continue
        if app.status != 'standby':
            failed += 1
            errors.append(f'{aid}: not in lot awarding queue')
            continue
        applicant = app.applicant
        phone = (applicant.phone_number or '').strip() if applicant else ''
        if not phone:
            skipped_no_phone += 1
            sys.stderr.write(f"  WARNING: {applicant.full_name}: no phone -- skipped\n")
            continue
        msg = f'{message_body} - {applicant.full_name}.'
        ok = send_sms(
            phone,
            msg,
            sms_workflow.PROCEED_TO_LOT_AWARDING,
            applicant=applicant,
            module='applications',
        )
        if ok:
            sent += 1
        else:
            failed += 1

    sys.stderr.write(
        f"\n[lot_awarding_bulk_notify_sms] Done -- sent={sent}, "
        f"skipped_no_phone={skipped_no_phone}, failed={failed}\n\n"
    )
    sys.stderr.flush()

    return JsonResponse({
        'success': True,
        'sent': sent,
        'skipped_no_phone': skipped_no_phone,
        'failed': failed,
        'errors': errors[:12],
    })


@login_required
@verify_position
@require_POST
def award_lot(request, position):
    """
    Record lot awarding for an applicant.

    URL: /applications/<position>/lot/award/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary lot awarding
    ✅ Joie (2nd Member) - Supervisor backup
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Jocel or Joie can record lot awarding.'
        }, status=403)
    
    application_id = request.POST.get('application_id')
    housing_unit_id = (request.POST.get('housing_unit_id') or '').strip()
    notes = (request.POST.get('notes') or '').strip()[:2000]

    unit_for_assign = None
    lot_number = ''
    block_number = ''
    site_name = ''

    if housing_unit_id:
        try:
            unit_for_assign = HousingUnit.objects.select_related('site').get(id=housing_unit_id)
        except (HousingUnit.DoesNotExist, ValueError):
            return JsonResponse({'success': False, 'error': 'Invalid or unknown housing unit.'}, status=400)
        if not HousingUnit.is_vacant_available_status(unit_for_assign.status):
            return JsonResponse({
                'success': False,
                'error': (
                    f'This unit cannot be awarded — status must be Vacant — available '
                    f'(current: {unit_for_assign.status}). Refresh and pick a vacant lot in Module 4.'
                ),
            }, status=400)
        if LotAward.objects.filter(unit=unit_for_assign, status='active').exists():
            return JsonResponse({
                'success': False,
                'error': 'This unit already has an active assignment. Refresh and pick another vacant unit.',
            }, status=400)
        lot_number = unit_for_assign.lot_number
        block_number = unit_for_assign.block_number or ''
        site_name = unit_for_assign.site.name
    else:
        lot_number = (request.POST.get('lot_number') or '').strip()
        block_number = (request.POST.get('block_number') or '').strip()
        site_name = (request.POST.get('site_name') or '').strip()
        if not lot_number:
            return JsonResponse({
                'success': False,
                'error': 'Select a vacant unit from the list (Module 4 inventory).',
            })

    try:
        application = Application.objects.select_related('applicant').get(id=application_id)
        handoff_error = _require_intake_archive(application.applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(application.applicant)
        if blacklist_error:
            return blacklist_error

        if application.status != 'standby':
            return JsonResponse({
                'success': False,
                'error': 'Application must be fully approved before lot can be awarded.'
            })

        with transaction.atomic():
            LotAwarding.objects.create(
                application=application,
                lot_number=lot_number,
                block_number=block_number,
                site_name=site_name,
                awarded_by=request.user,
                notes=notes,
            )

            application.status = 'awarded'
            application.save()

            application.applicant.status = 'awarded'
            application.applicant.save()

            if unit_for_assign:
                _assign_housing_unit_after_lot_award(application, unit_for_assign, request.user)
            else:
                _sync_housing_unit_after_lot_award(
                    application, site_name, block_number, lot_number, request.user
                )

        if application.applicant.phone_number:
            applicant_name = (application.applicant.full_name or '').strip()
            message = (
                f"Congratulations! {applicant_name} You have been awarded Lot {lot_number}"
                f"{' Block ' + block_number if block_number else ''}"
                f"{' at ' + site_name if site_name else ''}. "
                f"Please visit THA office for contract signing and key turnover. "
                f"Reference: {application.applicant.reference_number}"
            )
            send_sms(
                application.applicant.phone_number,
                message,
                'lot_awarded',
                applicant=application.applicant,
                module='applications',
            )

        return JsonResponse({
            'success': True,
            'lot_number': lot_number,
            'message': f'Lot {lot_number} awarded successfully to {application.applicant.full_name}'
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


