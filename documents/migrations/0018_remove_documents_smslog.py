# Unused table — Module 2 SMS logs to applications.SMSLog only.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0017_remove_committeeinterview"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SMSLog",
        ),
    ]
