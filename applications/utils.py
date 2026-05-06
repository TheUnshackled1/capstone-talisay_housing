"""
Module 2 utility helpers.
"""

from units.models import Blacklist as UnitsBlacklist
from intake.utils import send_sms as _base_send_sms


class _UnitsBlacklistAdapter:
    """
    Adapter to make Units blacklist entries compatible with Module 2 checks.
    Exposes `get_reason_display()` and `notes` like intake blacklist entries.
    """

    def __init__(self, entry):
        self._entry = entry
        self.notes = ' '.join(
            part for part in [
                (entry.reason_details or '').strip(),
                (entry.supporting_notes or '').strip(),
            ]
            if part
        ).strip()
        self.source = 'units_blacklist'
        self.policy_note = ''
        if entry.reason == 'repossession':
            self.policy_note = (
                'Housing Units monitoring flag: prior lot award was repossessed due to non-compliance with '
                'house-construction/compliance requirements.'
            )

    def get_reason_display(self):
        return self._entry.get_reason_display()

    @property
    def full_name(self):
        return self._entry.applicant.full_name if self._entry and self._entry.applicant else ''


def check_blacklist_module2(
    full_name,
    phone_number=None,
    applicant_id=None,
    last_name=None,
    first_name=None,
    date_of_birth=None,
    barangay_id=None,
):
    """
    Module 2 automatic blacklist gate (workflow step 2.1).

    Source of truth: ``units.Blacklist`` (housing monitoring / compliance).

    Match priority (first match wins):
        1. Applicant UUID (direct OneToOne link — strongest)
        2. Phone number (exact)
        3. Last name + First name + Date of birth + Barangay (full identity match)
        4. Last name + First name + Date of birth (3-of-4)
        5. Last name + First name + Barangay (3-of-4 — when DOB unknown)
        6. Full name (case-insensitive exact) — last-resort fallback

    Returns:
        tuple[bool, _UnitsBlacklistAdapter | None]
    """
    full_name = (full_name or '').strip()
    phone_number = (phone_number or '').strip()
    applicant_id = str(applicant_id or '').strip()
    last_name = (last_name or '').strip()
    first_name = (first_name or '').strip()
    if hasattr(barangay_id, 'pk'):
        barangay_id = barangay_id.pk

    # Primary source for Module 2 disqualification gate:
    # Units blacklist entries produced by compliance/repossession monitoring.
    units_q = UnitsBlacklist.objects.select_related('applicant')
    units_match = None

    if applicant_id:
        units_match = (
            units_q.filter(applicant_id=applicant_id)
            .order_by('-blacklisted_at')
            .first()
        )

    if not units_match and phone_number:
        units_match = (
            units_q.filter(applicant__phone_number=phone_number)
            .order_by('-blacklisted_at')
            .first()
        )

    has_first_last = bool(first_name and last_name)

    if not units_match and has_first_last and date_of_birth and barangay_id:
        units_match = (
            units_q.filter(
                applicant__last_name__iexact=last_name,
                applicant__first_name__iexact=first_name,
                applicant__date_of_birth=date_of_birth,
                applicant__barangay_id=barangay_id,
            )
            .order_by('-blacklisted_at')
            .first()
        )

    if not units_match and has_first_last and date_of_birth:
        units_match = (
            units_q.filter(
                applicant__last_name__iexact=last_name,
                applicant__first_name__iexact=first_name,
                applicant__date_of_birth=date_of_birth,
            )
            .order_by('-blacklisted_at')
            .first()
        )

    if not units_match and has_first_last and barangay_id:
        units_match = (
            units_q.filter(
                applicant__last_name__iexact=last_name,
                applicant__first_name__iexact=first_name,
                applicant__barangay_id=barangay_id,
            )
            .order_by('-blacklisted_at')
            .first()
        )

    if not units_match and full_name:
        units_match = (
            units_q.filter(applicant__full_name__iexact=full_name)
            .order_by('-blacklisted_at')
            .first()
        )

    if units_match:
        return True, _UnitsBlacklistAdapter(units_match)

    return False, None


_APPLICATIONS_SMS_TRIGGERS = frozenset({
    'eligibility_check_failed',
    'lot_awarded',
    'lot_awarding_queue_notify',
})


def send_sms_for_applications(recipient_phone, message_content, trigger_event, applicant=None):
    """
    Module 2 SMS gateway wrapper.

    Allowed triggers:
    - eligibility_check_failed (checklist SMS opt-in)
    - lot_awarded (post–lot-award congratulations / office visit)
    - lot_awarding_queue_notify (staff bulk notify from Lot Awarding queue; no schedule stored)
    """
    if trigger_event not in _APPLICATIONS_SMS_TRIGGERS:
        return False
    return _base_send_sms(
        recipient_phone,
        message_content,
        trigger_event,
        applicant=applicant,
        module='applications',
    )
