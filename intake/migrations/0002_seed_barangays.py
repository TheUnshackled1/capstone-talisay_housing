# Generated migration to seed Talisay City barangays
from django.db import migrations


# Official 27 Barangays of Talisay City, Negros Occidental
# Source: Official THA organizational data
TALISAY_BARANGAYS = [
    'Bubog',
    'Cabatangan',
    'Concepcion',
    'Dos Hermanas',
    'Efigenio Lizares',
    'Katilingban',
    'Matab-ang',
    'San Fernando',
    'Zone 1 (Pob.)',
    'Zone 2 (Pob.)',
    'Zone 3 (Pob.)',
    'Zone 4 (Pob.)',
    'Zone 4-A (Pob.)',
    'Zone 5 (Pob.)',
    'Zone 6 (Pob.)',
    'Zone 7 (Pob.)',
    'Zone 8 (Pob.)',
    'Zone 9 (Pob.)',
    'Zone 10 (Pob.)',
    'Zone 11 (Pob.)',
    'Zone 12 (Pob.)',
    'Zone 12-A (Pob.)',
    'Zone 14 (Pob.)',
    'Zone 14-A (Pob.)',
    'Zone 14-B (Pob.)',
    'Zone 15 (Pob.)',
    'Zone 16 (Pob.)',
]


def seed_barangays(apps, schema_editor):
    """Populate barangays table with Talisay City barangays."""
    Barangay = apps.get_model('intake', 'Barangay')
    
    for name in TALISAY_BARANGAYS:
        Barangay.objects.get_or_create(
            name=name,
            defaults={'is_active': True}
        )


def remove_barangays(apps, schema_editor):
    """Remove seeded barangays (for reverse migration)."""
    Barangay = apps.get_model('intake', 'Barangay')
    Barangay.objects.filter(name__in=TALISAY_BARANGAYS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_barangays, remove_barangays),
    ]
