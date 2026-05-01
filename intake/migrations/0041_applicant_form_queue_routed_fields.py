from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0040_applicant_doc_voter_cert'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant',
            name='form_queue_routed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Timestamp when staff moved this record to the Ready for Form queue.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='applicant',
            name='form_queue_routed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='form_queue_routed_applicants',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

