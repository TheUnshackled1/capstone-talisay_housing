from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0010_case_year_sequence'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='field_intake_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
