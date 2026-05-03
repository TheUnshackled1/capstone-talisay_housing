from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0005_smslog"),
    ]

    operations = [
        migrations.DeleteModel(name="OccupancyReportDetail"),
        migrations.DeleteModel(name="OccupancyReport"),
        migrations.DeleteModel(name="ComplianceNotice"),
    ]
