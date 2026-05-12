from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("units", "0012_monitoring_grace_period_and_photo_evidence"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitoringtask",
            name="notified_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When staff notified the monitoring dashboard about this task",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="monitoringtask",
            name="notified_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Staff user who notified the monitoring dashboard",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notified_monitoring_tasks",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
