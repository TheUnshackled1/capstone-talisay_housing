from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Prefetch, Max
from django.db import IntegrityError, transaction
from django.utils import timezone
from functools import wraps
from intake.models import Applicant
from intake import sms_workflow
from documents.models import (
    FacilitatedService,
    ElectricityConnection,
    LotAwarding,
    Requirement,
    RequirementSubmission,
    SignatoryRouting,
)
from .models import (
    Application, QueueEntry, CDRRMOCertificationProxy, CDRRMOCertification, FieldVerificationPhoto,
)
from .utils import check_blacklist_module2, send_sms_for_applications

MODULE1_MONTHLY_INCOME_CEILING_PESO = 10000
# Minimum years of residence in Talisay City for Module 2 Layer 2 (2.6) eligibility.
# Mirror of `MODULE1_MIN_YEARS_RESIDING_TALISAY` in intake/views.py — keep in sync.
MODULE1_MIN_YEARS_RESIDING_TALISAY = 5
EVAL28_APPROVED_SMS_EVENT = 'evaluation_approval_approved'


def send_sms(recipient_phone, message_content, trigger_event, applicant=None, module='applications'):
    """
    Applications-module SMS policy:
    Send ISF SMS only after Layer 4 (2.8) is saved as Approved.
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
    - Joie (2nd Member): Supervisor, electricity tracking, routing backup
    - Laarni (5th Member): Electricity tracking
    - Victor (OIC): Final signature
    """
    position = user.position

    permissions = {
        'can_view': False,
        'can_verify_documents': False,
        'can_generate_form': False,
        'can_receive_routing': False,
        'can_forward_routing': False,
        'can_sign_oic': False,
        'can_award_lot': False,
        'can_manage_electricity': False,
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
        # Joie - Supervisor + Electricity
        permissions.update({
            'can_view': True,
            'can_verify_documents': True,  # Supervisor can also verify
            'can_generate_form': True,
            'can_receive_routing': True,  # Supervisor backup for signatory handoff
            'can_forward_routing': True,  # Supervisor backup for signatory handoff
            'can_manage_electricity': True,
            'role_description': 'Supervisor, Routing Backup & Electricity Tracking',
        })
    elif position == 'fifth_member':
        # Laarni - Electricity only
        permissions.update({
            'can_view': True,
            'can_manage_electricity': True,
            'role_description': 'Electricity Tracking',
        })
    elif position == 'oic':
        # Victor - OIC signature
        permissions.update({
            'can_view': True,
            'can_sign_oic': True,
            'role_description': 'OIC Signatory',
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
        'units_blacklist': 'Units Blacklist Entries',
    }
    return source_map.get(getattr(bl_entry, 'source', ''), 'Units Blacklist Entries')


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
    Module 2 workflow step 2.1: blacklist check is now advisory-only.
    Shows red indicator in the eligibility pipeline but does not block actions.
    """
    return None


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
            blacklist_detail += f' — {bl_entry.notes[:200]}'
        advisories.append(f'Blacklist match [{blacklist_source}] ({blacklist_detail}).')
        if blacklist_policy_note:
            advisories.append(blacklist_policy_note)

    income_ok = bool(applicant.is_income_eligible)
    if not income_ok:
        advisories.append(
            f'Declared monthly income ₱{applicant.monthly_income:,.2f} exceeds Module 1 ceiling of ₱{MODULE1_MONTHLY_INCOME_CEILING_PESO:,.0f}.'
        )

    property_ok = not bool(applicant.has_property_in_talisay)
    if not property_ok:
        advisories.append('Applicant is flagged as owning property in Talisay City.')

    declared_household = int(applicant.household_size or 0)
    listed_household = applicant.household_members.count() + 1
    has_min_household = declared_household >= 1
    if not has_min_household:
        advisories.append('Declared household size must be at least 1.')

    # Layer 2 / 2.4 Household Composition: a registered "live-in partner"
    # household member triggers the Household Composition flag and pushes the
    # applicant to the walk-in queue (Module 2 policy).
    live_in_partner_count = applicant.household_members.filter(
        relationship='live_in_partner'
    ).count()
    household_has_live_in_partner = live_in_partner_count > 0
    household_ok = has_min_household and not household_has_live_in_partner
    if household_has_live_in_partner:
        advisories.append(
            'Household Composition flagged: registered household includes a live-in partner '
            '(walk-in path under Module 2 policy).'
        )

    # Layer 2 / 2.5 Voter Registration: applicant must be a registered voter
    # in Talisay City (declared at Module 1 registration). Any non-registered
    # applicant is a Layer 2 flag and pushes them to the walk-in queue.
    voter_ok = bool(applicant.is_registered_voter_talisay)
    if not voter_ok:
        advisories.append(
            'Voter Registration flagged: applicant is not a registered voter in Talisay City '
            '(walk-in path under Module 2 policy).'
        )

    # Layer 2 / 2.6 Length of Residence: applicant must have resided in
    # Talisay City for at least `MODULE1_MIN_YEARS_RESIDING_TALISAY` years.
    # Below threshold is a Layer 2 flag (walk-in path).
    try:
        years_residing_int = int(applicant.years_residing or 0)
    except (TypeError, ValueError):
        years_residing_int = 0
    residency_ok = years_residing_int >= MODULE1_MIN_YEARS_RESIDING_TALISAY
    if not residency_ok:
        advisories.append(
            f'Length of Residence flagged: declared {years_residing_int} year(s) in Talisay City '
            f'is below the {MODULE1_MIN_YEARS_RESIDING_TALISAY}-year minimum '
            '(walk-in path under Module 2 policy).'
        )

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
            'Option D (none of A, B, or C): applicant is on the Walk-in path; Priority is not available for this ground.'
        )

    requires_cdrrmo = bool((applicant.danger_zone_type or '').strip() or (applicant.danger_zone_location or '').strip())
    cdrrmo_status = None
    if requires_cdrrmo:
        try:
            cdrrmo_status = applicant.cdrrmo_certification.status
        except CDRRMOCertification.DoesNotExist:
            cdrrmo_status = None

    # Queue mapping policy (Module 2):
    # - Layer 1 (blacklist) is advisory only; it does not affect queue placement.
    # - Layer 2 (2.2 property, 2.3 income, 2.4 household composition,
    #   2.5 voter registration, 2.6 length of residence) — any flag here
    #   pushes the applicant to the walk-in queue.
    # - Layer 3 — A, B, C, or D. Option D (not_abc) always routes to Walk-in;
    #   A/B/C with Layer 2 clean may route to Priority. Document verification
    #   for A/B/C still happens in Module 3.
    layer2_clear = bool(
        property_ok and income_ok and household_ok and voter_ok and residency_ok
    )
    layer3_clear = bool(displacement_classified)
    qualifies_for_priority = bool(
        layer2_clear
        and (displacement_reason in displacement_reasons_priority)
    )

    if qualifies_for_priority:
        allowed_queue_types = ['priority']
        recommended_queue_type = 'priority'
    else:
        allowed_queue_types = ['walk_in']
        recommended_queue_type = 'walk_in'

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
    }


# =============================================================================
# MAIN APPLICATIONS LIST VIEW
# =============================================================================

@login_required
@verify_position
def applications_list(request, position):
    """
    Module 2 - Housing Application & Eligibility
    Shows eligible applicants with document checklist progress, signatory routing, etc.

    URL: /applications/<position>/list/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Full access: verify docs, generate forms, award lots
    ✅ Jay (3rd Member) - View + routing actions
    ✅ Joie (2nd Member) - Supervisor: verify docs, electricity tracking
    ✅ Laarni (5th Member) - Electricity tracking only
    ✅ Victor (OIC) - View + OIC signature
    """
    # Check access
    allowed_positions = ['fourth_member', 'second_member', 'fifth_member', 'oic']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. Module 2 is for authorized staff only.')
        return redirect('accounts:dashboard')
    
    # Get user permissions
    permissions = get_module2_permissions(request.user)

    # Self-heal records declared as non-hazard in Module 1 but left in pending_cdrrmo.
    Applicant.objects.filter(
        channel='danger_zone',
        status='pending_cdrrmo',
        danger_zone_type='',
        danger_zone_location='',
    ).update(status='pending', updated_at=timezone.now())

    # Legacy safety net: older Module 2 handoffs may have hazard declaration but
    # no pending CDRRMO row yet. Normalize these rows before rendering.
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

    # Auto-heal non-hazard handoff rows that were never queue-assigned.
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
        _auto_finalize_non_hazard_walkin(candidate, acted_by=request.user)
    
    # Module 2 shows only records explicitly handed off from Module 1
    # (plus records already attached to an application object).
    # Once an applicant is 2.6-approved, they leave the Module 2 list and live
    # in Module 3 (documents/<position>/management/) only.
    applicants = Applicant.objects.filter(
        status__in=['pending', 'pending_cdrrmo', 'eligible', 'requirements', 'application', 'standby', 'awarded']
    ).filter(
        Q(module2_handoff_at__isnull=False) | Q(application__isnull=False)
    ).exclude(
        evaluation_approval_status='approved'
    ).select_related(
        'application',
        'cdrrmo_certification',
        'registered_by',
        'module2_handoff_by',
    ).prefetch_related(
        'requirement_submissions',
        'requirement_submissions__requirement',
        Prefetch(
            'application__routing_steps',
            queryset=SignatoryRouting.objects.order_by('action_at'),
        ),
    ).order_by('module2_handoff_at', 'created_at', 'id')
    
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
        ).count(),
        'signatory_routing': applicants.filter(
            application__status='routing'
        ).count(),
        'fully_approved': applicants.filter(
            application__status__in=['oic_signed', 'standby']
        ).count(),
        'lot_awarded': applicants.filter(
            application__status='awarded'
        ).count(),
    }
    
    # Check for routing delays (>3 days)
    delayed_routings = SignatoryRouting.objects.filter(
        action_at__lt=timezone.now() - timezone.timedelta(days=3)
    ).select_related('application', 'application__applicant')
    
    # Prepare applicant data with document counts
    applicants_data = []
    for applicant in applicants:
        # Count verified Group A documents
        group_a_verified = applicant.requirement_submissions.filter(
            requirement__group='A',
            status='verified'
        ).count()
        
        # Check if form can be generated (all 7 Group A verified)
        can_generate_form = group_a_verified >= 7
        
        # Get application status if exists
        application = getattr(applicant, 'application', None)
        application_status = application.status if application else None
        
        # Determine current stage
        if application and application.status == 'awarded':
            current_stage = 'Lot Awarded'
        elif application and application.status in ['oic_signed', 'standby']:
            current_stage = 'Fully Approved'
        elif application and application.status == 'routing':
            current_stage = 'Signatory Routing'
        elif application and application.status in ['draft', 'completed']:
            current_stage = 'Form Released'
        elif group_a_verified > 0:
            current_stage = 'Document Gathering'
        else:
            current_stage = 'Eligibility'
        
        # Get routing status
        routing_status = 'Not Started'
        latest_routing_step = None
        if application:
            latest_routing = application.routing_steps.last()
            if latest_routing:
                latest_routing_step = latest_routing.step
                if latest_routing.step == 'signed_oic':
                    routing_status = 'Completed'
                else:
                    routing_status = 'In Progress'
        
        # Check for routing delay
        is_delayed = False
        delayed_at = None
        if application:
            for step in application.routing_steps.all():
                if step.is_delayed:
                    is_delayed = True
                    delayed_at = step.get_step_display()
                    break
        
        # Determine what actions this user can take on this applicant
        user_actions = []
        if permissions['can_verify_documents'] and not application:
            user_actions.append('verify_docs')
        if permissions['can_generate_form'] and can_generate_form and not application:
            user_actions.append('generate_form')
        if permissions['can_receive_routing'] and application and application.status in ['draft', 'completed']:
            user_actions.append('receive_routing')
        if permissions['can_forward_routing'] and application and latest_routing_step == 'received':
            user_actions.append('forward_to_oic')
        if permissions['can_sign_oic'] and application and latest_routing_step == 'forwarded_oic':
            user_actions.append('sign_oic')
        if permissions['can_award_lot'] and application and application.status in ['oic_signed', 'standby']:
            user_actions.append('award_lot')
        if permissions['can_manage_electricity'] and application and application.status == 'awarded':
            user_actions.append('manage_electricity')

        # --- Central Module 2 eligibility rules snapshot ---
        rules = _module2_eligibility_snapshot(applicant, checked_by=request.user)
        blacklist_blocked = rules['blacklist_blocked']
        blacklist_detail = rules['blacklist_detail']
        blacklist_source = rules['blacklist_source']
        blacklist_policy_note = rules['blacklist_policy_note']
        # Blacklist is advisory-only; do not strip actions.

        applicants_data.append({
            'applicant': applicant,
            'application': application,
            'applicant_status': applicant.status,
            'applicant_status_display': applicant.get_status_display(),
            'cdrrmo_status': getattr(getattr(applicant, 'cdrrmo_certification', None), 'status', None),
            'group_a_verified': group_a_verified,
            'can_generate_form': can_generate_form and application is None,
            'form_generated': application is not None,
            'current_stage': current_stage,
            'routing_status': routing_status,
            'latest_routing_step': latest_routing_step,
            'is_delayed': is_delayed,
            'delayed_at': delayed_at,
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
            'evaluation_approval_status': applicant.evaluation_approval_status or '',
            'evaluation_approval_status_display': applicant.get_evaluation_approval_status_display() if applicant.evaluation_approval_status else '',
        })
    
    # Filter by stage if requested
    filter_stage = request.GET.get('stage', 'all')
    if filter_stage != 'all':
        stage_map = {
            'eligibility': 'Eligibility',
            'document_gathering': 'Document Gathering',
            'form_released': 'Form Released',
            'signatory_routing': 'Signatory Routing',
            'fully_approved': 'Fully Approved',
            'lot_awarded': 'Lot Awarded',
        }
        target_stage = stage_map.get(filter_stage)
        if target_stage:
            applicants_data = [a for a in applicants_data if a['current_stage'] == target_stage]

    filter_eval28 = request.GET.get('eval28', 'all')
    if filter_eval28 != 'all':
        if filter_eval28 == 'not_recorded':
            applicants_data = [a for a in applicants_data if not (a.get('evaluation_approval_status') or '').strip()]
        elif filter_eval28 in ('approved', 'for_review'):
            applicants_data = [a for a in applicants_data if a.get('evaluation_approval_status') == filter_eval28]
    
    # Search filter
    search = request.GET.get('search', '')
    if search:
        applicants_data = [
            a for a in applicants_data
            if search.lower() in a['applicant'].full_name.lower() or
               search.lower() in a['applicant'].reference_number.lower()
        ]

    from_intake_handoff = request.GET.get('from') == 'intake_scan_checklist'
    intake_handoff_ref = (request.GET.get('ref') or '').strip()[:120]

    context = {
        'applicants_data': applicants_data,
        'stage_counts': stage_counts,
        'requirements': requirements,
        'group_a_requirements': group_a_requirements,
        'group_b_requirements': group_b_requirements,
        'delayed_routings': delayed_routings,
        'filter_stage': filter_stage,
        'filter_eval28': filter_eval28,
        'search': search,
        'total_eligible': applicants.count(),
        'permissions': permissions,
        'user_position': request.user.position,
        'from_intake_handoff': from_intake_handoff,
        'intake_handoff_ref': intake_handoff_ref,
    }
    
    return render(request, 'applications/applications_list.html', context)


# =============================================================================
# APPLICATION DETAIL (AJAX)
# =============================================================================

@login_required
@verify_position
def application_detail(request, position, application_id):
    """
    Get applicant/application detail for modal (AJAX).

    URL: /applications/<position>/detail/<application_id>/

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
                'routing_steps',
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
        'routing_steps': [],
        'latest_step': None,
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
                if ph.image:
                    try:
                        photo_urls.append(request.build_absolute_uri(ph.image.url))
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
        
        # Add routing steps
        latest_step = None
        for step in application.routing_steps.all().order_by('action_at'):
            latest_step = step.step
            data['routing_steps'].append({
                'step': step.step,
                'step_display': step.get_step_display(),
                'action_at': step.action_at.strftime('%Y-%m-%d %H:%M'),
                'action_by': step.action_by.get_full_name() if step.action_by else 'System',
                'is_delayed': step.is_delayed,
                'days_since': step.days_since_action,
            })
        data['latest_step'] = latest_step
    
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
    allowed_positions = ['fourth_member', 'second_member', 'oic']
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
                    sms_msg = sms_workflow.message_cdrrmo_office_received(applicant, queue_entry.position)
                    sms_event = sms_workflow.CDRRMO_OFFICE_CERTIFIED
                else:
                    sms_msg = sms_workflow.message_cdrrmo_certified_priority(applicant, queue_entry.position)
                    sms_event = sms_workflow.CDRRMO_CERTIFIED
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
            sent = send_sms(applicant.phone_number, sms_msg, sms_workflow.CDRRMO_NOT_CERTIFIED, applicant=applicant, module='applications')
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
    Module 2 — Layer 3 acknowledgement (particulars are captured at Module 1 registration).

    For new applicants, ``review_only=1`` runs queue placement using the
    displacement reason and details already stored on the Applicant record.

    The full POST body (``displacement_reason``, ``hazard_type``, etc.) remains
    supported as a legacy/administrative override when needed.
    """
    allowed_positions = ['fourth_member', 'second_member', 'oic']
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
                'message': 'Layer 3 acknowledged — particulars are on file from Module 1 intake.',
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
        # the applicant is moved to the Priority Queue immediately — regardless
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
    Module 2 endpoint for Ronda/Field on-site verification findings.
    """
    if request.user.position not in ['ronda', 'field']:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only field personnel can verify.'}, status=403)

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
        if cert.status != 'pending':
            return JsonResponse({
                'success': False,
                'error': (
                    'A CDRRMO disposition is already on file (for example, official certification received at THA intake). '
                    'Field verification cannot overwrite it.'
                ),
            })

        cert.status = verification_decision
        cert.certified_at = timezone.now()
        cert.result_recorded_by = request.user
        cert.disposition_source = 'field_unit'
        cert.office_intake_notes = ''
        cert.certification_notes = verification_notes if verification_notes else ''
        cert.save()

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
            sms_dispatched = send_sms(applicant.phone_number, sms_body, sms_ev, applicant=applicant, module='applications')

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
                # Not certified finding approved by staff — assign to Walk-in queue.
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

        # Staff rejected CDRRMO finding — assign to Walk-in queue instead of disqualifying.
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
    force_sms = str(request.POST.get('force_sms', '')).strip().lower() in {'1', 'true', 'yes', 'on'}

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

    previous_eval28_status = applicant.evaluation_approval_status or ''

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

    # NOTE: Layer 3 CDRRMO completion gate temporarily disabled — 2.8 approval can
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

    sms_dispatched = None
    should_send_eval28_sms = approval_status == 'approved' and applicant.phone_number and (
        previous_eval28_status != approval_status or force_sms
    )
    if should_send_eval28_sms:
        queue_label = 'Priority Queue' if (active_queue and active_queue.queue_type == 'priority') else 'Walk-in Queue'
        queue_pos = active_queue.position if active_queue else '?'
        sms_msg = (
            "THA update: Your Module 2 eligibility approval has been recorded. "
            f"Queue assignment: {queue_label} position #{queue_pos}. "
            f"Ref: {applicant.reference_number}."
        )
        sms_dispatched = send_sms_for_applications(
            applicant.phone_number,
            sms_msg,
            EVAL28_APPROVED_SMS_EVENT,
            applicant=applicant,
        )

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
# DOCUMENT VERIFICATION (Jocel, Joie)
# =============================================================================

@login_required
@verify_position
@require_POST
def update_requirement(request, position):
    """
    Update requirement submission status (AJAX).

    URL: /applications/<position>/requirement/update/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary document verifier
    ✅ Joie (2nd Member) - Supervisor backup
    """
    # Check permission
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False, 
            'error': 'Permission denied. Only Jocel or Joie can verify documents.'
        }, status=403)
    
    applicant_id = request.POST.get('applicant_id')
    requirement_code = request.POST.get('requirement_code')
    status = request.POST.get('status')
    
    # UI fallback codes (used when requirements table is empty) -> canonical DB codes
    requirement_aliases = {
        'brgy_residency': ('brgy_res', 'Brgy. Certificate of Residency', 1),
        'brgy_indigency': ('brgy_ind', 'Brgy. Certificate of Indigency', 2),
        'cedula': ('cedula', 'Cedula', 3),
        'police_clearance': ('police_clr', 'Police Clearance', 4),
        'no_property': ('no_prop', 'Certificate of No Property', 5),
        'photo_2x2': ('photo2x2', '2x2 Picture', 6),
        'sketch': ('sketch', 'Sketch of House Location', 7),
    }

    try:
        applicant = Applicant.objects.get(id=applicant_id)
        handoff_error = _require_intake_archive(applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(applicant)
        if blacklist_error:
            return blacklist_error

        # Resolve incoming code and self-heal missing Requirement rows.
        resolved = requirement_aliases.get(requirement_code)
        canonical_code = resolved[0] if resolved else requirement_code

        requirement = Requirement.objects.filter(code=canonical_code).first()
        if requirement is None:
            if resolved is None:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown requirement code: {requirement_code}',
                }, status=400)
            requirement = Requirement.objects.create(
                code=canonical_code,
                name=resolved[1],
                group='A',
                order=resolved[2],
                is_required_for_form=True,
                is_active=True,
            )
        
        submission, created = RequirementSubmission.objects.get_or_create(
            applicant=applicant,
            requirement=requirement,
            defaults={'status': status}
        )
        
        if not created:
            submission.status = status
            if status == 'verified':
                submission.verified_at = timezone.now()
                submission.verified_by = request.user
            elif status == 'submitted':
                submission.submitted_at = timezone.now()
            submission.save()
        
        # Check if all 7 Group A documents are now verified
        group_a_verified = applicant.requirement_submissions.filter(
            requirement__group='A',
            status='verified'
        ).count()
        
        # Send SMS when all 7 verified
        if group_a_verified >= 7 and applicant.phone_number:
            # Check if we already sent this notification
            existing_app = hasattr(applicant, 'application')
            if not existing_app:
                message = (
                    f"All 7 requirements verified! Please visit Talisay Housing Authority "
                    f"to sign your application form. Reference: {applicant.reference_number}"
                )
                send_sms(applicant.phone_number, message, 'documents_complete', applicant=applicant, module='applications')
        
        return JsonResponse({
            'success': True,
            'group_a_verified': group_a_verified,
            'all_verified': group_a_verified >= 7,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


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
    
    applicant = get_object_or_404(Applicant, id=applicant_id)
    handoff_error = _require_intake_archive(applicant)
    if handoff_error:
        return handoff_error
    blacklist_error = _require_module2_blacklist_clear(applicant)
    if blacklist_error:
        return blacklist_error

    rules = _module2_eligibility_snapshot(applicant)
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
    
    # Check if all Group A requirements are verified
    group_a_count = applicant.requirement_submissions.filter(
        requirement__group='A',
        status='verified'
    ).count()
    
    if group_a_count < 7:
        return JsonResponse({
            'success': False,
            'error': f'Only {group_a_count}/7 requirements verified. All 7 must be complete.'
        })
    
    # Check if application already exists
    if hasattr(applicant, 'application'):
        return JsonResponse({
            'success': False,
            'error': 'Application form already generated.'
        })
    
    # Create application
    application = Application.objects.create(
        applicant=applicant,
        form_generated_by=request.user,
        status='draft'
    )
    
    # Update applicant status
    applicant.status = 'application'
    applicant.save()
    
    # Send SMS notification
    if applicant.phone_number:
        from intake import sms_workflow
        message = sms_workflow.message_proceed_to_evaluation(applicant)
        send_sms(applicant.phone_number, message, sms_workflow.PROCEED_TO_EVALUATION, applicant=applicant, module='applications')
    
    return JsonResponse({
        'success': True,
        'application_number': application.application_number,
        'message': f'Application form {application.application_number} generated successfully.'
    })


# =============================================================================
# SIGNATORY ROUTING (Jocel/Joie, OIC)
# =============================================================================

@login_required
@verify_position
@require_POST
def update_routing(request, position):
    """
    Update signatory routing step (AJAX).

    URL: /applications/<position>/routing/update/

    ACCESS CONTROL:
    - Staff (Jocel 4th / Joie 2nd): marks physical-paper checkpoints
    - OIC may update its own signature checkpoint
    """
    application_id = request.POST.get('application_id')
    step = request.POST.get('step')
    notes = request.POST.get('notes', '')
    
    # Validate step and check permission
    step_permissions = {
        'received': ['fourth_member', 'second_member'],
        'forwarded_oic': ['fourth_member', 'second_member'],
        'signed_oic': ['fourth_member', 'second_member', 'oic'],
    }

    allowed_positions = step_permissions.get(step, [])
    if request.user.position not in allowed_positions:
        position_names = {
            'fourth_member': 'Jocel (4th Member)',
            'second_member': 'Joie (2nd Member)',
            'oic': 'Victor (OIC)',
        }
        required = ', '.join([position_names.get(p, p) for p in allowed_positions])
        return JsonResponse({
            'success': False,
            'error': f'Permission denied. This action requires: {required}'
        }, status=403)
    
    try:
        application = Application.objects.select_related('applicant').get(id=application_id)
        handoff_error = _require_intake_archive(application.applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(application.applicant)
        if blacklist_error:
            return blacklist_error

        step_sequence = ['received', 'forwarded_oic', 'signed_oic']
        if step not in step_sequence:
            return JsonResponse({'success': False, 'error': 'Invalid routing step.'}, status=400)

        completed_steps = set(application.routing_steps.values_list('step', flat=True))
        if step in completed_steps:
            return JsonResponse({
                'success': True,
                'new_status': application.status,
                'message': f'Routing step "{step}" already recorded.'
            })

        step_index = step_sequence.index(step)
        if step_index > 0:
            previous_step = step_sequence[step_index - 1]
            if previous_step not in completed_steps:
                return JsonResponse({
                    'success': False,
                    'error': f'Cannot mark "{step}" before "{previous_step}" is completed.'
                }, status=400)
        
        # Create routing step
        SignatoryRouting.objects.create(
            application=application,
            step=step,
            action_by=request.user,
            notes=notes
        )
        
        # Update application status based on step
        if step == 'signed_oic':
            application.status = 'oic_signed'
            application.fully_approved_at = timezone.now()

            # Send SMS: Fully Approved
            if application.applicant.phone_number:
                message = (
                    f"Congratulations! Your housing application {application.application_number} "
                    f"has been FULLY APPROVED. You are now on the Standby Queue. "
                    f"Please wait for lot availability notification. Reference: {application.applicant.reference_number}"
                )
                send_sms(application.applicant.phone_number, message, 'fully_approved', applicant=application.applicant, module='applications')

        elif step in ['received', 'forwarded_oic']:
            application.status = 'routing'
        
        application.save()
        
        return JsonResponse({
            'success': True,
            'new_status': application.status,
            'message': f'Routing step "{step}" recorded successfully.'
        })
    except Application.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Application not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# MOVE TO STANDBY QUEUE
# =============================================================================

@login_required
@verify_position
@require_POST
def move_to_standby(request, position):
    """
    Move fully approved application to standby queue.

    URL: /applications/<position>/standby/

    ACCESS CONTROL:
    ✅ Jocel (4th Member) - Primary
    ✅ Joie (2nd Member) - Supervisor
    """
    allowed_positions = ['fourth_member', 'second_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Jocel or Joie can manage standby queue.'
        }, status=403)
    
    application_id = request.POST.get('application_id')
    
    try:
        application = Application.objects.select_related('applicant').get(id=application_id)
        handoff_error = _require_intake_archive(application.applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(application.applicant)
        if blacklist_error:
            return blacklist_error
        
        if application.status != 'oic_signed':
            return JsonResponse({
                'success': False,
                'error': 'Application must be fully approved (OIC signed) before moving to standby.'
            })
        
        application.status = 'standby'
        application.standby_entered_at = timezone.now()
        
        # Calculate standby position
        last_position = Application.objects.filter(
            status='standby'
        ).exclude(id=application.id).aggregate(
            max_pos=Max('standby_position')
        )['max_pos'] or 0
        application.standby_position = last_position + 1
        
        application.save()

        if application.applicant.phone_number:
            message = (
                f"Your housing application {application.application_number} is now on the STANDBY queue "
                f"(position #{application.standby_position}). You will be notified when a lot is ready for awarding. "
                f"Reference: {application.applicant.reference_number}"
            )
            send_sms(
                application.applicant.phone_number,
                message,
                'standby_queue',
                applicant=application.applicant,
                module='applications',
            )
        
        return JsonResponse({
            'success': True,
            'standby_position': application.standby_position,
            'message': f'Moved to Standby Queue at position #{application.standby_position}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# LOT AWARDING (Jocel)
# =============================================================================

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
    lot_number = request.POST.get('lot_number')
    block_number = request.POST.get('block_number', '')
    site_name = request.POST.get('site_name', '')
    
    if not lot_number:
        return JsonResponse({'success': False, 'error': 'Lot number is required.'})
    
    try:
        application = Application.objects.select_related('applicant').get(id=application_id)
        handoff_error = _require_intake_archive(application.applicant)
        if handoff_error:
            return handoff_error
        blacklist_error = _require_module2_blacklist_clear(application.applicant)
        if blacklist_error:
            return blacklist_error
        
        if application.status not in ['oic_signed', 'standby']:
            return JsonResponse({
                'success': False,
                'error': 'Application must be fully approved before lot can be awarded.'
            })
        
        # Create lot awarding record
        lot_awarding = LotAwarding.objects.create(
            application=application,
            lot_number=lot_number,
            block_number=block_number,
            site_name=site_name,
            awarded_by=request.user
        )
        
        # Update application status
        application.status = 'awarded'
        application.save()
        
        # Update applicant status
        application.applicant.status = 'awarded'
        application.applicant.save()
        
        # Create electricity connection record (pending)
        ElectricityConnection.objects.create(
            application=application,
            status='pending'
        )
        
        # Send SMS notification
        if application.applicant.phone_number:
            message = (
                f"Congratulations! You have been awarded Lot {lot_number}"
                f"{' Block ' + block_number if block_number else ''}"
                f"{' at ' + site_name if site_name else ''}. "
                f"Please visit THA office for contract signing and key turnover. "
                f"Reference: {application.applicant.reference_number}"
            )
            send_sms(application.applicant.phone_number, message, 'lot_awarded', applicant=application.applicant, module='applications')
        
        return JsonResponse({
            'success': True,
            'lot_number': lot_number,
            'message': f'Lot {lot_number} awarded successfully to {application.applicant.full_name}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# ELECTRICITY TRACKING (Joie, Laarni)
# =============================================================================

@login_required
@verify_position
def electricity_list(request, position):
    """
    Deprecated path kept for backward compatibility.
    Electricity tracking moved to Housing Units module.
    """
    return redirect('units:electricity_list', position=position)


@login_required
@verify_position
@require_POST
def update_electricity(request, position):
    """
    Deprecated path kept for backward compatibility.
    Electricity tracking moved to Housing Units module.
    """
    from units.views import update_electricity as units_update_electricity
    return units_update_electricity(request, position)
