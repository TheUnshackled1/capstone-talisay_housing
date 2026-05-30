# Generated manually for data migration

from django.db import migrations

def migrate_relationships(apps, schema_editor):
    """
    Migrate old relationship values to new ones:
    - 'child' + sex='F' → 'daughter'
    - 'child' + sex='M' → 'son'
    - 'child' + no sex → 'other'
    - 'parent' + sex='F' → 'mother'
    - 'parent' + sex='M' → 'father'
    - 'parent' + no sex → 'other'
    - 'sibling' → 'other' (no brother/sister option)
    """
    HouseholdMember = apps.get_model('intake', 'HouseholdMember')

    # Migrate 'child'
    HouseholdMember.objects.filter(relationship='child', sex='F').update(relationship='daughter')
    HouseholdMember.objects.filter(relationship='child', sex='M').update(relationship='son')
    HouseholdMember.objects.filter(relationship='child', sex='').update(relationship='other')

    # Migrate 'parent'
    HouseholdMember.objects.filter(relationship='parent', sex='F').update(relationship='mother')
    HouseholdMember.objects.filter(relationship='parent', sex='M').update(relationship='father')
    HouseholdMember.objects.filter(relationship='parent', sex='').update(relationship='other')

    # Migrate 'sibling'
    HouseholdMember.objects.filter(relationship='sibling').update(relationship='other')

def reverse_migrate(apps, schema_editor):
    """Reverse migration - restore old values (limited reverse capability)"""
    # We can't reliably reverse this, so we'll just restore to 'other'
    HouseholdMember = apps.get_model('intake', 'HouseholdMember')
    HouseholdMember.objects.filter(relationship__in=['son', 'daughter', 'mother', 'father']).update(relationship='other')

class Migration(migrations.Migration):

    dependencies = [
        ("intake", "0048_update_relationship_choices"),
    ]

    operations = [
        migrations.RunPython(migrate_relationships, reverse_migrate),
    ]
