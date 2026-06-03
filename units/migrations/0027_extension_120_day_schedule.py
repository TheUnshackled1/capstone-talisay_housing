"""Reschedule explanation-letter extension visits to 90 / 120 days from extension start."""

from datetime import timedelta

from django.db import migrations


def reschedule_extension_visits(apps, schema_editor):
    ExtensionRecord = apps.get_model("units", "ExtensionRecord")
    MonitoringTask = apps.get_model("units", "MonitoringTask")
    OccupancyMonitoringCycle = apps.get_model("units", "OccupancyMonitoringCycle")
    pending_statuses = ("pending", "overdue")

    for ext in ExtensionRecord.objects.filter(lot_award__status="active").iterator():
        start = ext.extension_start_date
        new_end = start + timedelta(days=120)
        ExtensionRecord.objects.filter(pk=ext.pk).update(extension_end_date=new_end)

        for task in MonitoringTask.objects.filter(
            lot_award_id=ext.lot_award_id,
            task_type="month_1_inspection",
            status__in=pending_statuses,
        ):
            new_due = start + timedelta(days=90)
            MonitoringTask.objects.filter(pk=task.pk).update(
                scheduled_date=new_due,
                due_date=new_due,
                days_from_award=90,
            )

        for task in MonitoringTask.objects.filter(
            lot_award_id=ext.lot_award_id,
            task_type="month_2_inspection",
            status__in=pending_statuses,
        ):
            new_due = start + timedelta(days=120)
            MonitoringTask.objects.filter(pk=task.pk).update(
                scheduled_date=new_due,
                due_date=new_due,
                days_from_award=120,
            )

    for cycle in OccupancyMonitoringCycle.objects.filter(
        cycle_stage="extension_month_1",
        is_active=True,
    ).iterator():
        OccupancyMonitoringCycle.objects.filter(pk=cycle.pk).update(
            stage_end_date=cycle.stage_start_date + timedelta(days=120),
            days_allowed=120,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0026_alter_occupancymonitoringcycle_cycle_stage"),
    ]

    operations = [
        migrations.RunPython(reschedule_extension_visits, migrations.RunPython.noop),
    ]
