from django.db import migrations, models


def migrate_head_routing_steps(apps, schema_editor):
    """
    Convert any existing forwarded_head/signed_head routing rows to signed_oic
    so the new STEP_CHOICES (received → forwarded_oic → signed_oic) remains valid.
    """
    SignatoryRouting = apps.get_model('documents', 'SignatoryRouting')
    SignatoryRouting.objects.filter(
        step__in=['forwarded_head', 'signed_head']
    ).update(step='signed_oic')


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
                    ('forwarded_oic', 'Forwarded to OIC'),
                    ('signed_oic', 'Signed by OIC - Complete'),
                ],
                max_length=20,
            ),
        ),
    ]
