from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0025_householdmember_contact_number'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HazardDeclarationAudit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('declared_before', models.BooleanField(blank=True, null=True)),
                ('declared_after', models.BooleanField()),
                ('danger_zone_type_before', models.CharField(blank=True, default='', max_length=50)),
                ('danger_zone_type_after', models.CharField(blank=True, default='', max_length=50)),
                ('danger_zone_location_before', models.CharField(blank=True, default='', max_length=255)),
                ('danger_zone_location_after', models.CharField(blank=True, default='', max_length=255)),
                ('change_source', models.CharField(choices=[('registration', 'Registration'), ('staff_edit', 'Staff Edit')], default='registration', max_length=20)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('applicant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hazard_declaration_audits', to='intake.applicant')),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hazard_declaration_changes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Hazard declaration audit',
                'verbose_name_plural': 'Hazard declaration audits',
                'ordering': ['-created_at'],
            },
        ),
    ]
