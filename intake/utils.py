# filepath: c:\Users\jtcor\Documents\capstone\intake\utils.py
"""
Utility functions for the intake module.
"""
from django.conf import settings
import logging
import requests
import time

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
    import sys
    sep = '=' * 60
    sys.stderr.write(f"\n{sep}\nSMS SIMULATED ({label}) — not sent via paid gateway\n{sep}\n")
    sys.stderr.write(f"To: {phone_number}\nEvent: {trigger_event}\nMessage:\n{message}\n{sep}\n\n")
    sys.stderr.flush()
    return True


def format_phone_number(phone_number):
    """
    Format Philippine phone number for SMS API.
    Converts various formats to 09XXXXXXXXX format.
    """
    # Keep only digits/+ so user-entered separators don't break delivery.
    raw = (phone_number or '').strip()
    phone = ''.join(ch for ch in raw if ch.isdigit() or ch == '+')
    
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


def send_sms(phone_number, message, trigger_event, applicant=None, module='intake'):
    """
    Send SMS notification via configured SMS API and log to app-specific SMSLog.

    Args:
        phone_number: Recipient phone number
        message: SMS message content
        trigger_event: Event that triggered SMS (registration, eligibility_passed, etc.)
        applicant: Applicant instance (optional)
        module: App module for SMS logging ('intake', 'applications', 'units').
            ``documents`` is accepted as a legacy alias and logs to ``applications.SMSLog``.

    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    # Route to correct app's SMSLog based on module parameter
    if module == 'intake':
        from .models import SMSLog
    elif module in ('applications', 'documents'):
        from applications.models import SMSLog
    elif module == 'units':
        from units.models import SMSLog
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

    sms_service = (getattr(settings, 'SMS_SERVICE', 'console') or 'console').strip().lower()
    sms_enabled = getattr(settings, 'SMS_ENABLED', True)
    is_debug = bool(getattr(settings, 'DEBUG', False))

    try:
        # Create SMS log record in app-specific table (pending status)
        sms_log = SMSLog.objects.create(
            recipient_phone=phone_number,
            message_content=message,
            trigger_event=trigger_event,
            applicant=applicant,
            status='pending'
        )

        # Local / CI only — set SMS_SERVICE=semaphore in .env for real delivery (restart runserver after edits).
        if sms_service == 'console':
            logger.info(
                'SMS console simulation (SMS_SERVICE=console). Set SMS_SERVICE=semaphore in .env '
                'and restart runserver to send via Semaphore.'
            )
            return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'console')

        # Backward-compatible service aliases used in older .env files.
        if sms_service in {'clicksend', 'click_send', 'click-send'}:
            logger.warning("SMS_SERVICE=%s is deprecated/unsupported; falling back to console simulation.", sms_service)
            return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'console-fallback')

        if sms_service in {'iprog'}:
            logger.warning(
                "SMS_SERVICE=iprog was removed; configure semaphore instead. Falling back to console simulation."
            )
            return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'console-fallback')

        # Unknown service values should not silently break local testing.
        if sms_service not in {'semaphore'}:
            logger.warning("Unknown SMS_SERVICE=%s; falling back to console simulation.", sms_service)
            return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'console-fallback')

        if not sms_enabled:
            return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'disabled')

        api_key = (getattr(settings, 'SEMAPHORE_API_KEY', '') or '').strip()
        if not api_key:
            if is_debug:
                logger.warning(
                    "SEMAPHORE_API_KEY is missing in DEBUG mode; falling back to console simulation."
                )
                return _sms_simulate_delivery(sms_log, phone_number, message, trigger_event, 'console-fallback')
            sms_log.status = 'failed'
            sms_log.error_message = 'Semaphore API key not configured'
            sms_log.save(update_fields=['status', 'error_message'])
            return False

        success = send_sms_semaphore(phone_number, message, sms_log)
        if success:
            logger.info('SMS sent via Semaphore: %s to %s (module: %s)', trigger_event, phone_number, module)
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



def _semaphore_send_url():
    """Standard queue can lag minutes at peak; priority queue sends immediately (2 credits/SMS)."""
    if getattr(settings, 'SEMAPHORE_USE_PRIORITY_QUEUE', True):
        return 'https://api.semaphore.co/api/v4/priority'
    return 'https://api.semaphore.co/api/v4/messages'


def send_sms_semaphore(phone_number, message, sms_log):
    """
    Send SMS via Semaphore (Philippines).

    Uses the priority endpoint by default (see SEMAPHORE_USE_PRIORITY_QUEUE) so staff alerts
    are not stuck behind bulk traffic on the standard FIFO queue.

    Messages whose body begins with the word 'TEST' are ignored by Semaphore (not billed, not sent).
    """
    api_key = (getattr(settings, 'SEMAPHORE_API_KEY', '') or '').strip()
    if not api_key:
        raise Exception('Semaphore API key not configured in settings')

    send_url = _semaphore_send_url()
    queue_label = 'priority' if '/priority' in send_url else 'standard'
    send_timeout = float(getattr(settings, 'SEMAPHORE_SEND_TIMEOUT_SECONDS', 12))
    retry_attempts = max(1, int(getattr(settings, 'SEMAPHORE_SEND_RETRY_ATTEMPTS', 2)))
    retry_backoff = float(getattr(settings, 'SEMAPHORE_SEND_RETRY_BACKOFF_SECONDS', 1.0))

    payload = {
        'apikey': api_key,
        'number': phone_number,
        'message': message,
    }
    sender_name = (getattr(settings, 'SEMAPHORE_SENDER_NAME', '') or '').strip()
    if sender_name:
        payload['sendername'] = sender_name[:11]

    if (message or '').strip().upper().startswith('TEST'):
        logger.warning(
            'Semaphore drops outbound SMS when the message starts with TEST; '
            'delivery may not occur for trigger_event=%s',
            sms_log.trigger_event,
        )

    response = None
    last_request_error = None
    for attempt in range(1, retry_attempts + 1):
        try:
            response = requests.post(send_url, data=payload, timeout=send_timeout)
            last_request_error = None
            break
        except requests.Timeout as req_err:
            # Do not retry on read/connect timeout — Semaphore may already have accepted the SMS.
            last_request_error = req_err
            logger.warning(
                'Semaphore %s queue timed out for %s (attempt %s/%s): %s',
                queue_label,
                phone_number,
                attempt,
                retry_attempts,
                req_err,
            )
            break
        except requests.ConnectionError as req_err:
            last_request_error = req_err
            logger.warning(
                'Semaphore %s queue connection error for %s (attempt %s/%s): %s',
                queue_label,
                phone_number,
                attempt,
                retry_attempts,
                req_err,
            )
            if attempt < retry_attempts:
                time.sleep(retry_backoff * attempt)
        except requests.RequestException as req_err:
            last_request_error = req_err
            logger.warning(
                'Semaphore %s queue request failed for %s (attempt %s/%s): %s',
                queue_label,
                phone_number,
                attempt,
                retry_attempts,
                req_err,
            )
            break

    try:
        if response is None:
            raise Exception(f'Unable to reach Semaphore after {retry_attempts} attempt(s): {last_request_error}')

        if response.status_code >= 400:
            raise Exception(f'Semaphore HTTP {response.status_code}: {response.text[:500]}')

        try:
            data = response.json()
        except ValueError:
            raise Exception(f'Semaphore non-JSON response HTTP {response.status_code}: {response.text[:500]}')

        if isinstance(data, list):
            if not data:
                raise Exception('Semaphore returned an empty message list')
            item = data[0]
        elif isinstance(data, dict):
            if data.get('message_id') is not None or data.get('recipient'):
                item = data
            else:
                err = data.get('message') or data.get('error') or response.text
                raise Exception(f'Semaphore error: {err}')
        else:
            raise Exception(f'Unexpected Semaphore response: {data!r}')

        message_id = item.get('message_id')
        external_id = str(message_id) if message_id is not None else ''
        provider_status = (item.get('status') or '').strip().lower()

        terminal_failed = {'failed', 'refunded'}
        if provider_status in terminal_failed:
            sms_log.status = 'failed'
            sms_log.external_id = external_id
            sms_log.error_message = f'Semaphore status: {item.get("status")}. Network={item.get("network")!r}'
            sms_log.save(update_fields=['status', 'external_id', 'error_message'])
            logger.error(
                'Semaphore SMS failed — message_id=%s status=%s',
                external_id,
                item.get('status'),
            )
            return False

        sms_log.status = 'sent'
        sms_log.external_id = external_id
        sms_log.error_message = (
            f'Semaphore status: {item.get("status") or "unknown"}. '
            f'Network={item.get("network")!r}'
        )
        sms_log.save(update_fields=['status', 'external_id', 'error_message'])
        logger.info(
            'Semaphore SMS accepted (%s queue) — message_id=%s status=%s',
            queue_label,
            external_id,
            item.get('status'),
        )
        return True

    except Exception as e:
        raw_error = str(e)
        error_msg = raw_error if raw_error.startswith('Semaphore ') else f'Semaphore error: {raw_error}'
        logger.error(error_msg)
        sms_log.status = 'failed'
        sms_log.error_message = error_msg
        sms_log.save(update_fields=['status', 'error_message'])
        return False
