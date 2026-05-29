"""
Whether an awarded lot counts as a housing unit on file (map, KPIs, pipeline).

Requires construction at 100% **and** staff Housing unit (normal_progress) on the
binding final monitoring visit — not caretaker submit alone.
"""

from __future__ import annotations

from units.monitoring_policy import (
    TASK_TYPE_EXTENSION_FINAL,
    TASK_TYPE_FINAL_INSPECTION,
)
from units.models import ConstructionProgress, LotAward, MonitoringTask, OccupancyMonitoringCycle


def _report_staff_approved_normal_progress(lot_award, task_type: str) -> bool:
    task = (
        MonitoringTask.objects.filter(
            lot_award=lot_award,
            task_type=task_type,
            status='completed',
        )
        .order_by('-due_date', '-scheduled_date')
        .first()
    )
    if not task:
        return False
    report = task.reports.order_by('-submitted_at').first()
    return bool(report and report.progress_assessment == 'normal_progress')


def housing_unit_staff_final_approved(lot_award: LotAward | None) -> bool:
    """Staff chose Housing unit on the binding final visit (Day 30 or extension Month 2)."""
    if not lot_award:
        return False

    if MonitoringTask.objects.filter(
        lot_award=lot_award,
        task_type=TASK_TYPE_EXTENSION_FINAL,
    ).exists():
        return _report_staff_approved_normal_progress(lot_award, TASK_TYPE_EXTENSION_FINAL)

    if not _report_staff_approved_normal_progress(lot_award, TASK_TYPE_FINAL_INSPECTION):
        return False

    if OccupancyMonitoringCycle.objects.filter(
        lot_award=lot_award,
        is_active=True,
    ).exclude(cycle_stage='original_30_day').exists():
        return False

    return True


def construction_progress_complete(progress: ConstructionProgress | None) -> bool:
    return bool(
        progress
        and progress.stage == 'completed'
        and (progress.percent_complete or 0) >= 100
    )


def housing_unit_on_file(lot_award: LotAward | None, progress: ConstructionProgress | None) -> bool:
    return construction_progress_complete(progress) and housing_unit_staff_final_approved(lot_award)


def housing_unit_on_file_for_lot_award(lot_award: LotAward | None) -> bool:
    if not lot_award:
        return False
    try:
        progress = lot_award.construction_progress
    except ConstructionProgress.DoesNotExist:
        progress = None
    return housing_unit_on_file(lot_award, progress)
