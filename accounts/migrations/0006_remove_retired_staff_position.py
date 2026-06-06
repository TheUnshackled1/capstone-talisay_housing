"""Remove retired staff position and clear legacy user records."""

from django.db import migrations, models

LEGACY_RETIRED_USERNAMES = ('victor.fregil',)


def deactivate_retired_staff_users(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(username__in=LEGACY_RETIRED_USERNAMES).update(
        is_active=False,
        position='',
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_remove_fifth_member_role'),
    ]

    operations = [
        migrations.RunPython(deactivate_retired_staff_users, noop),
        migrations.AlterField(
            model_name='user',
            name='position',
            field=models.CharField(
                blank=True,
                choices=[
                    ('second_member', 'Second Member'),
                    ('fourth_member', 'Fourth Member'),
                    ('ronda', 'Ronda (Field Personnel)'),
                    ('field', 'Field Personnel'),
                ],
                help_text='Staff position in THA organizational structure',
                max_length=50,
            ),
        ),
    ]
