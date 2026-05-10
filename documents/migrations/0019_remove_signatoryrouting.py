from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0018_remove_documents_smslog'),
    ]

    operations = [
        migrations.DeleteModel(name='SignatoryRouting'),
    ]
