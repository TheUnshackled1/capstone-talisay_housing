# Generated manually for checklist parity with Requirement RVT.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intake", "0039_alter_applicant_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="doc_voter_cert",
            field=models.BooleanField(
                default=False,
                verbose_name="Voter Certification",
            ),
        ),
        migrations.AlterField(
            model_name="applicant",
            name="document_deadline",
            field=models.DateTimeField(
                blank=True,
                help_text="Deadline by which all baseline required documents must be submitted",
                null=True,
                verbose_name="Document Submission Deadline",
            ),
        ),
        migrations.AlterField(
            model_name="applicant",
            name="documents_submitted_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When all baseline required documents were completed",
                null=True,
                verbose_name="Documents Completed Date",
            ),
        ),
    ]
