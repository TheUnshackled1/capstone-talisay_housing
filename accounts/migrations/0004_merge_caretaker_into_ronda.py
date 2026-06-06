from django.db import migrations, models


def merge_caretaker_to_ronda(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(position="caretaker").update(position="ronda")


def reverse_merge(apps, schema_editor):
    """Cannot restore which users were caretaker vs ronda before merge."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_position"),
    ]

    operations = [
        migrations.RunPython(merge_caretaker_to_ronda, reverse_merge),
        migrations.AlterField(
            model_name="user",
            name="position",
            field=models.CharField(
                blank=True,
                choices=[
                    ("second_member", "Second Member"),
                    ("fourth_member", "Fourth Member"),
                    ("ronda", "Ronda (Field Personnel)"),
                    ("field", "Field Personnel"),
                ],
                help_text="Staff position in THA organizational structure",
                max_length=50,
            ),
        ),
    ]
