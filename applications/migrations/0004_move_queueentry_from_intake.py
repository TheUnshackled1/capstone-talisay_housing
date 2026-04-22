# Generated migration to add QueueEntry to applications

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0003_alter_signatoryrouting_step'),
        ('intake', '0026_remove_queueentry'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QueueEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('queue_type', models.CharField(choices=[('priority', 'Priority Queue - Danger Zone')], max_length=20)),
                ('position', models.PositiveIntegerField(help_text='Position number in the queue (FIFO order)', verbose_name='Queue Position')),
                ('status', models.CharField(choices=[('active', 'Active - Waiting'), ('notified', 'Notified for Requirements'), ('processing', 'Processing Application'), ('completed', 'Completed - Moved to Application'), ('removed', 'Removed from Queue')], default='active', max_length=20)),
                ('entered_at', models.DateTimeField(auto_now_add=True)),
                ('notified_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('added_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='queue_entries_added', to=settings.AUTH_USER_MODEL)),
                ('applicant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='queue_entries', to='intake.applicant')),
            ],
            options={
                'verbose_name': 'Queue Entry',
                'verbose_name_plural': 'Queue Entries',
                'ordering': ['queue_type', 'position'],
            },
        ),
        migrations.AddConstraint(
            model_name='queueentry',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'active')), fields=('queue_type', 'position'), name='unique_active_queue_position'),
        ),
    ]
