from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0009_move_cdrrmo_and_field_photos_from_intake"),
        ("documents", "0003_electricityconnection_lotawarding_facilitatedservice"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("intake", "0029_remove_intake_blacklist"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Requirement",
                    fields=[
                        ("code", models.CharField(max_length=10, primary_key=True, serialize=False, unique=True)),
                        ("name", models.CharField(max_length=100)),
                        ("description", models.TextField(blank=True)),
                        ("group", models.CharField(choices=[("A", "Group A - Applicant Requirements"), ("B", "Group B - Office-Generated"), ("C", "Group C - Post-Award")], default="A", max_length=1)),
                        ("order", models.PositiveSmallIntegerField(default=0)),
                        ("is_required_for_form", models.BooleanField(default=True, help_text="If True, this must be complete before application form is generated")),
                        ("is_active", models.BooleanField(default=True)),
                    ],
                    options={
                        "verbose_name": "Requirement",
                        "verbose_name_plural": "Requirements",
                        "ordering": ["group", "order"],
                        "db_table": "applications_requirement",
                    },
                ),
                migrations.CreateModel(
                    name="RequirementSubmission",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("status", models.CharField(choices=[("pending", "Pending"), ("submitted", "Submitted"), ("verified", "Verified"), ("rejected", "Rejected - Resubmit Required")], default="pending", max_length=20)),
                        ("rejection_reason", models.TextField(blank=True)),
                        ("submitted_at", models.DateTimeField(blank=True, null=True)),
                        ("verified_at", models.DateTimeField(blank=True, null=True)),
                        ("notes", models.TextField(blank=True)),
                        ("applicant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirement_submissions", to="intake.applicant")),
                        ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submissions", to="documents.requirement")),
                        ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="verified_requirements", to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        "verbose_name": "Requirement Submission",
                        "verbose_name_plural": "Requirement Submissions",
                        "ordering": ["applicant", "requirement__order"],
                        "db_table": "applications_requirementsubmission",
                    },
                ),
                migrations.AddConstraint(
                    model_name="requirementsubmission",
                    constraint=models.UniqueConstraint(fields=("applicant", "requirement"), name="unique_applicant_requirement"),
                ),
                migrations.CreateModel(
                    name="SignatoryRouting",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("step", models.CharField(choices=[("received", "Received - Processing"), ("forwarded_oic", "Forwarded to OIC"), ("signed_oic", "Signed by OIC"), ("forwarded_head", "Forwarded to Head"), ("signed_head", "Signed by Head - Complete")], max_length=20)),
                        ("action_at", models.DateTimeField(auto_now_add=True)),
                        ("notes", models.TextField(blank=True)),
                        ("action_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="routing_actions", to=settings.AUTH_USER_MODEL)),
                        ("application", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="routing_steps", to="applications.application")),
                    ],
                    options={
                        "verbose_name": "Signatory Routing Step",
                        "verbose_name_plural": "Signatory Routing Steps",
                        "ordering": ["application", "action_at"],
                        "db_table": "applications_signatoryrouting",
                    },
                ),
                migrations.AlterField(
                    model_name="document",
                    name="requirement_submission",
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documents", to="documents.requirementsubmission"),
                ),
            ],
        ),
    ]
