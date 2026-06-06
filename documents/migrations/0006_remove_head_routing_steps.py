from django.db import migrations, models


def migrate_head_routing_steps(apps, schema_editor):
    """
    Convert any existing forwarded_head/signed_head routing rows to signed_final
    so the new step choices (received → forwarded_final → signed_final) remain valid.
    """
    SignatoryRouting = apps.get_model('documents', 'SignatoryRouting')
    SignatoryRouting.objects.filter(
        step__in=['forwarded_head', 'signed_head']
    ).update(step='signed_final')


def reverse_noop(apps, schema_editor):
    """No-op reverse: forwarded_head and signed_head are no longer valid choices."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0005_committeeinterview_fieldinspection_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_head_routing_steps, reverse_noop),
        migrations.AlterField(
            model_name='signatoryrouting',
            name='step',
            field=models.CharField(
                choices=[
                    ('received', 'Received - Processing'),
                    ('forwarded_final', 'Forwarded for final sign-off'),
                    ('signed_final', 'Final signature complete'),
                ],
                max_length=20,
            ),
        ),
    ]
