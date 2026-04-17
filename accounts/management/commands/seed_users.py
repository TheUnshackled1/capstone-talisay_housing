from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial THA staff users'
    
    def handle(self, *args, **options):
        # Superusers (Admin access)
        superusers_data = [
            {
                'username': 'arthur.maramba',
                'email': 'arthur.maramba@talisayhousing.gov.ph',
                'first_name': 'Arthur Benjamin',
                'last_name': 'Maramba',
                'position': 'head',
            },
            {
                'username': 'victor.fregil',
                'email': 'victor.fregil@talisayhousing.gov.ph',
                'first_name': 'Victor',
                'last_name': 'Fregil',
                'position': 'oic',
            },
            {
                'username': 'joie.tingson',
                'email': 'joie.tingson@talisayhousing.gov.ph',
                'first_name': 'Lourynie Joie',
                'last_name': 'Tingson',
                'position': 'second_member',
            },
        ]

        # Regular staff (No admin access)
        staff_data = [
            {
                'username': 'jocel.cuaysing',
                'email': 'jocel.cuaysing@talisayhousing.gov.ph',
                'first_name': 'Jocel',
                'last_name': 'Cuaysing',
                'position': 'fourth_member',
            },
            {
                'username': 'laarni.hellera',
                'email': 'laarni.hellera@talisayhousing.gov.ph',
                'first_name': 'Laarni',
                'last_name': 'Hellera',
                'position': 'fifth_member',
            },
            # Caretaker
            {
                'username': 'nonoy.caretaker',
                'email': 'nonoy@talisayhousing.gov.ph',
                'first_name': 'Nonoy',
                'last_name': 'Cura',
                'position': 'caretaker',
            },
            # Ronda / Field Personnel
            {
                'username': 'paul.betila',
                'email': 'paul.betila@talisayhousing.gov.ph',
                'first_name': 'Paul Martin',
                'last_name': 'Betila',
                'position': 'ronda',
            },
            {
                'username': 'roberto.dreyfus',
                'email': 'roberto.dreyfus@talisayhousing.gov.ph',
                'first_name': 'Roberto',
                'last_name': 'Dreyfus',
                'position': 'ronda',
            },
            {
                'username': 'field.team',
                'email': 'field@talisayhousing.gov.ph',
                'first_name': 'Field',
                'last_name': 'Team',
                'position': 'field',
            },
        ]

        created_count = 0
        skipped_count = 0

        # Create superusers
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Creating Superusers ==='))
        for user_data in superusers_data:
            username = user_data['username']
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f'  [SKIP] "{username}" already exists'))
                skipped_count += 1
                continue

            user = User.objects.create_user(
                username=username,
                email=user_data['email'],
                password='tha2026',
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                position=user_data['position'],
                is_staff=True,
                is_superuser=True,
            )
            self.stdout.write(self.style.SUCCESS(f'  [OK] {user.get_full_name()} ({username})'))
            created_count += 1

        # Create regular staff
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Creating Staff Users ==='))
        for user_data in staff_data:
            username = user_data['username']
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f'  [SKIP] "{username}" already exists'))
                skipped_count += 1
                continue

            user = User.objects.create_user(
                username=username,
                email=user_data['email'],
                password='tha2026',
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                position=user_data['position'],
                is_staff=True,
                is_superuser=False,
            )
            self.stdout.write(self.style.SUCCESS(f'  [OK] {user.get_full_name()} ({username})'))
            created_count += 1

        # Summary
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Summary ==='))
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(self.style.NOTICE('\n  Default password: tha2026'))
        self.stdout.write('  Please change passwords after first login.\n')
