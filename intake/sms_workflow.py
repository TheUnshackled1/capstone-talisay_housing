"""
Central definitions for SMS trigger_event keys and message bodies (Module 1).

Use these from views so workflow buttons map to consistent audit entries in SMSLog.
When SMS_SERVICE=console, messages are still written to SMSLog and logged — no paid API required.
"""

# --- trigger_event values (keep ≤ 50 chars; indexed in SMSLog) ---
REGISTRATION = 'registration'
ELIGIBILITY = 'eligibility'
ELIGIBILITY_PASSED = 'eligibility_passed'
ELIGIBILITY_FAIL = 'eligibility_fail'
CDRRMO_CERTIFIED = 'cdrrmo_certified'
CDRRMO_NOT_CERTIFIED = 'cdrrmo_not_certified'
CDRRMO_OFFICE_CERTIFIED = 'cdrrmo_office_certified'
FIELD_VERIFICATION_CERTIFIED = 'field_verification_certified'
FIELD_VERIFICATION_NOT_CERTIFIED = 'field_verification_not_certified'


def message_cdrrmo_certified_priority(applicant, queue_position: int) -> str:
    return (
        f'THA: Your hazard-area certification is on file. Priority queue no. {queue_position}. '
        f'Ref {applicant.reference_number}. Please visit the Talisay Housing Authority for next steps.'
    )


def message_cdrrmo_office_received(applicant, queue_position: int) -> str:
    return (
        f'THA: Official CDRRMO certification was received and filed at our intake office. '
        f'Priority queue no. {queue_position}. Ref {applicant.reference_number}. '
        f'Please visit the Talisay Housing Authority when instructed for next steps.'
    )


def message_cdrrmo_not_certified(applicant) -> str:
    return (
        f'THA: Your hazard-area claim could not be certified under current CDRRMO rules. '
        f'Ref {applicant.reference_number}. You may visit the Talisay Housing Authority for more information.'
    )


def message_field_inspection_sustained(applicant) -> str:
    return (
        f'THA Module 1: Field inspection supports your declared hazard-area classification. '
        f'Ref {applicant.reference_number}. Intake will complete supervisory review; await further SMS or office advice.'
    )


def message_field_inspection_not_sustained(applicant) -> str:
    return (
        f'THA Module 1: Field inspection did not sustain hazard-area status for your declared address. '
        f'Ref {applicant.reference_number}. Intake will update your record; you may visit THA for clarification.'
    )
