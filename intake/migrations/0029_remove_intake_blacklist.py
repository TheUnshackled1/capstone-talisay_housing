# Removes intake-local Blacklist model and intake_blacklist table.
# Blacklist source of truth is units.Blacklist only.

from django.db import migrations, models


def merge_blacklisted_applicants(apps, schema_editor):
    Applicant = apps.get_model("intake", "Applicant")
    note = (
        "Applicant status was Blacklisted (legacy intake flag); "
        "consolidated to Disqualified when intake blacklist was removed. "
        "Use Units → Blacklist Entries for enforcement."
    )
    qs = Applicant.objects.filter(status="blacklisted")
    for a in qs.iterator():
        a.status = "disqualified"
        if not (getattr(a, "disqualification_reason", None) or "").strip():
            a.disqualification_reason = note
        a.save(update_fields=["status", "disqualification_reason", "updated_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("intake", "0028_merge_20260423_0106"),
    ]

    operations = [
        migrations.RunPython(merge_blacklisted_applicants, noop_reverse),
        migrations.AlterField(
            model_name="applicant",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending eligibility check"),
                    ("pending_cdrrmo", "Pending CDRRMO verification (hazard claim)"),
                    ("eligible", "Eligible - In Queue"),
                    ("disqualified", "Disqualified"),
                    ("requirements", "Submitting Requirements"),
                    ("application", "Application In Progress"),
                    ("standby", "Fully Approved - Standby"),
                    ("awarded", "Lot Awarded"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.DeleteModel(
            name="Blacklist",
        ),
    ]
