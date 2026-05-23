from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0011_case_field_intake_reviewed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='field_settlement_outcome',
            field=models.CharField(
                blank=True,
                choices=[('settled', 'Settled'), ('not_settled', 'Not settled')],
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='case',
            name='field_settlement_saved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
