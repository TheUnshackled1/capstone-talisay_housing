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


def check_blacklist_module2(full_name, phone_number=None, applicant_id=None):
    """
    Module 2 automatic blacklist gate (workflow step 2.1).

    Source of truth: ``units.Blacklist`` (housing monitoring / compliance).

    Returns:
        tuple[bool, _UnitsBlacklistAdapter | None]
    """
    full_name = (full_name or '').strip()
    phone_number = (phone_number or '').strip()
    applicant_id = str(applicant_id or '').strip()

    # Primary source for Module 2 disqualification gate:
    # Units blacklist entries produced by compliance/repossession monitoring.
    units_q = UnitsBlacklist.objects.select_related('applicant')
    units_match = None
    if applicant_id:
        units_match = units_q.filter(applicant_id=applicant_id).order_by('-blacklisted_at').first()
    if not units_match and phone_number:
        units_match = units_q.filter(applicant__phone_number=phone_number).order_by('-blacklisted_at').first()
    if not units_match and full_name:
        units_match = units_q.filter(applicant__full_name__iexact=full_name).order_by('-blacklisted_at').first()
    if not units_match and full_name:
        units_match = units_q.filter(applicant__full_name__icontains=full_name).order_by('-blacklisted_at').first()
    if units_match:
        return True, _UnitsBlacklistAdapter(units_match)

    return False, None


def send_sms_for_applications(recipient_phone, message_content, trigger_event, applicant=None):
    """
    Module 2 SMS gateway wrapper.

    Policy: only 2.8 approved event should send applicant-facing SMS
    from Applications module.
    """
    if trigger_event != 'evaluation_approval_approved':
        return False
    return _base_send_sms(
        recipient_phone,
        message_content,
        trigger_event,
        applicant=applicant,
        module='applications',
    )
