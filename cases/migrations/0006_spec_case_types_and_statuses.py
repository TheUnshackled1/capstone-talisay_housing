from django.db import migrations, models


TYPE_MAP = {
    'boundary': 'lot_boundary',
    'interpersonal': 'community_quarrel',
    'illegal_transfer': 'illegal_occupant',
    'unauthorized': 'illegal_occupant',
    'structural': 'occupancy_dispute',
    'damage': 'other',
}


def remap_types(apps, schema_editor):
    Case = apps.get_model('cases', 'Case')
    for case in Case.objects.all():
        new_type = TYPE_MAP.get(case.case_type, case.case_type)
        if new_type != case.case_type:
            case.case_type = new_type
            case.save(update_fields=['case_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0005_workflow_seven_steps'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='case_type',
            field=models.CharField(
                choices=[
                    ('lot_boundary', 'Lot Boundary Issue'),
                    ('noise', 'Noise Complaint'),
                    ('drunk_disturbance', 'Drunk Disturbance'),
                    ('community_quarrel', 'Community Quarrel'),
                    ('illegal_occupant', 'Illegal Occupant Concern'),
                    ('occupancy_dispute', 'Occupancy Dispute'),
                    ('sanitation', 'Sanitation Complaint'),
                    ('other', 'Other Community Concern'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='case',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_review', 'Pending Review'),
                    ('under_review', 'Under Review'),
                    ('mediation_monitoring', 'Under Mediation / Monitoring'),
                    ('awaiting_response', 'Awaiting Response'),
                    ('referred_engineering', 'Awaiting Engineering Findings'),
                    ('resolved', 'Resolved'),
                    ('closed', 'Closed'),
                ],
                default='pending_review',
                max_length=24,
            ),
        ),
        migrations.RunPython(remap_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='caseaction',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('refer_engineering', 'Refer to City Engineering'),
                    ('issue_warning', 'Issue warning'),
                    ('schedule_mediation', 'Schedule mediation'),
                    ('monitor_complaint', 'Monitor complaint'),
                    ('record_incident', 'Record incident'),
                    ('record_resolution', 'Record resolution'),
                    ('review_occupancy', 'Review occupancy'),
                    ('request_clarification', 'Request clarification'),
                    ('monitor_case', 'Monitor case'),
                    ('issue_reminder', 'Issue reminder'),
                    ('monitor_compliance', 'Monitor compliance'),
                    ('schedule_inspection', 'Schedule lot survey'),
                    ('verbal_warning', 'Verbal warning issued'),
                    ('written_warning', 'Written warning issued'),
                    ('mediation_held', 'Mediation conducted'),
                    ('notice_issued', 'Notice issued'),
                    ('follow_up', 'Follow-up logged'),
                    ('other', 'Other action recorded'),
                ],
                max_length=32,
            ),
        ),
    ]
