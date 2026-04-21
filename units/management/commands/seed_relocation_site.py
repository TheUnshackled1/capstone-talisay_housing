from django.core.management.base import BaseCommand
from django.db import transaction

from intake.models import Barangay
from units.models import HousingUnit, RelocationSite


class Command(BaseCommand):
    help = (
        "Create a demo RelocationSite (GK Cabatangan) and sample HousingUnit rows "
        "so Module 4 / housing-units views work in local development."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-units",
            action="store_true",
            help="Only ensure the relocation site exists; do not create housing units.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        barangay = (
            Barangay.objects.filter(is_active=True, name__iexact="Cabatangan").first()
            or Barangay.objects.filter(is_active=True).order_by("name").first()
        )
        if not barangay:
            self.stderr.write(
                self.style.ERROR(
                    "No barangays found. Run migrations so intake.0002_seed_barangays applies, "
                    "then run this command again."
                )
            )
            return

        site, created = RelocationSite.objects.update_or_create(
            code="GK-CAB",
            defaults={
                "name": "GK Cabatangan Relocation Site",
                "address": "Cabatangan, Talisay City, Cebu",
                "barangay": barangay,
                "total_blocks": 2,
                "total_lots": 12,
                "is_active": True,
                "notes": "Seeded for development (manage.py seed_relocation_site).",
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} relocation site: {site.name} ({site.code}) "
                f"(barangay: {barangay.name})"
            )
        )

        if options["skip_units"]:
            self.stdout.write(self.style.WARNING("Skipped housing units (--skip-units)."))
            return

        demo_units = [
            ("1", "1", "Occupied", "Sample Resident A"),
            ("1", "2", "Vacant — available", ""),
            ("1", "3", "Vacant — available", ""),
            ("1", "4", "Under notice (30-day)", "Sample Resident B"),
            ("2", "1", "Occupied", "Sample Resident C"),
            ("2", "2", "Vacant — available", ""),
            ("2", "3", "Final notice (10-day)", "Sample Resident D"),
            ("2", "4", "Repossessed", ""),
        ]

        n_new = 0
        for block, lot, status, occupant_name in demo_units:
            _, u_created = HousingUnit.objects.get_or_create(
                site=site,
                block_number=block,
                lot_number=lot,
                defaults={
                    "status": status,
                    "occupant_name": occupant_name or None,
                },
            )
            if u_created:
                n_new += 1

        total = site.units.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Housing units: created {n_new} new row(s); {total} total for this site."
            )
        )
