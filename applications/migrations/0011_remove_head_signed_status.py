from django.db import migrations, models


def migrate_head_signed_to_legacy_full_approval(apps, schema_editor):
    """Convert any existing head_signed applications to the legacy full-approval status."""
    Application = apps.get_model('applications', 'Application')
    Application.objects.filter(status='head_signed').update(status='legacy_full_approval')


def reverse_noop(apps, schema_editor):
    """No-op reverse: head_signed is no longer a valid choice."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0010_remove_hard_moved_requirement_models'),
    ]

    operations = [
        migrations.RunPython(migrate_head_signed_to_legacy_full_approval, reverse_noop),
        migrations.AlterField(
            model_name='application',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft - Form Generated'),
                    ('completed', 'Completed - Signed by Applicant'),
                    ('routing', 'Under Signatory Routing'),
                    ('legacy_full_approval', 'Fully approved - legacy status'),
                    ('standby', 'Fully Approved - On Standby'),
                    ('awarded', 'Lot Awarded'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
    ]
