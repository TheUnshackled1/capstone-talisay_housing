"""Rename legacy day_15_inspection task_type to day_60_inspection."""

from django.db import migrations, models


def rename_initial_inspection_task_type(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")
    MonitoringTask.objects.filter(task_type="day_15_inspection").update(
        task_type="day_60_inspection"
    )


def rename_initial_inspection_task_type_back(apps, schema_editor):
    MonitoringTask = apps.get_model("units", "MonitoringTask")
    MonitoringTask.objects.filter(task_type="day_60_inspection").update(
        task_type="day_15_inspection"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0021_alter_monitoringtask_days_from_award_and_more"),
    ]

    operations = [
        migrations.RunPython(
            rename_initial_inspection_task_type,
            rename_initial_inspection_task_type_back,
        ),
        migrations.AlterField(
            model_name="monitoringtask",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("day_60_inspection", "Day 60 Inspection"),
                    ("day_30_inspection", "Day 30 Inspection"),
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
