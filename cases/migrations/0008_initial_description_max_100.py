from django.db import migrations, models


def truncate_descriptions(apps, schema_editor):
    Case = apps.get_model('cases', 'Case')
    for case in Case.objects.all().only('id', 'initial_description'):
        desc = (case.initial_description or '')[:100]
        if desc != case.initial_description:
            Case.objects.filter(pk=case.pk).update(initial_description=desc)


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0007_remove_smslog'),
    ]

    operations = [
        migrations.RunPython(truncate_descriptions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='case',
            name='initial_description',
            field=models.CharField(max_length=100, verbose_name='Incident description'),
        ),
    ]
