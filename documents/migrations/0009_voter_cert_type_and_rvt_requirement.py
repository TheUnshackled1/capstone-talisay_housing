# Generated manually for voter certification vault type + Requirement RVT.

from django.db import migrations, models


DOC_CHOICES = [
    ("barangay_residency", "Barangay Certificate of Residency"),
    ("barangay_indigency", "Barangay Certificate of Indigency"),
    ("cedula", "Cedula (Community Tax Certificate)"),
    ("police_clearance", "Police Clearance"),
    ("no_property", "Certificate of No Property"),
    ("photo_2x2", "2x2 Picture"),
    ("house_sketch", "Sketch of House Location"),
    (
        "voter_certification",
        "Voter Certification (COMELEC / Barangay voter record)",
    ),
    (
        "isf_situational_docs",
        "ISF situational documentation (Applicant Situation Options A/B/C)",
    ),
    ("application_form", "Application Form"),
    ("notarized_docs", "Notarized Documents"),
    ("engineering_assessment", "Engineering Assessment"),
    ("signed_application", "Signed Application (Head-Approved)"),
    ("lot_award", "Lot Award Document"),
    ("electricity_app", "Electricity Connection Application"),
    ("cdrrmo_cert", "CDRRMO Certification"),
    ("explanation_letter", "Explanation Letter"),
    ("other", "Other Document"),
]


def ensure_rvt_requirement(apps, schema_editor):
    Requirement = apps.get_model("documents", "Requirement")
    Requirement.objects.update_or_create(
        code="RVT",
        defaults={
            "name": "Voter Certification (COMELEC / Barangay voter record)",
            "description": "",
            "group": "A",
            "order": 99,
            "vault_document_type": "voter_certification",
            "is_required_for_form": True,
            "is_active": True,
        },
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0008_document_isf_vault_choice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="document_type",
            field=models.CharField(
                choices=DOC_CHOICES,
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="requirement",
            name="vault_document_type",
            field=models.CharField(
                blank=True,
                choices=DOC_CHOICES,
                default="",
                help_text="Links this row to vault uploads: a scan exists when Applicant has a Document with this type.",
                max_length=30,
            ),
        ),
        migrations.RunPython(ensure_rvt_requirement, noop_reverse),
    ]
