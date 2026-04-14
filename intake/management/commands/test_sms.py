"""
Management command to test SMS sending via Twilio or Semaphore.

Usage:
    python manage.py test_sms --phone 09XXXXXXXXX
    python manage.py test_sms --phone 09XXXXXXXXX --service twilio
    python manage.py test_sms --phone 09XXXXXXXXX --service semaphore
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from intake.utils import send_sms


class Command(BaseCommand):
    help = 'Test SMS sending via Twilio or Semaphore'

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
            default='twilio',
            choices=['twilio', 'semaphore'],
            help='SMS service to use (default: twilio)'
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

        # Temporarily override SMS service
        original_service = getattr(settings, 'SMS_SERVICE', 'semaphore')
        settings.SMS_SERVICE = service

        # Test SMS
        success = send_sms(
            phone_number=phone,
            message=message,
            trigger_event='test_sms',
            applicant=None,
            isf_record=None
        )

        # Restore original service
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
