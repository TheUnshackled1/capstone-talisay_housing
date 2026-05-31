"""
Module 4 occupancy monitoring schedule (office policy).

Timeline after lot award:
  - 30-day possession grace
  - Initial field visit at monitoring day 90
  - Final (120 Day) visit 120 calendar days after the 90 Day due date

Explanation-letter extension (90-day build window):
  - Extension 30 Day visit at extension start + 30 days
  - Extension midpoint visit at extension start + 90 days
"""

from __future__ import annotations

from datetime import date, timedelta

POSSESSION_GRACE_DAYS = 30
INITIAL_INSPECTION_DAYS = 90
# Final visit is scheduled this many calendar days after the 90 Day visit due date.
FINAL_INSPECTION_GAP_AFTER_INITIAL_DAYS = 120
# Monitoring day index (after grace) when the final visit is due: 90 + 120 = 210.
FINAL_INSPECTION_DAYS_FROM_MONITORING_START = (
    INITIAL_INSPECTION_DAYS + FINAL_INSPECTION_GAP_AFTER_INITIAL_DAYS
)

EXTENSION_BUILD_DAYS = 90
EXTENSION_FINAL_INSPECTION_OFFSET_DAYS = 30
EXTENSION_MIDPOINT_INSPECTION_OFFSET_DAYS = 90

# MonitoringTask.task_type values (stored in DB; labels are 90 Day / 120 Day in UI)
TASK_TYPE_INITIAL_INSPECTION = 'day_60_inspection'
TASK_TYPE_FINAL_INSPECTION = 'day_30_inspection'
TASK_TYPE_EXTENSION_MIDPOINT = 'month_1_inspection'
TASK_TYPE_EXTENSION_FINAL = 'month_2_inspection'
TASK_TYPE_EXTENSION_MONTH_3 = 'month_3_inspection'
TASK_TYPE_FINAL_NOTICE = 'final_inspection'

# Legacy key superseded by TASK_TYPE_INITIAL_INSPECTION (removed after migration 0022)
LEGACY_TASK_TYPE_INITIAL_INSPECTION = 'day_15_inspection'

# User-facing visit labels (task_type keys unchanged for stable migrations/reports)
INITIAL_INSPECTION_LABEL = '90 Day'
FINAL_INSPECTION_LABEL = '120 Day'
INITIAL_INSPECTION_INSPECTION_LABEL = '90 Day Inspection'
FINAL_INSPECTION_INSPECTION_LABEL = '120 Day Inspection'
MONITORING_POLICY_SUMMARY = '30-day grace, 90 Day visit, then 120 Day after 90 Day'


def monitoring_start_date(award_date: date) -> date:
    return award_date + timedelta(days=POSSESSION_GRACE_DAYS)


def initial_inspection_due(award_date: date) -> date:
    return monitoring_start_date(award_date) + timedelta(days=INITIAL_INSPECTION_DAYS)


def final_inspection_due(award_date: date) -> date:
    return initial_inspection_due(award_date) + timedelta(days=FINAL_INSPECTION_GAP_AFTER_INITIAL_DAYS)


def initial_inspection_days_from_award() -> int:
    return INITIAL_INSPECTION_DAYS


def final_inspection_days_from_award() -> int:
    return FINAL_INSPECTION_DAYS_FROM_MONITORING_START


def inspection_display_label(task_type: str, *, short: bool = False) -> str:
    """Map stored task_type to current office-policy labels."""
    if task_type == TASK_TYPE_INITIAL_INSPECTION:
        return INITIAL_INSPECTION_LABEL if short else INITIAL_INSPECTION_INSPECTION_LABEL
    if task_type == TASK_TYPE_FINAL_INSPECTION:
        return FINAL_INSPECTION_LABEL if short else FINAL_INSPECTION_INSPECTION_LABEL
    if task_type == TASK_TYPE_EXTENSION_MIDPOINT:
        return 'Extension 90 Day' if short else 'Extension 90 Day Inspection'
    if task_type == TASK_TYPE_EXTENSION_FINAL:
        return 'Extension 30 Day' if short else 'Extension 30 Day Inspection'
    return task_type.replace('_', ' ').title()
