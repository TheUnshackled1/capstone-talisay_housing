from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0029_remove_intake_blacklist'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant',
            name='evaluation_approval_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='applicant',
            name='evaluation_approval_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluation_approved_applicants', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='applicant',
            name='evaluation_approval_notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='applicant',
            name='evaluation_approval_status',
            field=models.CharField(blank=True, choices=[('', 'Not Recorded'), ('approved', 'Approved'), ('for_review', 'For Review')], default='', help_text='Module 2 step 2.8 approval/review marker only.', max_length=20),
        ),
    ]

