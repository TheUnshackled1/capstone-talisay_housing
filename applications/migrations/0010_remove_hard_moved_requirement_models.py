from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0009_move_cdrrmo_and_field_photos_from_intake"),
        ("documents", "0004_hard_move_requirements_and_routing"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="RequirementSubmission"),
                migrations.DeleteModel(name="Requirement"),
                migrations.DeleteModel(name="SignatoryRouting"),
            ],
        ),
    ]
