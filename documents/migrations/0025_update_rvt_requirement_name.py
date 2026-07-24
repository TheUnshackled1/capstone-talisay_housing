# Rename RVT requirement name to Voter Certification in database.

from django.db import migrations


def rename_rvt(apps, schema_editor):
    Requirement = apps.get_model('documents', 'Requirement')
    Requirement.objects.filter(code='RVT').update(name='Voter Certification')


def revert_rvt(apps, schema_editor):
    Requirement = apps.get_model('documents', 'Requirement')
    Requirement.objects.filter(code='RVT').update(
        name='Voter Certification (COMELEC / Barangay voter record)'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0024_requirement_rvt_optional_for_form'),
    ]

    operations = [
        migrations.RunPython(rename_rvt, revert_rvt),
    ]
