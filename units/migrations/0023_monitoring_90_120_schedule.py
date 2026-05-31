"""Reschedule original-program monitoring to 90 / 120 days; extension window to 90 days."""

from datetime import timedelta

from django.db import migrations, models


def _monitoring_start(award_date):
    return award_date + timedelta(days=30)


def reschedule_to_90_120(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")
    ExtensionRecord = apps.get_model("units", "ExtensionRecord")
    OccupancyMonitoringCycle = apps.get_model("units", "OccupancyMonitoringCycle")

    pending_statuses = ("pending", "overdue")

    for task in (
        MonitoringTask.objects.filter(
            task_type="day_60_inspection",
            status__in=pending_statuses,
        )
        .select_related("lot_award")
        .iterator()
    ):
        awarded_at = getattr(task.lot_award, "awarded_at", None)
        if not awarded_at:
            continue
        award_date = awarded_at.date()
        new_due = _monitoring_start(award_date) + timedelta(days=90)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=90,
        )

    for task in (
        MonitoringTask.objects.filter(
            task_type="day_30_inspection",
            status__in=pending_statuses,
        )
        .select_related("lot_award")
        .iterator()
    ):
        awarded_at = getattr(task.lot_award, "awarded_at", None)
        if not awarded_at:
            continue
        award_date = awarded_at.date()
        new_due = _monitoring_start(award_date) + timedelta(days=120)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=120,
        )

    for ext in ExtensionRecord.objects.filter(lot_award__status="active").iterator():
        new_end = ext.extension_start_date + timedelta(days=90)
        ExtensionRecord.objects.filter(pk=ext.pk).update(extension_end_date=new_end)

    for task in MonitoringTask.objects.filter(
        task_type="month_1_inspection",
        status__in=pending_statuses,
    ).iterator():
        ext = (
            ExtensionRecord.objects.filter(lot_award_id=task.lot_award_id)
            .order_by("-extension_start_date")
            .first()
        )
        if not ext:
            continue
        new_due = ext.extension_start_date + timedelta(days=90)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=90,
        )

    for task in MonitoringTask.objects.filter(
        task_type="month_2_inspection",
        status__in=pending_statuses,
    ).iterator():
        ext = (
            ExtensionRecord.objects.filter(lot_award_id=task.lot_award_id)
            .order_by("-extension_start_date")
            .first()
        )
        if not ext:
            continue
        new_due = ext.extension_start_date + timedelta(days=30)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=30,
        )

    for cycle in OccupancyMonitoringCycle.objects.filter(
        cycle_stage="extension_month_1",
        is_active=True,
    ).iterator():
        OccupancyMonitoringCycle.objects.filter(pk=cycle.pk).update(
            stage_end_date=cycle.stage_start_date + timedelta(days=90),
            days_allowed=90,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0022_rename_day15_to_day60_inspection"),
    ]

    operations = [
        migrations.RunPython(reschedule_to_90_120, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="monitoringtask",
            name="days_from_award",
            field=models.PositiveIntegerField(
                help_text=(
                    "Monitoring day after the 30-day possession grace period when the visit is due "
                    "(90 for the first visit; 120 for the final visit)."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="monitoringtask",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("day_60_inspection", "90 Day Inspection"),
                    ("day_30_inspection", "120 Day Inspection"),
                    ("month_1_inspection", "Extension Month 1 — Inspection"),
                    ("month_2_inspection", "Extension Month 2 — Inspection"),
                    ("month_3_inspection", "Extension Month 3 — Inspection"),
                    ("final_inspection", "Final Inspection (Post-Notice)"),
                ],
                help_text="Type of monitoring task",
                max_length=30,
            ),
        ),
    ]
