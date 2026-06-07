# Voter certification (RVT) is optional for intake checklist and Module 2 baseline gate.

from django.db import migrations


def rvt_optional_for_form(apps, schema_editor):
    Requirement = apps.get_model('documents', 'Requirement')
    Requirement.objects.filter(code='RVT').update(is_required_for_form=False)


def rvt_required_for_form(apps, schema_editor):
    Requirement = apps.get_model('documents', 'Requirement')
    Requirement.objects.filter(code='RVT').update(is_required_for_form=True)


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0023_alter_document_document_type_and_more'),
    ]

    operations = [
        migrations.RunPython(rvt_optional_for_form, rvt_required_for_form),
    ]
