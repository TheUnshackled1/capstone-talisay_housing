"""
Shared staff-facing labels for applicant pipeline stage (Modules 2–4 + blacklist registry).
Used by Document Management and Intake Archives.
"""

from __future__ import annotations

from intake.models import Applicant
from units.models import Blacklist, LotAward
from units.housing_unit_status import housing_unit_on_file_for_lot_award


def active_lot_award_with_unit(app_obj) -> LotAward | None:
    if not app_obj:
        return None
    for la in app_obj.lot_awards.all():
        if la.status == 'active' and la.unit_id:
            return la
    return None


def staff_pipeline_primary_detail(
    applicant: Applicant, app_obj, bl_row: Blacklist | None
) -> tuple[str, str | None]:
    """
    Primary Applicant Status line plus optional detail (block/lot / occupancy).

    Blacklisted Beneficiaries registry overrides post-award labels.
    """
    if bl_row:
        return ('Blacklisted Beneficiaries registry', None)

    la_active = active_lot_award_with_unit(app_obj) if app_obj else None
    if la_active and la_active.unit:
        unit = la_active.unit
        loc = f'Block {unit.block_number}, Lot {unit.lot_number}'
        if housing_unit_on_file_for_lot_award(la_active):
            status_disp = unit.get_status_display() if hasattr(unit, 'get_status_display') else unit.status
            return (
                'Housing Units',
                f'{loc} · Housing unit on file · {status_disp}',
            )
        status_disp = unit.get_status_display() if hasattr(unit, 'get_status_display') else unit.status
        return (
            'Awarded lot — not housing unit on file',
            f'{loc} · {status_disp}',
        )

    if app_obj:
        if app_obj.status == 'awarded':
            return ('Awarded — pending unit linkage', None)
        if app_obj.status == 'standby':
            return ('Ready for Awarding', None)
        if app_obj.status == 'completed':
            return ('Ready for Awarding', None)

    if getattr(applicant, 'form_queue_routed_at', None):
        return ('Ready for Form queue', None)
    return ('Evaluation & Eligibility', None)


def archive_applicant_status(
    applicant: Applicant | None, bl_row: Blacklist | None
) -> tuple[str, str | None]:
    """
    Intake Archives table: current stage including pre–Module 2 handoff (Applicant Intake).
    """
    if not applicant:
        return ('—', None)
    if bl_row:
        return ('Blacklisted Beneficiaries registry', None)
    if not getattr(applicant, 'module2_handoff_at', None):
        return ('Applicant Intake', None)
    app_obj = getattr(applicant, 'application', None)
    return staff_pipeline_primary_detail(applicant, app_obj, None)
