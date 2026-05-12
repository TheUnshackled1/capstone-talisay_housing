import uuid

from django.db import migrations, models
import django.db.models.deletion


def backfill_primary_report_photos(apps, schema_editor):
    MonitoringReportPhoto = apps.get_model("units", "MonitoringReportPhoto")
    MonitoringReport = apps.get_model("units", "MonitoringReport")

    photos = []
    for report in MonitoringReport.objects.exclude(photo_evidence=""):
        photos.append(
            MonitoringReportPhoto(
                report_id=report.id,
                image=report.photo_evidence,
            )
        )

    if photos:
        MonitoringReportPhoto.objects.bulk_create(photos)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0014_monitoringreport_progress_assessment"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitoringReportPhoto",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "image",
                    models.FileField(
                        help_text="Field photo evidence captured during inspection",
                        upload_to="monitoring_evidence/%Y/%m/",
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="units.monitoringreport",
                    ),
                ),
            ],
            options={
                "verbose_name": "Monitoring Report Photo",
                "verbose_name_plural": "Monitoring Report Photos",
                "ordering": ["uploaded_at", "id"],
            },
        ),
        migrations.RunPython(backfill_primary_report_photos, reverse_noop),
    ]
