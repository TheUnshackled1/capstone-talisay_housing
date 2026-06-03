"""Cancel pending Extension 90 Day (month_1_inspection) tasks — extension workflow uses 120 Day only."""

from django.db import migrations


def cancel_extension_midpoint_tasks(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")
    ExtensionRecord = apps.get_model("units", "ExtensionRecord")

    lot_award_ids = (
        ExtensionRecord.objects.filter(explanation_review__isnull=False)
        .values_list("lot_award_id", flat=True)
        .distinct()
    )
    MonitoringTask.objects.filter(
        lot_award_id__in=lot_award_ids,
        task_type="month_1_inspection",
        status__in=("pending", "overdue"),
    ).update(status="cancelled")


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0027_extension_120_day_schedule"),
    ]

    operations = [
        migrations.RunPython(cancel_extension_midpoint_tasks, migrations.RunPython.noop),
    ]
