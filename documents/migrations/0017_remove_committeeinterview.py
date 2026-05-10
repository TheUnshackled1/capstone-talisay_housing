# Unused in staff UI — only gated module3_ready_for_module4 in document_management context.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0016_remove_endorsementroutingstep"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CommitteeInterview",
        ),
    ]
