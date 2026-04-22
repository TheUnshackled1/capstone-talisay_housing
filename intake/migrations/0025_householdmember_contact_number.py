from django.db import migrations, models
import intake.models


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0024_applicant_module2_handoff'),
    ]

    operations = [
        migrations.AddField(
            model_name='householdmember',
            name='contact_number',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Optional household member mobile number (09XXXXXXXXXX).',
                max_length=20,
                validators=[intake.models.validate_philippine_phone],
                verbose_name='Contact Number',
            ),
        ),
    ]
