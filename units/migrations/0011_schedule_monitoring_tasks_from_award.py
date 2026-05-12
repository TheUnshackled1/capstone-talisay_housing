from datetime import timedelta

from django.db import migrations


def reschedule_day_tasks(apps, schema_editor):
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
        if task.scheduled_date != target_date or task.due_date != target_date:
            task.scheduled_date = target_date
            task.due_date = target_date
            task.days_from_award = offset
            to_update.append(task)

    if to_update:
        MonitoringTask.objects.bulk_update(
            to_update,
            ["scheduled_date", "due_date", "days_from_award"],
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0010_explanationreview_extensionrecord_monitoringreport_and_more"),
    ]

    operations = [
        migrations.RunPython(reschedule_day_tasks, reverse_noop),
    ]
