# filepath: c:\Users\jtcor\Documents\capstone\intake\utils.py
"""
Utility functions for the intake module.
"""
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_sms(phone_number, message, trigger_event, applicant=None, isf_record=None):
    """
    Send SMS notification and log to database.
    
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
    
    # Clean phone number
    phone_number = phone_number.strip()
    
    try:
        # TODO: Integrate with actual SMS provider (e.g., Semaphore, Twilio)
        # For now, just log the SMS
        
        # Create SMS log record
        sms_log = SMSLog.objects.create(
            recipient_phone=phone_number,
            message_content=message,
            trigger_event=trigger_event,
            applicant=applicant,
            isf_record=isf_record,
            status='sent'  # In production, would be 'pending' until confirmed
        )
        
        logger.info(f"SMS logged: {trigger_event} to {phone_number}")
        print(f"\n{'='*60}")
        print(f"SMS NOTIFICATION")
        print(f"{'='*60}")
        print(f"To: {phone_number}")
        print(f"Event: {trigger_event}")
        print(f"Message: {message}")
        print(f"{'='*60}\n")
        
        return True
        
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
