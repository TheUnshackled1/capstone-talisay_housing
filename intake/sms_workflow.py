"""
Central definitions for Module 1→2 proceed-to-evaluation SMS (Hiligaynon) and its SMSLog trigger key.

Typical sends: Intake ``proceed_to_applications`` and/or Applications ``proceed_to_form_queue``
(the **Proceed to Application & Eligibility** action on the Application & Evaluation list). The
latter skips sending if this event already logged ``sent`` in Intake or Applications ``SMSLog``.

Delivery is not implemented here. All sends go through ``intake.utils.send_sms`` (and the applications
wrapper that forwards to it with ``module='applications'``), which reads Django settings:

Developer console (default)
    Set ``SMS_SERVICE=console`` in ``.env`` (see ``.env.example``). Runserver prints the full SMS
    (recipient, event, body) and writes ``SMSLog`` with simulated delivery — no API key.

Semaphore (production / staging)
    Set ``SMS_SERVICE=semaphore``, ``SMS_ENABLED=True``, and ``SEMAPHORE_API_KEY`` from
    https://semaphore.co/docs — optional ``SEMAPHORE_SENDER_NAME`` (≤11 chars). In ``DEBUG``,
    missing API key falls back to console simulation. Do not start the message body with the word
    ``TEST`` if you expect Semaphore to transmit it (provider ignores those).

Smoke test: ``python manage.py test_sms --phone 09123456789 --service console`` (or ``semaphore``).
"""

# --- trigger_event values (keep ≤ 50 chars; indexed in SMSLog) ---
PROCEED_TO_EVALUATION = 'proceed_evaluation'


def _situation_clause_proceed_sms(displacement_reason: str) -> str:
    """
    Hiligaynon add-on by Applicant Situation (Module 1 Layer 3 / displacement_reason).
    """
    dr = (displacement_reason or '').strip()
    if dr == 'danger_zone':
        return (
            'Basi sa imo Applicant Situation (Option A — Resident sang Danger Zone/Hazard Area): '
            'naga-ukoy ka sa hazard area. I-check ka namon paagi sa amon Ronda para sa photo verification. '
        )
    if dr == 'ejected':
        return (
            'Basi sa imo Applicant Situation (Option B — Gin-eject ukon gin-displace gikan sa imo nagligad nga puluy-an). '
            'Magasumiter ka sang Required Documentation: Court Order, Legal Office Certification, or Barangay Certification. '
        )
    if dr == 'relocated':
        return (
            'Basi sa imo Applicant Situation (Option C — Gin-displace tungod sa proyekto o imprastraktura sang gobyerno). '
            'Magasumiter ka sang imo Required Documentation: Notice of Relocation, Right-of-Way Documentation, or Project Order. '
        )
    if dr == 'not_abc':
        return (
            'Basi sa imo Applicant Situation (Option D — Wala sa A, B, ukon C / lain nga sitwasyon). '
        )
    return (
        'Wala pa nakuha ang imo Applicant Situation (A–D) sa rekordo, ukon wala pa ini mat-ud. '
        'Palihog magdu-aw sa Talisay Housing Authority intake para ma-update ang imo kaso. '
    )


def message_proceed_to_evaluation(applicant) -> str:
    """
    Hiligaynon handoff SMS toward Application & Eligibility.

    Triggered from Intake archive/proceed or from Applications when routing to Ready for Form
    (see ``applications.views.proceed_to_form_queue``). Body reflects Applicant Situation (A–D) or a
    fallback when ``displacement_reason`` is unset.
    """
    ref = applicant.reference_number
    dr = getattr(applicant, 'displacement_reason', None) or ''
    base = (
        f'THA {ref}: Ang imo registration yara na sa evaluation stage. '
        f'Nabaton na namon ang imo mga dokumento. '
    )
    situation = _situation_clause_proceed_sms(dr)
    closing = 'Mag-hulat sang updates para sa eligibility. Salamat!'
    return f'{base}{situation}{closing}'
