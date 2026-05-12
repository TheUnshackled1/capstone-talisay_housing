from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("units", "0013_monitoringtask_notification_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitoringreport",
            name="progress_assessment",
            field=models.CharField(
                blank=True,
                choices=[
                    ("normal_progress", "Normal Progress"),
                    ("no_progress", "No Progress"),
                ],
                help_text="Staff review decision after checking caretaker monitoring report",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="monitoringreport",
            name="assessed_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Staff user who reviewed the monitoring report",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="monitoring_reports_assessed",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="monitoringreport",
            name="assessed_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When staff reviewed the monitoring report",
                null=True,
            ),
        ),
    ]
