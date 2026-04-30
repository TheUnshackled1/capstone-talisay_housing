from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0011_remove_head_signed_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EligibilityCheckDecision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("check_key", models.CharField(max_length=40)),
                ("status", models.CharField(choices=[("passed", "Passed"), ("failed", "Failed")], max_length=10)),
                ("failure_reason", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(auto_now=True)),
                ("applicant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="eligibility_check_decisions", to="intake.applicant")),
                ("reviewed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eligibility_check_decisions_reviewed", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["applicant", "check_key"],
            },
        ),
        migrations.AddConstraint(
            model_name="eligibilitycheckdecision",
            constraint=models.UniqueConstraint(fields=("applicant", "check_key"), name="unique_applicant_eligibility_check_decision"),
        ),
    ]
