"""
Management command to test SMS routing (console / Twilio / Semaphore / httpSMS).

Usage:
    python manage.py test_sms --phone 09987654321
    python manage.py test_sms --phone 09987654321 --service console
    python manage.py test_sms --phone 09987654321 --service twilio
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from intake.utils import send_sms


class Command(BaseCommand):
    help = 'Test SMS pipeline (console mode needs no API keys; use twilio when subscribed)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            required=True,
            help='Philippine phone number (09XXXXXXXXX format)'
        )
        parser.add_argument(
            '--service',
            type=str,
            default='console',
            choices=['console', 'twilio', 'semaphore', 'httpsms'],
            help='SMS_SERVICE override for this run (default: console)'
        )
        parser.add_argument(
            '--message',
            type=str,
            default='Test SMS from IHSMS System',
            help='Custom message to send'
        )

    def handle(self, *args, **options):
        phone = options['phone']
        service = options['service']
        message = options['message']

        self.stdout.write(self.style.WARNING(f'\nTesting SMS via {service.upper()}'))
        self.stdout.write(f'Phone: {phone}')
        self.stdout.write(f'Message: {message}\n')

        original_service = getattr(settings, 'SMS_SERVICE', 'console')
        settings.SMS_SERVICE = service

        success = send_sms(
            phone_number=phone,
            message=message,
            trigger_event='test_sms',
            applicant=None,
        )

        settings.SMS_SERVICE = original_service

        if success:
            self.stdout.write(
                self.style.SUCCESS(f'\nSMS test SUCCESSFUL!')
            )
            self.stdout.write(f'Message sent to {phone} via {service.upper()}')
        else:
            self.stdout.write(
                self.style.ERROR(f'\nSMS test FAILED!')
            )
            self.stdout.write('Check your phone number format and API credentials.')

        self.stdout.write('')
