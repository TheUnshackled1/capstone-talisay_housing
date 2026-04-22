"""
Module 2 utility helpers.
"""

from .models import BlacklistProxy
from units.models import Blacklist as UnitsBlacklist


class _IntakeBlacklistAdapter:
    """
    Adapter for intake blacklist rows so Module 2 can consume a unified shape.
    """

    _REASON_LABELS = {
        'repossession': 'Housing Unit Repossessed',
        'fraud': 'Fraudulent Information',
        'violation': 'Violation of Housing Rules',
        'other': 'Other',
    }

    def __init__(self, entry):
        self._entry = entry
        self.notes = (entry.notes or '').strip()
        self.source = 'intake_blacklist'
        self.policy_note = ''

    def get_reason_display(self):
        reason_key = (getattr(self._entry, 'reason', '') or '').strip()
        return self._REASON_LABELS.get(reason_key, reason_key.replace('_', ' ').title() or 'Blacklist match')


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


def check_blacklist_module2(full_name, phone_number=None):
    """
    Module 2 automatic blacklist gate (workflow step 2.1).

    Returns:
        tuple[bool, BlacklistProxy | None]
    """
    full_name = (full_name or '').strip()
    phone_number = (phone_number or '').strip()

    if full_name:
        name_match = BlacklistProxy.objects.filter(
            full_name__icontains=full_name,
        ).first()
        if name_match:
            return True, _IntakeBlacklistAdapter(name_match)

    if phone_number:
        phone_match = BlacklistProxy.objects.filter(
            phone_number=phone_number,
        ).first()
        if phone_match:
            return True, _IntakeBlacklistAdapter(phone_match)

    # Temporary cross-module pipeline:
    # also enforce Units blacklist entries while final consolidation is pending.
    units_name_q = UnitsBlacklist.objects.none()
    units_phone_q = UnitsBlacklist.objects.none()

    if full_name:
        units_name_q = UnitsBlacklist.objects.select_related('applicant').filter(
            applicant__full_name__icontains=full_name,
            reason='repossession',
        )
    if phone_number:
        units_phone_q = UnitsBlacklist.objects.select_related('applicant').filter(
            applicant__phone_number=phone_number,
            reason='repossession',
        )

    units_match = (units_name_q | units_phone_q).order_by('-blacklisted_at').first()
    if units_match:
        return True, _UnitsBlacklistAdapter(units_match)

    return False, None
