from django.db import migrations


def rename_rvt(apps, schema_editor):
    Requirement = apps.get_model('documents', 'Requirement')
    Requirement.objects.filter(code='RVT').update(name="Voter's Certificate")


def revert_rvt(apps, schema_editor):
    Requirement = apps.get_model('documents', 'Requirement')
    Requirement.objects.filter(code='RVT').update(
        name='Voter Certification'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0027_alter_document_document_type_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_rvt, revert_rvt),
    ]
