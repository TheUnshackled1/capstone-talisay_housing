from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intake", "0036_alter_householdmember_relationship"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="displacement_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Not declared"),
                    ("danger_zone", "Danger Zone / Hazard Area"),
                    ("ejected", "Ejected from Previous Residence"),
                    (
                        "relocated",
                        "Relocated Due to Expansion or Project Development",
                    ),
                ],
                default="",
                help_text="Module 2 Layer 3 displacement classification.",
                max_length=20,
                verbose_name="Displacement Reason",
            ),
        ),
        migrations.AddField(
            model_name="applicant",
            name="ejection_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "— Select —"),
                    ("private_eviction", "Private land eviction"),
                    ("court_order", "Court order"),
                    ("landowner_recovery", "Landowner recovery"),
                    ("other", "Other"),
                ],
                default="",
                max_length=30,
                verbose_name="Ejection Type",
            ),
        ),
        migrations.AddField(
            model_name="applicant",
            name="ejection_date",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Ejection / Notice Date",
            ),
        ),
        migrations.AddField(
            model_name="applicant",
            name="project_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Project that triggered relocation "
                    "(road widening, drainage, government project, etc.)."
                ),
                max_length=255,
                verbose_name="Relocation Project Name",
            ),
        ),
    ]
