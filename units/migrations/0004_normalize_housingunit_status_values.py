# Generated manually — normalizes legacy status strings after AlterField choice change.

from django.db import migrations


STATUS_MAP = {
    "vacant": "Vacant — available",
    "occupied": "Occupied",
    "notice_30": "Under notice (30-day)",
    "notice_10": "Final notice (10-day)",
    "repossessed": "Repossessed",
    "maintenance": "maintenance",
}


def forwards(apps, schema_editor):
    HousingUnit = apps.get_model("units", "HousingUnit")
    for old, new in STATUS_MAP.items():
        HousingUnit.objects.filter(status=old).update(status=new)


def backwards(apps, schema_editor):
    reverse_map = {v: k for k, v in STATUS_MAP.items()}
    HousingUnit = apps.get_model("units", "HousingUnit")
    for new, old in reverse_map.items():
        HousingUnit.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0003_caserecord_caseupdate"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
