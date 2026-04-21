from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0023_alter_cdrrmocertification_certification_notes_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant',
            name='module2_handoff_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Timestamp when staff forwarded this intake record to Module 2.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='applicant',
            name='module2_handoff_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='module2_handed_off_applicants',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
