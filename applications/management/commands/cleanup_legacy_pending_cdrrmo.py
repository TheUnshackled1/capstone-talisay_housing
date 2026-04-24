from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.utils import timezone

from applications.models import QueueEntry
from intake.models import Applicant, CDRRMOCertification


class Command(BaseCommand):
    help = (
        "One-time cleanup for legacy pending_cdrrmo rows that already have finalized "
        "CDRRMO status. Assigns queue based on certification and marks applicant eligible."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to database.",
        )

    def _deactivate_active_queue_entries(self, applicant):
        applicant.queue_entries.filter(status="active").update(
            status="removed",
            completed_at=timezone.now(),
        )

    def _ensure_queue_entry(self, applicant, queue_type):
        active_entries = list(
            applicant.queue_entries.filter(status="active").order_by("entered_at", "position")
        )
        if active_entries and active_entries[0].queue_type == queue_type:
            return active_entries[0], False
        if active_entries:
            self._deactivate_active_queue_entries(applicant)

        for _ in range(3):
            last_position = (
                QueueEntry.objects.filter(queue_type=queue_type, status="active")
                .order_by("-position")
                .values_list("position", flat=True)
                .first()
                or 0
            )
            try:
                with transaction.atomic():
                    entry = QueueEntry.objects.create(
                        applicant=applicant,
                        queue_type=queue_type,
                        position=last_position + 1,
                        status="active",
                        added_by=None,
                    )
                return entry, True
            except IntegrityError:
                continue

        existing = (
            applicant.queue_entries.filter(status="active", queue_type=queue_type)
            .order_by("entered_at")
            .first()
        )
        if existing:
            return existing, False
        raise RuntimeError("Unable to allocate queue position during cleanup.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        fixed = 0
        to_priority = 0
        to_walkin = 0
        skipped = 0

        cert_map = {
            cert.applicant_id: cert.status
            for cert in CDRRMOCertification.objects.filter(status__in=["certified", "not_certified"])
        }
        candidates = Applicant.objects.filter(
            channel="danger_zone",
            status="pending_cdrrmo",
            module2_handoff_at__isnull=False,
            id__in=list(cert_map.keys()),
        ).order_by("created_at")

        self.stdout.write(
            self.style.NOTICE(
                f"Found {candidates.count()} legacy pending_cdrrmo record(s) with finalized CDRRMO."
            )
        )

        for applicant in candidates:
            cert_status = cert_map.get(applicant.id)
            if cert_status not in ("certified", "not_certified"):
                skipped += 1
                continue

            queue_type = "priority" if cert_status == "certified" else "walk_in"
            if dry_run:
                fixed += 1
                if queue_type == "priority":
                    to_priority += 1
                else:
                    to_walkin += 1
                continue

            applicant.status = "eligible"
            applicant.disqualification_reason = ""
            if not applicant.eligibility_checked_at:
                applicant.eligibility_checked_at = timezone.now()
            applicant.save(update_fields=["status", "disqualification_reason", "eligibility_checked_at", "updated_at"])

            self._ensure_queue_entry(applicant, queue_type)
            fixed += 1
            if queue_type == "priority":
                to_priority += 1
            else:
                to_walkin += 1

        summary = (
            f"Cleanup complete. Fixed={fixed}, "
            f"Priority assigned={to_priority}, Walk-in assigned={to_walkin}, Skipped={skipped}"
        )
        self.stdout.write(self.style.SUCCESS(summary))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run mode: no database changes were made."))

