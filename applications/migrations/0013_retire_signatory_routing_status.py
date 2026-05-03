from django.db import migrations, models


def migrate_routing_to_completed(apps, schema_editor):
    Application = apps.get_model('applications', 'Application')
    Application.objects.filter(status='routing').update(status='completed')


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0012_eligibilitycheckdecision'),
    ]

    operations = [
        migrations.RunPython(migrate_routing_to_completed, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='application',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft - Form Generated'),
                    ('completed', 'Completed - Signed by Applicant'),
                    ('oic_signed', 'Signed by OIC - Fully Approved'),
                    ('standby', 'Fully Approved - On Standby'),
                    ('awarded', 'Lot Awarded'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
    ]
