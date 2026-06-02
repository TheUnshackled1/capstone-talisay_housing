"""
Send SMS reminders for explanation-letter deadlines opened from No Progress monitoring.

Schedule this command (e.g. daily) via cron or a host scheduler:
    python manage.py send_explanation_letter_deadline_reminders

- Day before deadline: one reminder SMS (if phone on file).
- After deadline with no scanned letter: one "deadline passed" SMS (non-compliance notice).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from intake.utils import send_sms
from units.models import ExplanationReview


class Command(BaseCommand):
    help = 'SMS reminders for explanation-letter deadlines (eve + past-due without letter).'

    def handle(self, *args, **options):
        now = timezone.now()
        today = timezone.localtime(now).date()
        tomorrow = today + timedelta(days=1)

        qs = (
            ExplanationReview.objects.filter(
                review_status='pending_review',
                letter_deadline_at__isnull=False,
            )
            .select_related('lot_award__application__applicant', 'unit')
        )

        eve_count = 0
        due_count = 0

        for rev in qs:
            if rev.letter_document:
                continue
            applicant = rev.lot_award.application.applicant
            phone = (applicant.phone_number or '').strip()
            if not phone:
                continue

            local_deadline = timezone.localtime(rev.letter_deadline_at).date()

            if (
                local_deadline == tomorrow
                and rev.deadline_eve_sms_sent_at is None
            ):
                local_disp = timezone.localtime(rev.letter_deadline_at).strftime('%b %d, %Y %I:%M %p')
                send_sms(
                    phone,
                    (
                        f"THA REMINDER: Your explanation letter for Block {rev.unit.block_number} Lot {rev.unit.lot_number} "
                        f"is due tomorrow ({local_disp}) at the Housing Office. Ref: {applicant.reference_number or '—'}"
                    ),
                    'explanation_letter_deadline_eve',
                    applicant=applicant,
                    module='units',
                )
                rev.deadline_eve_sms_sent_at = now
                rev.save(update_fields=['deadline_eve_sms_sent_at', 'updated_at'])
                eve_count += 1

            if now >= rev.letter_deadline_at and rev.deadline_due_sms_sent_at is None:
                send_sms(
                    phone,
                    (
                        f"THA NOTICE: Nalabyan na ang deadline sang imo explanation letter para sa Block {rev.unit.block_number} "
                        f"Lot {rev.unit.lot_number}, kag wala pa sang scanned nga kopya nga na-file. "
                        f"Palihog magkadto dayon sa Housing Office ukon mahimo nga ma-disqualify ang imo aplikasyon. "
                        f"Ref: {applicant.reference_number or '—'}"
                    ),
                    'explanation_letter_deadline_passed',
                    applicant=applicant,
                    module='units',
                )
                rev.deadline_due_sms_sent_at = now
                rev.save(update_fields=['deadline_due_sms_sent_at', 'updated_at'])
                due_count += 1

        self.stdout.write(self.style.SUCCESS(f'Eve reminders: {eve_count}; past-due notices: {due_count}'))
