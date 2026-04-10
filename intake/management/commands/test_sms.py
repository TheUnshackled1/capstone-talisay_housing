"""
Django management command to test Semaphore SMS integration.

Usage:
    python manage.py test_sms --phone "YOUR_PHONE_NUMBER"
    python manage.py test_sms -p 09171234567
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from intake.utils import send_sms
from intake.models import SMSLog


class Command(BaseCommand):
    help = 'Test Semaphore SMS integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            '-p',
            type=str,
            required=True,
            help='Phone number to send test SMS to (09XX format)'
        )
        parser.add_argument(
            '--message',
            '-m',
            type=str,
            default='Test SMS from Talisay Housing System. If you received this, SMS integration is working! 🎉',
            help='Custom message to send'
        )

    def handle(self, *args, **options):
        phone_number = options['phone']
        message = options['message']

        self.stdout.write(self.style.HTTP_INFO('=' * 70))
        self.stdout.write(self.style.HTTP_INFO('SEMAPHORE SMS INTEGRATION TEST'))
        self.stdout.write(self.style.HTTP_INFO('=' * 70))

        # Check configuration
        self.stdout.write('\n📋 Configuration Check:')
        sms_enabled = getattr(settings, 'SMS_ENABLED', False)
        api_key = getattr(settings, 'SEMAPHORE_API_KEY', None)
        sender_name = getattr(settings, 'SEMAPHORE_SENDER_NAME', 'SEMAPHORE')

        self.stdout.write(f'  SMS_ENABLED: {self.style.SUCCESS("✓") if sms_enabled else self.style.ERROR("✗")} {sms_enabled}')
        self.stdout.write(f'  SEMAPHORE_API_KEY: {self.style.SUCCESS("✓") if api_key else self.style.ERROR("✗")} {"***" + api_key[-8:] if api_key else "NOT SET"}')
        self.stdout.write(f'  SEMAPHORE_SENDER_NAME: {self.style.SUCCESS("✓")} {sender_name}')

        if not sms_enabled:
            self.stdout.write(self.style.WARNING('\n⚠️  SMS_ENABLED is False. SMS will be logged but not sent.'))

        if not api_key:
            raise CommandError(self.style.ERROR('❌ SEMAPHORE_API_KEY not configured in settings.py'))

        # Phone number validation
        self.stdout.write('\n📱 Phone Validation:')
        self.stdout.write(f'  Input: {phone_number}')

        from intake.utils import format_phone_number
        formatted_phone = format_phone_number(phone_number)
        self.stdout.write(f'  Formatted: {formatted_phone}')

        if not formatted_phone.startswith('09') or len(formatted_phone) != 11:
            raise CommandError(self.style.ERROR(f'❌ Invalid phone number format: {formatted_phone}'))

        self.stdout.write(self.style.SUCCESS(f'  ✓ Phone number valid'))

        # Send test SMS
        self.stdout.write('\n📤 Sending Test SMS...')
        self.stdout.write(f'  To: {formatted_phone}')
        self.stdout.write(f'  Message: {message}')
        self.stdout.write('')

        try:
            result = send_sms(
                phone_number=formatted_phone,
                message=message,
                trigger_event='test_sms_command'
            )

            if result:
                self.stdout.write(self.style.SUCCESS('\n✅ SMS send request successful!'))
            else:
                self.stdout.write(self.style.ERROR('\n❌ SMS send failed. Check logs below.'))

        except Exception as e:
            raise CommandError(self.style.ERROR(f'❌ Error sending SMS: {str(e)}'))

        # Show SMS log entry
        self.stdout.write('\n📋 SMS Log Entry:')
        try:
            latest_log = SMSLog.objects.filter(recipient_phone=formatted_phone).latest('sent_at')
            self.stdout.write(f'  SMS ID: {latest_log.id}')
            self.stdout.write(f'  Status: {self.style.SUCCESS(latest_log.get_status_display()) if latest_log.status == "sent" else self.style.ERROR(latest_log.get_status_display())}')
            self.stdout.write(f'  Trigger Event: {latest_log.trigger_event}')
            self.stdout.write(f'  Sent At: {latest_log.sent_at}')
            if latest_log.error_message:
                self.stdout.write(f'  Error: {self.style.ERROR(latest_log.error_message)}')
        except SMSLog.DoesNotExist:
            self.stdout.write(self.style.WARNING('  No SMS log found'))

        # Next steps
        self.stdout.write('\n' + self.style.HTTP_INFO('=' * 70))
        self.stdout.write(self.style.SUCCESS('✓ TEST COMPLETE'))
        self.stdout.write(self.style.HTTP_INFO('=' * 70))

        self.stdout.write('\n💡 Next Steps:')
        self.stdout.write('  1. Check your phone for the test SMS')
        self.stdout.write('  2. If received: SMS integration is working! 🎉')
        self.stdout.write('  3. If NOT received:')
        self.stdout.write('     - Verify API key is correct in /talisay_housing/settings.py')
        self.stdout.write('     - Check Semaphore account balance/quota at https://semaphore.co')
        self.stdout.write('     - Review error message in SMS Log above')
        self.stdout.write('  4. View full SMS logs in Django admin: /admin/intake/smslog/')
        self.stdout.write('')
