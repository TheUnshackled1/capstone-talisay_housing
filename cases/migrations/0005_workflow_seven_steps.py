# Generated manually for 7-step workflow

import uuid

from django.conf import settings
from django.db import migrations, models


def remap_legacy_statuses(apps, schema_editor):
    Case = apps.get_model('cases', 'Case')
    mapping = {
        'open': 'pending_review',
        'investigation': 'under_review',
        'pending_decision': 'mediation_monitoring',
        'resolved': 'resolved',
        'closed': 'closed',
    }
    for case in Case.objects.all():
        old = case.status
        if old == 'referred':
            if case.case_type == 'boundary':
                case.status = 'referred_engineering'
            else:
                case.status = 'mediation_monitoring'
                if not case.referred_to:
                    case.referred_to = 'External office'
        elif old in mapping:
            case.status = mapping[old]
        case.save(update_fields=['status', 'referred_to'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0004_case_evidence'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='closure_outcome',
            field=models.CharField(
                blank=True,
                help_text='Short outcome summary when case is closed',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='case',
            name='follow_up_at',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='case',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_review', 'Pending Review'),
                    ('under_review', 'Under Review'),
                    ('mediation_monitoring', 'Under Mediation / Monitoring'),
                    ('referred_engineering', 'Referred to Engineering'),
                    ('resolved', 'Resolved'),
                    ('closed', 'Closed'),
                ],
                default='pending_review',
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name='case',
            name='case_type',
            field=models.CharField(
                choices=[
                    ('boundary', 'Lot Boundary Dispute'),
                    ('structural', 'Structural Issue'),
                    ('interpersonal', 'Interpersonal Conflict'),
                    ('illegal_transfer', 'Illegal Transfer'),
                    ('unauthorized', 'Unauthorized Occupant'),
                    ('damage', 'Property Damage'),
                    ('noise', 'Noise / Disturbance'),
                    ('sanitation', 'Sanitation'),
                    ('other', 'Other'),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(remap_legacy_statuses, noop_reverse),
        migrations.CreateModel(
            name='CaseAction',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'action_type',
                    models.CharField(
                        choices=[
                            ('verbal_warning', 'Verbal warning issued'),
                            ('written_warning', 'Written warning issued'),
                            ('schedule_mediation', 'Mediation scheduled'),
                            ('mediation_held', 'Mediation conducted'),
                            ('refer_engineering', 'Referred to City Engineering'),
                            ('schedule_inspection', 'Inspection / survey scheduled'),
                            ('notice_issued', 'Notice issued'),
                            ('follow_up', 'Follow-up logged'),
                            ('other', 'Other action recorded'),
                        ],
                        max_length=32,
                    ),
                ),
                ('details', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'case',
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name='actions',
                        to='cases.case',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='case_actions_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Case action',
                'verbose_name_plural': 'Case actions',
                'ordering': ['-created_at'],
            },
        ),
    ]
