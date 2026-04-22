# filepath: c:\Users\jtcor\Documents\capstone\intake\utils.py
"""
Utility functions for the intake module.
"""
from django.conf import settings
import logging
import requests

logger = logging.getLogger(__name__)


def _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, label):
    """Mark log as sent without calling an external provider (local / test)."""
    sms_log.status = 'sent'
    sms_log.external_id = f'{label}:simulated'
    sms_log.save(update_fields=['status', 'external_id'])
    logger.info(
        'SMS simulated [%s] event=%s to=%s msg=%s',
        label, trigger_event, phone_number, (message or '')[:200],
    )
    print(f"\n{'=' * 60}\nSMS SIMULATED ({label}) — not sent via paid gateway\n{'=' * 60}")
    print(f"To: {phone_number}\nEvent: {trigger_event}\nMessage:\n{message}\n{'=' * 60}\n")
    return True


def format_phone_number(phone_number):
    """
    Format Philippine phone number for SMS API.
    Converts various formats to 09XXXXXXXXX format.
    """
    phone = phone_number.strip().replace(' ', '').replace('-', '')
    
    # Remove +63 prefix
    if phone.startswith('+63'):
        phone = '0' + phone[3:]
    # Remove 63 prefix (without +)
    elif phone.startswith('63') and len(phone) == 12:
        phone = '0' + phone[2:]
    # Add 0 prefix if starts with 9
    elif phone.startswith('9') and len(phone) == 10:
        phone = '0' + phone
    
    return phone


def send_sms(phone_number, message, trigger_event, applicant=None, isf_record=None, module='intake'):
    """
    Send SMS notification via configured SMS API and log to app-specific SMSLog.

    Args:
        phone_number: Recipient phone number
        message: SMS message content
        trigger_event: Event that triggered SMS (registration, eligibility_passed, etc.)
        applicant: Applicant instance (optional)
        isf_record: ISFRecord instance (optional)
        module: App module for SMS logging ('intake', 'applications', 'documents', 'units', 'cases')

    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    # Route to correct app's SMSLog based on module parameter
    if module == 'intake':
        from .models import SMSLog
    elif module == 'applications':
        from applications.models import SMSLog
    elif module == 'documents':
        from documents.models import SMSLog
    elif module == 'units':
        from units.models import SMSLog
    elif module == 'cases':
        from cases.models import SMSLog
    else:
        logger.warning(f"Unknown SMS module: {module}")
        from .models import SMSLog  # Default to intake

    if not phone_number or not message:
        logger.warning("Cannot send SMS: missing phone number or message")
        return False

    # Format phone number
    phone_number = format_phone_number(phone_number)

    # Validate phone number format (Philippine mobile: 09XXXXXXXXX)
    if not phone_number.startswith('09') or len(phone_number) != 11:
        logger.warning(f"Invalid phone number format: {phone_number}")
        return False

    sms_service = (getattr(settings, 'SMS_SERVICE', 'console') or 'console').lower()
    sms_enabled = getattr(settings, 'SMS_ENABLED', True)

    try:
        # Create SMS log record in app-specific table (pending status)
        sms_log = SMSLog.objects.create(
            recipient_phone=phone_number,
            message_content=message,
            trigger_event=trigger_event,
            applicant=applicant,
            status='pending'
        )

        # Local / CI: no API keys required — full workflow + SMSLog audit trail
        if sms_service == 'console':
            return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'console')

        if not sms_enabled:
            return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'disabled')

        # IPROG: Affordable SMS gateway (P1/SMS - perfect for capstone projects)
        success = send_sms_iprog(phone_number, message, sms_log)
        if success:
            logger.info('SMS sent via IPROG: %s to %s (module: %s)', trigger_event, phone_number, module)
        return success


    except Exception as e:
        logger.error('Failed to send SMS: %s', str(e))

        SMSLog.objects.create(
            recipient_phone=phone_number,
            message_content=message,
            trigger_event=trigger_event,
            applicant=applicant,
            status='failed',
            error_message=str(e)
        )

        return False



def send_sms_iprog(phone_number, message, sms_log):
    """
    Send SMS via IPROG SMS API (Affordable Philippine SMS Gateway - P1/SMS).

    Args:
        phone_number: Philippine mobile number (09XXXXXXXXX format)
        message: SMS message content
        sms_log: SMSLog instance to update

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        api_token = getattr(settings, 'IPROG_API_TOKEN', None)

        if not api_token:
            raise Exception("IPROG API token not configured in settings")

        # IPROG API endpoint with query parameters
        base_url = 'https://www.iprogsms.com/api/v1/sms_messages'

        # Convert to IPROG format: 09XXXXXXXXX → 639XXXXXXXXX (no + or leading 0)
        if phone_number.startswith('0'):
            to_number = '63' + phone_number[1:]
        elif phone_number.startswith('+63'):
            to_number = phone_number[1:]  # Remove +
        else:
            to_number = phone_number

        # Build query parameters
        params = {
            'api_token': api_token,
            'phone_number': to_number,
            'message': message
        }

        response = requests.post(
            base_url,
            params=params,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            # IPROG returns status: 200 and message_id on success
            if result.get('status') == 200 and result.get('message_id'):
                sms_log.status = 'sent'
                sms_log.external_id = result.get('message_id', f'iprog-{sms_log.id}')
                sms_log.save(update_fields=['status', 'external_id'])
                logger.info(f"IPROG SMS sent - Message ID: {sms_log.external_id}")
                return True
            else:
                error_msg = result.get('message', 'Unknown IPROG error')
                raise Exception(f"IPROG error: {error_msg}")
        else:
            error_msg = f"IPROG API error: HTTP {response.status_code}"
            if response.text:
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('message', response.text)}"
                except:
                    error_msg += f" - {response.text}"
            raise Exception(error_msg)

    except Exception as e:
        error_msg = f"IPROG error: {str(e)}"
        logger.error(error_msg)
        sms_log.status = 'failed'
        sms_log.error_message = error_msg
        sms_log.save(update_fields=['status', 'error_message'])
        return False


