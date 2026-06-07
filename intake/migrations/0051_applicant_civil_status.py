from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0050_alter_householdmember_relationship'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant',
            name='civil_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('single', 'Single'),
                    ('married', 'Married'),
                    ('widowed', 'Widowed'),
                    ('divorced', 'Divorced'),
                    ('separated', 'Separated'),
                    ('common_law', 'Common-law'),
                ],
                default='',
                max_length=20,
                verbose_name='Civil Status',
            ),
        ),
    ]
