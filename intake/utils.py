# filepath: c:\Users\jtcor\Documents\capstone\intake\utils.py
"""
Utility functions for the intake module.
"""
from django.conf import settings
import logging
import requests

logger = logging.getLogger(__name__)


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


def send_sms(phone_number, message, trigger_event, applicant=None, isf_record=None):
    """
    Send SMS notification via Semaphore API and log to database.
    
    Args:
        phone_number: Recipient phone number
        message: SMS message content
        trigger_event: Event that triggered SMS (registration, eligibility_passed, etc.)
        applicant: Applicant instance (optional)
        isf_record: ISFRecord instance (optional)
    
    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    from .models import SMSLog
    
    if not phone_number or not message:
        logger.warning("Cannot send SMS: missing phone number or message")
        return False
    
    # Format phone number
    phone_number = format_phone_number(phone_number)
    
    # Validate phone number format (Philippine mobile: 09XXXXXXXXX)
    if not phone_number.startswith('09') or len(phone_number) != 11:
        logger.warning(f"Invalid phone number format: {phone_number}")
        return False
    
    # Get Semaphore API key from settings
    api_key = getattr(settings, 'SEMAPHORE_API_KEY', None)
    sender_name = getattr(settings, 'SEMAPHORE_SENDER_NAME', 'SEMAPHORE')
    sms_enabled = getattr(settings, 'SMS_ENABLED', False)
    
    try:
        # Create SMS log record first (pending status)
        sms_log = SMSLog.objects.create(
            recipient_phone=phone_number,
            message_content=message,
            trigger_event=trigger_event,
            applicant=applicant,
            isf_record=isf_record,
            status='pending'
        )
        
        if sms_enabled and api_key:
            # Send via Semaphore API
            response = requests.post(
                'https://api.semaphore.co/api/v4/messages',
                data={
                    'apikey': api_key,
                    'number': phone_number,
                    'message': message,
                    'sendername': sender_name
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                sms_log.status = 'sent'
                sms_log.save(update_fields=['status'])
                logger.info(f"SMS sent via Semaphore: {trigger_event} to {phone_number}")
                return True
            else:
                error_msg = f"Semaphore API error: {response.status_code} - {response.text}"
                sms_log.status = 'failed'
                sms_log.error_message = error_msg
                sms_log.save(update_fields=['status', 'error_message'])
                logger.error(error_msg)
                return False
        else:
            # Development mode - just log to console
            sms_log.status = 'sent'
            sms_log.save(update_fields=['status'])
            
            logger.info(f"SMS logged (dev mode): {trigger_event} to {phone_number}")
            print(f"\n{'='*60}")
            print(f"📱 SMS NOTIFICATION {'(DEV MODE - Not actually sent)' if not sms_enabled else ''}")
            print(f"{'='*60}")
            print(f"To: {phone_number}")
            print(f"Event: {trigger_event}")
            print(f"Message: {message}")
            print(f"{'='*60}\n")
            
            return True
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error sending SMS: {str(e)}"
        logger.error(error_msg)
        
        # Update log with error
        SMSLog.objects.filter(id=sms_log.id).update(
            status='failed',
            error_message=error_msg
        )
        return False
        
    except Exception as e:
        logger.error(f"Failed to send SMS: {str(e)}")
        
        # Log failed SMS
        SMSLog.objects.create(
            recipient_phone=phone_number,
            message_content=message,
            trigger_event=trigger_event,
            applicant=applicant,
            isf_record=isf_record,
            status='failed',
            error_message=str(e)
        )
        
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
    from .models import Applicant, Barangay, QueueEntry
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
        
        # Get next position in priority queue
        last_position = QueueEntry.objects.filter(
            queue_type='priority',
            status='active'
        ).order_by('-position').first()
        
        next_position = (last_position.position + 1) if last_position else 1
        
        # Add to priority queue
        QueueEntry.objects.create(
            applicant=applicant,
            queue_type='priority',
            position=next_position,
            status='active',
            added_by=checked_by_user
        )
        
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
