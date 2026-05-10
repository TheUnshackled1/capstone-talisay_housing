# Generated manually — unused Phase D model (no UI / writes).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0015_alter_document_document_type_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EndorsementRoutingStep",
        ),
    ]
