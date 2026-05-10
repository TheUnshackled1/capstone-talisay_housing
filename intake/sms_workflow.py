"""
Central definitions for Module 1→2 SMS helpers (Hiligaynon) and SMSLog trigger keys.

- Intake archive handoff: ``proceed_evaluation`` via ``message_proceed_to_evaluation``.
- Applications **Proceed to Ready for Form queue** sends ``ready_for_form_queue_reminder``
  (``message_ready_for_form_queue_reminder``). Dedupe for that event only for repeat clicks.

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
READY_FOR_FORM_QUEUE_REMINDER = 'ready_for_form_queue_reminder'


def _tha_ref_name_header(applicant) -> str:
    """
    Opening line: always includes Ref#; adds applicant full name when present (never drops ref).
    """
    ref = (getattr(applicant, 'reference_number', None) or '').strip() or 'N/A'
    name = (getattr(applicant, 'full_name', None) or '').strip()
    if name:
        return f'THA Ref# {ref} — {name}'
    return f'THA Ref# {ref}'


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


def message_ready_for_form_queue_reminder(applicant) -> str:
    """
    Hiligaynon Go to Form reminder — sent when staff clicks **Proceed to Ready for Form queue**
    on the Application & Evaluation list (``applications.views.proceed_to_form_queue``).
    """
    head = _tha_ref_name_header(applicant)
    return (
        f'{head}: Ang imo aplikasyon yara sa Form Generation magahulat nalang kita sang ila nga perma nga ini paga permahan sang mga opisyales na nagahulugan sang eligibility '
        f'Mag-hulat sang updates ukon magdu-aw sa Talisay Housing Authority kon kinahanglan. Salamat!'
    )


def message_proceed_to_evaluation(applicant) -> str:
    """
    Hiligaynon handoff SMS toward Application & Eligibility.

    Triggered from Intake archive/proceed only (Module 1 handoff). Body reflects Applicant Situation
    (A–D) or a fallback when ``displacement_reason`` is unset.
    """
    head = _tha_ref_name_header(applicant)
    dr = getattr(applicant, 'displacement_reason', None) or ''
    base = (
        f'{head}: Ang imo registration yara na sa evaluation stage. '
        f'Nabaton na namon ang imo mga dokumento. '
    )
    situation = _situation_clause_proceed_sms(dr)
    closing = 'Mag-hulat sang updates para sa eligibility. Salamat!'
    return f'{base}{situation}{closing}'
