# Recreated — already applied in DB as cases.0013_module5_field_reports

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0001_initial'),
        ('units', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cases', '0012_case_field_settlement_outcome'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='monitored_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Ronda tagged by staff to observe this case on-site.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='monitored_cases',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='FieldReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('subject_name', models.CharField(blank=True, max_length=255)),
                ('complaint_type', models.CharField(max_length=20)),
                ('description', models.CharField(max_length=200)),
                ('what_was_tried', models.CharField(max_length=200)),
                ('photo', models.FileField(blank=True, upload_to='cases/reports/%Y/%m/')),
                ('is_urgent', models.BooleanField(default=False)),
                ('status', models.CharField(default='pending', max_length=32)),
                ('staff_remarks', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='source_field_reports',
                    to='cases.case',
                )),
                ('related_unit', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='field_reports',
                    to='units.housingunit',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='field_reports_reviewed',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('ronda', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='field_reports_submitted',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('subject_applicant', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='field_reports_as_subject',
                    to='intake.applicant',
                )),
            ],
            options={
                'verbose_name': 'Field report',
                'verbose_name_plural': 'Field reports',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='FieldSettledIncidentLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('subject_name', models.CharField(blank=True, max_length=255)),
                ('case_type', models.CharField(max_length=20)),
                ('description', models.CharField(max_length=150)),
                ('logged_at', models.DateTimeField(auto_now_add=True)),
                ('logged_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='settled_incident_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('related_unit', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='settled_incident_logs',
                    to='units.housingunit',
                )),
                ('subject_applicant', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='settled_incident_logs',
                    to='intake.applicant',
                )),
            ],
            options={
                'verbose_name': 'Settled incident log',
                'verbose_name_plural': 'Settled incident logs',
                'ordering': ['-logged_at'],
            },
        ),
        migrations.CreateModel(
            name='CaseFieldUpdate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('note', models.TextField()),
                ('photo', models.FileField(blank=True, upload_to='cases/field-updates/%Y/%m/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='field_updates',
                    to='cases.case',
                )),
                ('submitted_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='case_field_updates',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Case field update',
                'verbose_name_plural': 'Case field updates',
                'ordering': ['-created_at'],
            },
        ),
    ]
