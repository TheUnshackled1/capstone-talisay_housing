"""
Module 4 occupancy monitoring schedule (office policy).

Timeline after lot award:
  - 30-day possession grace
  - Initial field visit at monitoring day 60
  - Final (30 Day) visit 30 calendar days after the initial due date

Explanation-letter extension (60-day build window):
  - Extension 30 Day visit at extension start + 30 days
  - Extension midpoint visit at extension start + 60 days
"""

from __future__ import annotations

from datetime import date, timedelta

POSSESSION_GRACE_DAYS = 30
INITIAL_INSPECTION_DAYS = 60
FINAL_INSPECTION_GAP_DAYS = 30

EXTENSION_BUILD_DAYS = 60
EXTENSION_FINAL_INSPECTION_OFFSET_DAYS = 30
EXTENSION_MIDPOINT_INSPECTION_OFFSET_DAYS = 60

# MonitoringTask.task_type values (stored in DB)
TASK_TYPE_INITIAL_INSPECTION = 'day_60_inspection'
TASK_TYPE_FINAL_INSPECTION = 'day_30_inspection'
TASK_TYPE_EXTENSION_MIDPOINT = 'month_1_inspection'
TASK_TYPE_EXTENSION_FINAL = 'month_2_inspection'
TASK_TYPE_EXTENSION_MONTH_3 = 'month_3_inspection'
TASK_TYPE_FINAL_NOTICE = 'final_inspection'

# Legacy key superseded by TASK_TYPE_INITIAL_INSPECTION (removed after migration 0022)
LEGACY_TASK_TYPE_INITIAL_INSPECTION = 'day_15_inspection'


def monitoring_start_date(award_date: date) -> date:
    return award_date + timedelta(days=POSSESSION_GRACE_DAYS)


def initial_inspection_due(award_date: date) -> date:
    return monitoring_start_date(award_date) + timedelta(days=INITIAL_INSPECTION_DAYS)


def final_inspection_due(award_date: date) -> date:
    return initial_inspection_due(award_date) + timedelta(days=FINAL_INSPECTION_GAP_DAYS)


def initial_inspection_days_from_award() -> int:
    return INITIAL_INSPECTION_DAYS


def final_inspection_days_from_award() -> int:
    return INITIAL_INSPECTION_DAYS + FINAL_INSPECTION_GAP_DAYS
