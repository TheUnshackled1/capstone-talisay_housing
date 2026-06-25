from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('units', '0028_remove_extension_90_day_visit'),
    ]

    operations = [
        migrations.AddField(
            model_name='housingunit',
            name='plan_polygon_index',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
