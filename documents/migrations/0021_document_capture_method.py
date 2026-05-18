from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0020_remove_fieldinspection_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='capture_method',
            field=models.CharField(
                blank=True,
                choices=[('', 'Not recorded'), ('upload', 'Uploaded'), ('scan', 'Scanned')],
                default='',
                help_text='How this file entered the vault (staff Upload vs TWAIN Scan).',
                max_length=10,
            ),
        ),
    ]
