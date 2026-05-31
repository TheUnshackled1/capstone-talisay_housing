"""Reschedule pending final visits to 120 calendar days after the 90 Day due date."""

from datetime import timedelta

from django.db import migrations, models


def _monitoring_start(award_date):
    return award_date + timedelta(days=30)


def reschedule_final_after_initial(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")
    pending_statuses = ("pending", "overdue")

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
        initial_due = _monitoring_start(award_date) + timedelta(days=90)
        new_due = initial_due + timedelta(days=120)
        MonitoringTask.objects.filter(pk=task.pk).update(
            scheduled_date=new_due,
            due_date=new_due,
            days_from_award=210,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0023_monitoring_90_120_schedule"),
    ]

    operations = [
        migrations.RunPython(reschedule_final_after_initial, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="monitoringtask",
            name="days_from_award",
            field=models.PositiveIntegerField(
                help_text=(
                    "Monitoring day after the 30-day possession grace period when the visit is due "
                    "(90 for the first visit; 210 for the final visit, i.e. 120 calendar days after the 90 Day due date)."
                ),
            ),
        ),
    ]
