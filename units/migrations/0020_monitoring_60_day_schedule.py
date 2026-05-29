"""Reschedule monitoring tasks to 60-day initial visit and 60-day extension window."""

from datetime import timedelta

from django.db import migrations


def _monitoring_start(award_date):
    return award_date + timedelta(days=30)


def reschedule_monitoring_tasks(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")
    ExtensionRecord = apps.get_model("units", "ExtensionRecord")
    OccupancyMonitoringCycle = apps.get_model("units", "OccupancyMonitoringCycle")

    for task in (
        MonitoringTask.objects.filter(task_type="day_15_inspection")
        .select_related("lot_award")
        .iterator()
    ):
        awarded_at = getattr(task.lot_award, "awarded_at", None)
        if not awarded_at:
            continue
        award_date = awarded_at.date()
        new_due = _monitoring_start(award_date) + timedelta(days=60)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=60,
        )

    for task in (
        MonitoringTask.objects.filter(task_type="day_30_inspection")
        .select_related("lot_award")
        .iterator()
    ):
        awarded_at = getattr(task.lot_award, "awarded_at", None)
        if not awarded_at:
            continue
        award_date = awarded_at.date()
        initial_due = _monitoring_start(award_date) + timedelta(days=60)
        new_due = initial_due + timedelta(days=30)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=90,
        )

    for ext in ExtensionRecord.objects.all().iterator():
        new_end = ext.extension_start_date + timedelta(days=60)
        ExtensionRecord.objects.filter(pk=ext.pk).update(extension_end_date=new_end)

    for task in MonitoringTask.objects.filter(task_type="month_1_inspection").iterator():
        ext = (
            ExtensionRecord.objects.filter(lot_award_id=task.lot_award_id)
            .order_by("-extension_start_date")
            .first()
        )
        if not ext:
            continue
        new_due = ext.extension_start_date + timedelta(days=60)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=60,
        )

    for cycle in OccupancyMonitoringCycle.objects.filter(
        cycle_stage="extension_month_1",
        is_active=True,
    ).iterator():
        OccupancyMonitoringCycle.objects.filter(pk=cycle.pk).update(
            stage_end_date=cycle.stage_start_date + timedelta(days=60),
            days_allowed=60,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0019_alter_housingunit_block_number_and_more"),
    ]

    operations = [
        migrations.RunPython(reschedule_monitoring_tasks, migrations.RunPython.noop),
    ]
