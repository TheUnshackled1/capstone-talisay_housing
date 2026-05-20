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


JOURNEY_CYCLE_STEPS = (
    ('evaluation', 'Evaluation & Eligibility'),
    ('ready_for_form', 'Ready for Form queue'),
    ('ready_for_awarding', 'Ready for Awarding'),
    ('housing_units', 'Housing Units'),
    ('cases', 'Cases'),
)

CASE_OPEN_STATUSES = frozenset({
    'pending_review',
    'under_review',
    'mediation_monitoring',
    'awaiting_response',
    'referred_engineering',
})


def _pipeline_cycle_index(
    applicant: Applicant | None, app_obj, bl_row: Blacklist | None
) -> int:
    """0–4 index into JOURNEY_CYCLE_STEPS; -1 when blacklisted."""
    if bl_row:
        return -1
    if not applicant or not getattr(applicant, 'module2_handoff_at', None):
        return 0
    primary, _ = staff_pipeline_primary_detail(applicant, app_obj, None)
    stage_map = {
        'Evaluation & Eligibility': 0,
        'Ready for Form queue': 1,
        'Ready for Awarding': 2,
        'Awarded — pending unit linkage': 2,
        'Awarded lot — not housing unit on file': 3,
        'Housing Units': 3,
    }
    return stage_map.get(primary, 0)


def _journey_step_detail(
    step_key: str,
    applicant: Applicant | None,
    app_obj,
    case_total: int,
    case_open: int,
    case_latest: str,
) -> str:
    if not applicant:
        return ''
    if step_key == 'evaluation':
        if getattr(applicant, 'module2_handoff_at', None):
            return 'Handed off to Application & Eligibility'
        return 'Awaiting Module 2 handoff'
    if step_key == 'ready_for_form':
        if getattr(applicant, 'form_queue_routed_at', None):
            return 'Routed to Ready for Form queue'
        if app_obj and getattr(app_obj, 'form_generated_at', None):
            return 'Application form generated'
        return 'Not yet routed to form queue'
    if step_key == 'ready_for_awarding':
        if not app_obj:
            return 'No application record yet'
        status = (app_obj.status or '').strip()
        if status == 'standby':
            return 'Fully approved — standby for lot award'
        if status == 'awarded':
            return 'Lot awarded'
        if status == 'completed':
            return 'Awaiting OIC / final approval'
        if status == 'draft':
            return 'Form released — in progress'
        return app_obj.get_status_display() if hasattr(app_obj, 'get_status_display') else status or '—'
    if step_key == 'housing_units':
        _, detail = staff_pipeline_primary_detail(applicant, app_obj, None)
        if detail:
            return detail
        la = active_lot_award_with_unit(app_obj) if app_obj else None
        if la and la.unit:
            return f"Block {la.unit.block_number}, Lot {la.unit.lot_number}"
        return 'No housing unit on file yet'
    if step_key == 'cases':
        if case_total <= 0:
            return 'No cases recorded'
        open_part = f'{case_open} open' if case_open else 'all closed'
        latest = f' · Latest: {case_latest}' if case_latest else ''
        return f'{case_total} case{"s" if case_total != 1 else ""} ({open_part}){latest}'
    return ''


def applicant_journey_cycle(
    applicant: Applicant | None,
    app_obj,
    bl_row: Blacklist | None,
    *,
    case_total: int = 0,
    case_open: int = 0,
    case_latest: str = '',
) -> list[dict]:
    """
    Staff pipeline cycle for Archive Summary / journey modals.
    Each step: key, label, state (done|current|upcoming|blocked), detail.
    """
    steps_out = []
    idx = _pipeline_cycle_index(applicant, app_obj, bl_row)

    if bl_row:
        for i, (key, label) in enumerate(JOURNEY_CYCLE_STEPS):
            state = 'blocked' if i == 0 else 'upcoming'
            detail = 'Blacklisted Beneficiaries registry' if i == 0 else ''
            steps_out.append({
                'key': key,
                'label': label,
                'state': state,
                'detail': detail,
            })
        return steps_out

    current_idx = idx
    if case_open > 0:
        current_idx = max(idx, 4)

    for i, (key, label) in enumerate(JOURNEY_CYCLE_STEPS):
        if i < current_idx:
            state = 'done'
        elif i == current_idx:
            state = 'current'
        elif key == 'cases' and case_total > 0 and idx >= 3:
            state = 'done'
        else:
            state = 'upcoming'

        detail = _journey_step_detail(
            key, applicant, app_obj, case_total, case_open, case_latest
        )
        steps_out.append({
            'key': key,
            'label': label,
            'state': state,
            'detail': detail,
        })
    return steps_out


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
