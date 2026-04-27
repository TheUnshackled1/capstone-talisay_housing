from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intake", "0034_add_name_components_to_archive"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="is_registered_voter_talisay",
            field=models.BooleanField(
                default=False,
                help_text="Declared voter registration status in Talisay City.",
                verbose_name="Registered Voter in Talisay City",
            ),
        ),
    ]
