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


import datetime
from django.utils import timezone

def _report_staff_approved_normal_progress(lot_award, task_type: str) -> bool:
    tasks = [t for t in lot_award.monitoring_tasks.all() if t.task_type == task_type and t.status == 'completed']
    if not tasks:
        return False
    tasks.sort(key=lambda t: (t.due_date or datetime.date.min, t.scheduled_date or datetime.date.min), reverse=True)
    task = tasks[0]
    
    reports = list(task.reports.all())
    if not reports:
        return False
    reports.sort(key=lambda r: r.submitted_at or timezone.now(), reverse=True)
    report = reports[0]
    return bool(report.progress_assessment == 'normal_progress')


def housing_unit_staff_final_approved(lot_award: LotAward | None) -> bool:
    """Staff chose Housing unit on the binding final visit (Day 30 or extension Month 2)."""
    if not lot_award:
        return False

    has_extension = any(t.task_type == TASK_TYPE_EXTENSION_FINAL for t in lot_award.monitoring_tasks.all())
    if has_extension:
        return _report_staff_approved_normal_progress(lot_award, TASK_TYPE_EXTENSION_FINAL)

    if not _report_staff_approved_normal_progress(lot_award, TASK_TYPE_FINAL_INSPECTION):
        return False

    has_active_non_original = any(c.is_active and c.cycle_stage != 'original_30_day' for c in lot_award.monitoring_cycles.all())
    if has_active_non_original:
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
