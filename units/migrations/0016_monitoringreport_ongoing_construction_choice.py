from django.db import migrations, models


def normalize_ongoing_construction(apps, schema_editor):
    MonitoringReport = apps.get_model("units", "MonitoringReport")
    MonitoringReport.objects.filter(construction_status="ongoing").update(
        construction_status="ongoing_construction"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0015_monitoringreportphoto"),
    ]

    operations = [
        migrations.AlterField(
            model_name="monitoringreport",
            name="construction_status",
            field=models.CharField(
                choices=[
                    ("no_structure", "No Structure"),
                    ("ongoing_construction", "Ongoing Construction"),
                    ("site_clearing", "Site Clearing"),
                    ("foundation", "Foundation"),
                    ("wall_framing", "Wall Framing"),
                    ("roofing", "Roofing"),
                    ("finishing", "Finishing"),
                    ("completed_occupied", "Completed / Occupied"),
                ],
                help_text="Current construction stage",
                max_length=30,
            ),
        ),
        migrations.RunPython(normalize_ongoing_construction, migrations.RunPython.noop),
    ]
