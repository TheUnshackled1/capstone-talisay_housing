from datetime import timedelta

from django.db import migrations, models


GRACE_PERIOD_DAYS = 30


def reschedule_tasks_after_grace_period(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")

    task_offsets = {
        "day_15_inspection": 15,
        "day_30_inspection": 30,
    }

    tasks = (
        MonitoringTask.objects
        .filter(task_type__in=task_offsets.keys(), lot_award__awarded_at__isnull=False)
        .select_related("lot_award")
    )

    to_update = []
    for task in tasks:
        monitoring_day = task_offsets[task.task_type]
        award_date = task.lot_award.awarded_at.date()
        target_date = award_date + timedelta(days=GRACE_PERIOD_DAYS + monitoring_day)
        if (
            task.scheduled_date != target_date
            or task.due_date != target_date
            or task.days_from_award != monitoring_day
        ):
            task.scheduled_date = target_date
            task.due_date = target_date
            task.days_from_award = monitoring_day
            to_update.append(task)

    if to_update:
        MonitoringTask.objects.bulk_update(
            to_update,
            ["scheduled_date", "due_date", "days_from_award"],
        )


def reverse_tasks_to_award_date_offsets(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")

    task_offsets = {
        "day_15_inspection": 15,
        "day_30_inspection": 30,
    }

    tasks = (
        MonitoringTask.objects
        .filter(task_type__in=task_offsets.keys(), lot_award__awarded_at__isnull=False)
        .select_related("lot_award")
    )

    to_update = []
    for task in tasks:
        offset = task_offsets[task.task_type]
        award_date = task.lot_award.awarded_at.date()
        target_date = award_date + timedelta(days=offset)
        task.scheduled_date = target_date
        task.due_date = target_date
        task.days_from_award = offset
        to_update.append(task)

    if to_update:
        MonitoringTask.objects.bulk_update(
            to_update,
            ["scheduled_date", "due_date", "days_from_award"],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0011_schedule_monitoring_tasks_from_award"),
    ]

    operations = [
        migrations.AlterField(
            model_name="monitoringtask",
            name="days_from_award",
            field=models.PositiveIntegerField(
                help_text="Monitoring day after the 30-day possession grace period",
            ),
        ),
        migrations.AddField(
            model_name="monitoringreport",
            name="photo_evidence",
            field=models.FileField(
                blank=True,
                help_text="Field photo evidence captured during inspection",
                upload_to="monitoring_evidence/%Y/%m/",
            ),
        ),
        migrations.RunPython(
            reschedule_tasks_after_grace_period,
            reverse_tasks_to_award_date_offsets,
        ),
    ]
