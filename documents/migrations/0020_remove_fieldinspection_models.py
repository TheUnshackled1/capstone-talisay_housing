from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0019_remove_signatoryrouting'),
    ]

    operations = [
        migrations.DeleteModel(name='FieldInspectionPhoto'),
        migrations.DeleteModel(name='FieldInspection'),
    ]
