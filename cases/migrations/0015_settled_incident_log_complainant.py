from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0001_initial'),
        ('cases', '0014_fix_case_delete_foreign_keys'),
    ]

    operations = [
        migrations.AddField(
            model_name='fieldsettledincidentlog',
            name='complainant_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='fieldsettledincidentlog',
            name='complainant_phone',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='fieldsettledincidentlog',
            name='complainant_applicant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='settled_incident_logs_as_complainant',
                to='intake.applicant',
            ),
        ),
    ]
