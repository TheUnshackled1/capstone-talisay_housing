from django.db import migrations, models


def clear_head_position(apps, schema_editor):
    """Clear position field on any users still holding the removed 'head' role."""
    User = apps.get_model('accounts', 'User')
    User.objects.filter(position='head').update(position='')


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_position"),
    ]

    operations = [
        migrations.RunPython(clear_head_position, reverse_noop),
        migrations.AlterField(
            model_name="user",
            name="position",
            field=models.CharField(
                blank=True,
                choices=[
                    ("second_member", "Second Member"),
                    ("fourth_member", "Fourth Member"),
                    ("caretaker", "Caretaker"),
                    ("ronda", "Ronda (Field Personnel)"),
                    ("field", "Field Personnel"),
                ],
                help_text="Staff position in THA organizational structure",
                max_length=50,
            ),
        ),
    ]
