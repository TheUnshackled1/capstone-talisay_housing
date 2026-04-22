# Generated migration to move QueueEntry from intake to applications

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0025_householdmember_contact_number'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='queueentry',
            name='unique_active_queue_position',
        ),
        migrations.DeleteModel(
            name='QueueEntry',
        ),
    ]