def check_blacklist(full_name, phone_number=None):
    """
    Check if a person is on the blacklist.
    
    Args:
        full_name: Full name to check
        phone_number: Phone number to check (optional)
    
    Returns:
        tuple: (is_blacklisted: bool, blacklist_entry or None)
    """
    from .models import Blacklist
    
    # Check by name (case-insensitive partial match)
    name_match = Blacklist.objects.filter(
        full_name__icontains=full_name.strip()
    ).first()
    
    if name_match:
        return (True, name_match)
    
    # Check by phone number if provided
    if phone_number:
        phone_match = Blacklist.objects.filter(
            phone_number=phone_number.strip()
        ).first()
        
        if phone_match:
            return (True, phone_match)
    
    return (False, None)


def ensure_priority_queue_entry(applicant, added_by=None):
    """
    Ensure an applicant has one active Priority queue entry.

    Returns:
        tuple[QueueEntry, bool]: (entry, created)
    """
    from django.db import IntegrityError, transaction
    from applications.models import QueueEntry

    existing = applicant.queue_entries.filter(status='active').order_by('entered_at').first()
    if existing:
        return existing, False

    for _ in range(3):
        last_position = QueueEntry.objects.filter(
            queue_type='priority',
            status='active'
        ).order_by('-position').values_list('position', flat=True).first() or 0

        try:
            with transaction.atomic():
                entry = QueueEntry.objects.create(
                    applicant=applicant,
                    queue_type='priority',
                    position=last_position + 1,
                    status='active',
                    added_by=added_by,
                )
            return entry, True
        except IntegrityError:
            # Retry when two staff actions race for same queue slot.
            continue

    entry = applicant.queue_entries.filter(status='active').order_by('entered_at').first()
    if entry:
        return entry, False

    raise RuntimeError('Unable to allocate priority queue position')


def create_applicant_from_isf(isf_record, checked_by_user):
    """
    Convert an eligible ISF record to a full Applicant profile.
    Places applicant in Priority Queue.
    
    Args:
        isf_record: ISFRecord instance
        checked_by_user: User who checked eligibility
    
    Returns:
        Applicant instance or None if failed
    """
    from .models import Applicant, Barangay
    from django.utils import timezone
    
    try:
        # Get barangay instance
        barangay, _ = Barangay.objects.get_or_create(
            name=isf_record.submission.barangay
        )
        
        # Create Applicant profile
        applicant = Applicant.objects.create(
            full_name=isf_record.full_name,
            phone_number=isf_record.phone_number,
            barangay=barangay,
            current_address=isf_record.submission.property_address,
            years_residing=isf_record.years_residing,
            monthly_income=isf_record.monthly_income,
            channel='landowner',
            status='eligible',
            isf_record=isf_record,
            has_property_in_talisay=False,  # Already checked during eligibility
            eligibility_checked_by=checked_by_user,
            eligibility_checked_at=timezone.now(),
            registered_by=checked_by_user
        )
        
        # Add to priority queue
        ensure_priority_queue_entry(applicant, added_by=checked_by_user)
        
        # Mark ISF record as converted
        isf_record.converted_to_applicant = True
        isf_record.applicant_created_at = timezone.now()
        isf_record.status = 'eligible'
        isf_record.save(update_fields=['converted_to_applicant', 'applicant_created_at', 'status'])
        
        # Send eligibility SMS
        isf_record.send_eligibility_sms(eligible=True)
        
        logger.info(f"Created applicant {applicant.reference_number} from ISF {isf_record.reference_number}")
        
        return applicant
        
    except Exception as e:
        logger.error(f"Failed to create applicant from ISF: {str(e)}")
        return None
