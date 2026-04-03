from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial THA staff users (Arthur, Victor, Joie)'

    def handle(self, *args, **options):
        users_data = [
            {
                'username': 'arthur.maramba',
                'email': 'arthur.maramba@talisayhousing.gov.ph',
                'first_name': 'Arthur Benjamin',
                'last_name': 'Maramba',
                'position': 'head',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'victor.fregil',
                'email': 'victor.fregil@talisayhousing.gov.ph',
                'first_name': 'Victor',
                'last_name': 'Fregil',
                'position': 'oic',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'joie.tingson',
                'email': 'joie.tingson@talisayhousing.gov.ph',
                'first_name': 'Lourynie Joie',
                'last_name': 'Tingson',
                'position': 'second_member',
                'is_staff': True,
                'is_superuser': True,
            },
        ]

        for user_data in users_data:
            username = user_data['username']
            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.WARNING(f'User "{username}" already exists, skipping.')
                )
                continue

            user = User.objects.create_user(
                username=user_data['username'],
                email=user_data['email'],
                password='tha2026',  # Default password - should be changed on first login
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                position=user_data['position'],
                is_staff=user_data['is_staff'],
                is_superuser=user_data['is_superuser'],
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created user: {user.get_full_name()} ({username})')
            )

        self.stdout.write(self.style.SUCCESS('\nInitial users seeded successfully!'))
        self.stdout.write('Default password: tha2026')
        self.stdout.write('Please change passwords after first login.')
