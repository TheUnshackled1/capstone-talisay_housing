"""Permanently remove legacy retired staff user accounts."""

from django.db import migrations

REMOVED_LEGACY_USERNAMES = ('victor.fregil',)


def delete_legacy_staff_users(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(username__in=REMOVED_LEGACY_USERNAMES).delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_remove_retired_staff_position'),
    ]

    operations = [
        migrations.RunPython(delete_legacy_staff_users, noop),
    ]
