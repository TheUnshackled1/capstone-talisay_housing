# Blacklist (Module 2 view) removed — Module 2 uses units.Blacklist only.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0006_smslog"),
    ]

    operations = [
        migrations.DeleteModel(
            name="BlacklistProxy",
        ),
    ]
