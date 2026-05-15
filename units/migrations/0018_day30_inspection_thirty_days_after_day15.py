from datetime import timedelta

from django.db import migrations


GRACE_PERIOD_DAYS = 30


def day30_thirty_days_after_day15(apps, schema_editor):
    """
    The 30 Day inspection must fall 30 calendar days after the 15 Day due date.
    Older rows used monitoring_start + 30, which is only 15 days after the 15 Day visit.
    """
    MonitoringTask = apps.get_model("units", "MonitoringTask")

    day15_tasks = (
        MonitoringTask.objects.filter(
            task_type="day_15_inspection",
            lot_award__awarded_at__isnull=False,
        )
        .select_related("lot_award")
    )

    to_update = []
    for day15 in day15_tasks:
        day30 = (
            MonitoringTask.objects.filter(
                lot_award_id=day15.lot_award_id,
                task_type="day_30_inspection",
            )
            .first()
        )
        if not day30:
            continue
        anchor = day15.due_date
        new_date = anchor + timedelta(days=30)
        if (
            day30.due_date != new_date
            or day30.scheduled_date != new_date
            or day30.days_from_award != 45
        ):
            day30.due_date = new_date
            day30.scheduled_date = new_date
            day30.days_from_award = 45
            to_update.append(day30)

    if to_update:
        MonitoringTask.objects.bulk_update(
            to_update,
            ["scheduled_date", "due_date", "days_from_award"],
        )

    # Lot awards that have a 30 Day task but no 15 Day row (edge case): align to award + grace + 45.
    orphan_30 = (
        MonitoringTask.objects.filter(
            task_type="day_30_inspection",
            lot_award__awarded_at__isnull=False,
        )
        .exclude(
            lot_award_id__in=MonitoringTask.objects.filter(
                task_type="day_15_inspection",
            ).values_list("lot_award_id", flat=True)
        )
        .select_related("lot_award")
    )
    orphan_update = []
    for t30 in orphan_30:
        award_date = t30.lot_award.awarded_at.date()
        monitoring_start = award_date + timedelta(days=GRACE_PERIOD_DAYS)
        new_date = monitoring_start + timedelta(days=45)
        if (
            t30.due_date != new_date
            or t30.scheduled_date != new_date
            or t30.days_from_award != 45
        ):
            t30.due_date = new_date
            t30.scheduled_date = new_date
            t30.days_from_award = 45
            orphan_update.append(t30)
    if orphan_update:
        MonitoringTask.objects.bulk_update(
            orphan_update,
            ["scheduled_date", "due_date", "days_from_award"],
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("units", "0017_explanation_letter_workflow"),
    ]

    operations = [
        migrations.RunPython(day30_thirty_days_after_day15, reverse_noop),
    ]
