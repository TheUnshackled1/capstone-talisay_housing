"""
Central definitions for Module 1→2 SMS helpers (Hiligaynon) and SMSLog trigger keys.

- Intake **Proceed to LIST OF APPLICANTS**: ``proceed_applicant_list`` via ``message_proceed_to_applicant_list``.
- Intake Module 2 handoff (checklist): ``proceed_evaluation`` via ``message_proceed_to_evaluation``.
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
PROCEED_TO_APPLICANT_LIST = 'proceed_applicant_list'
READY_FOR_FORM_QUEUE_REMINDER = 'ready_for_form_queue_reminder'
PROCEED_TO_LOT_AWARDING = 'proceed_to_lot_awarding'


def _tha_ref_name_header(applicant) -> str:
    """
    Opening line: always includes Ref#; adds applicant full name when present (never drops ref).
    """
    ref = (getattr(applicant, 'reference_number', None) or '').strip() or 'N/A'
    name = (getattr(applicant, 'full_name', None) or '').strip()
    if name:
        return f'THA Ref# {ref} — {name}'
    return f'THA Ref# {ref}'


def _applicant_has_isf_situational_on_file(applicant) -> bool:
    """True when ISF-SIT / isf_situational_docs is already in the document vault."""
    if applicant is None:
        return False
    try:
        return applicant.documents.filter(document_type='isf_situational_docs').exists()
    except Exception:
        return False


def _situation_clause_proceed_sms(displacement_reason: str, *, has_isf_situational: bool = False) -> str:
    """
    Hiligaynon add-on by Applicant Situation (Module 1 Layer 3 / displacement_reason).

    Options B/C: when ISF-SIT is already on file, omit the extra “submit required documentation”
    reminder (baseline scans are complete and situational docs were filed).
    """
    dr = (displacement_reason or '').strip()
    if dr == 'danger_zone':
        return (
            'Basi sa imo Applicant Situation (Option A — Resident sang Danger Zone/Hazard Area): '
            'naga-ukoy ka sa hazard area. I-check ka namon paagi sa amon Ronda para sa photo verification. '
        )
    if dr == 'ejected':
        intro = (
            'Basi sa imo Applicant Situation (Option B — Gin-eject ukon gin-displace gikan sa imo nagligad nga puluy-an). '
        )
        if has_isf_situational:
            return intro
        return (
            intro
            + 'Magasumiter ka sang Required Documentation: Court Order, Legal Office Certification, or Barangay Certification. '
        )
    if dr == 'relocated':
        intro = (
            'Basi sa imo Applicant Situation (Option C — Gin-displace tungod sa proyekto o imprastraktura sang gobyerno). '
        )
        if has_isf_situational:
            return intro
        return (
            intro
            + 'Magasumiter ka sang imo Required Documentation: Notice of Relocation, Right-of-Way Documentation, or Project Order. '
        )
    if dr == 'not_abc':
        return (
            'Basi sa imo Applicant Situation (Option D — Wala sa A, B, ukon C / lain nga sitwasyon): '
            'Ang imo kaso indi sakop sang danger zone, ejection, ukon government project. '
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


# Baseline checklist codes (R01–R07, RVT) — listed by document name only (no R01/R02 codes in SMS).
_BASELINE_APPLICANT_LIST_SMS_CODES = frozenset({
    'R01', 'R02', 'R03', 'R04', 'R05', 'R06', 'R07', 'RVT',
})
_SITUATIONAL_CHECKLIST_CODES = frozenset({'CDRRMO', 'ISF-SIT'})


def _applicant_list_situational_sms_clause(code: str, displacement_reason: str) -> str:
    """
    Hiligaynon last line(s) on LIST OF APPLICANTS SMS — which documents / situational items to prepare.

    Different from ``_situation_clause_proceed_sms`` (evaluation handoff: Ronda, next steps after
  scans are filed). Do not merge the two; applicants may receive both SMS at different times.
    """
    c = (code or '').strip().upper()
    dr = (displacement_reason or '').strip()
    if dr == 'not_abc':
        return _situation_clause_proceed_sms(dr).strip()
    if c == 'CDRRMO' or dr == 'danger_zone':
        return (
            'INI NGA DOKYUMENTO ANG CDRRMO MAGA PROVIDE SANG CERTIFIKASYON! '
            'Option A — Resident of Danger Zone or Hazard Area — CDRRMO certification.'
        )
    if c == 'ISF-SIT' and dr == 'ejected':
        return (
            'Magasumiter sang imo situational nga dokumento para sa Option B — '
            'Ejected or Evicted from Prior Residence (ISF situational documentation).'
        )
    if c == 'ISF-SIT' and dr == 'relocated':
        return (
            'Magasumiter sang imo situational nga dokumento para sa Option C — '
            'Displaced by Government Project or Infrastructure (ISF situational documentation).'
        )
    if c == 'ISF-SIT':
        return 'Magasumiter sang imo ISF situational documentation sunod sa imo Applicant Situation.'
    return ''


def message_proceed_to_applicant_list(applicant, checklist_rows) -> str:
    """
    Hiligaynon SMS when staff archives a record to LIST OF APPLICANTS (review modal).

    Baseline requirements (R01–R07, RVT) appear as document names only; situational follow-up
    uses Hiligaynon clauses when Applicant Situation is A, B, C, or D.
    """
    head = _tha_ref_name_header(applicant)
    dr = getattr(applicant, 'displacement_reason', None) or ''
    baseline_names = []
    situational_parts = []
    seen_situational = set()
    for row in checklist_rows or []:
        code = ((row.get('code') if isinstance(row, dict) else getattr(row, 'code', '')) or '').strip().upper()
        name = ((row.get('name') if isinstance(row, dict) else getattr(row, 'name', '')) or '').strip()
        if code in _BASELINE_APPLICANT_LIST_SMS_CODES:
            if name:
                baseline_names.append(name)
            continue
        if code in _SITUATIONAL_CHECKLIST_CODES:
            clause = _applicant_list_situational_sms_clause(code, dr)
            if clause and clause not in seen_situational:
                seen_situational.add(clause)
                situational_parts.append(clause)
    if not situational_parts:
        clause = _applicant_list_situational_sms_clause('', dr)
        if clause and clause not in seen_situational:
            situational_parts.append(clause)

    doc_parts = list(baseline_names)
    doc_parts.extend(situational_parts)
    if not doc_parts:
        doc_parts = [
            'Brgy. Certificate of Residency',
            'Brgy. Certificate of Indigency',
            'Cedula',
            'Police Clearance',
            'Certificate of No Property',
            '2x2 Picture',
            'Sketch of House Location',
            'Voter Certification (COMELEC / Barangay voter record)',
        ]

    checklist = '\n'.join(doc_parts)
    return (
        f'{head}: Ari kana subong sa LISTA sang mga aplikante.\n'
        f'Dal-a ang masunod nga mga dokumento:\n'
        f'{checklist}\n'
        f'Salamat!'
    )


def message_proceed_to_evaluation(applicant) -> str:
    """
    Hiligaynon handoff SMS toward Application & Eligibility.

    Triggered when staff promotes to Module 2 from the document checklist (``promote_to_module2``).
    Uses ``_situation_clause_proceed_sms`` for next steps — not the document list from LIST SMS.
    """
    head = _tha_ref_name_header(applicant)
    dr = (getattr(applicant, 'displacement_reason', None) or '').strip()
    has_isf = dr in ('ejected', 'relocated') and _applicant_has_isf_situational_on_file(applicant)
    base = (
        f'{head}: Ang imo registration yara na sa evaluation stage. '
        f'Nabaton na namon ang imo mga dokumento. '
    )
    situation = _situation_clause_proceed_sms(dr, has_isf_situational=has_isf)
    if has_isf:
        return f'{base}{situation}'
    closing = 'Mag-hulat sang updates para sa eligibility. Salamat!'
    return f'{base}{situation}{closing}'


def format_orientation_schedule(when) -> str:
    """Human-readable orientation schedule for SMS (local time)."""
    from django.utils import timezone as tz

    if when is None:
        return ''
    local = tz.localtime(when) if tz.is_aware(when) else when
    time_part = local.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
    return f'{local.strftime("%B %d, %Y")}, {time_part}'


def lot_awarding_notify_body(*, orientation_at=None) -> str:
    """
    Core Hiligaynon body for lot-awarding / orientation SMS (no THA header, no name suffix).
    When orientation_at is set, include the schedule instead of “wait for schedule”.
    """
    if orientation_at:
        when_label = format_orientation_schedule(orientation_at)
        return (
            'Congratulations! Pirmanado na ang imo forms. Ikaw ang assignan na sang lot. '
            f'Ang inyo orientasyon sa {when_label}. Salamat!'
        )
    return (
        'Congratulations! Pirmanado na ang imo forms. Ikaw ang assignan na sang lot. '
        'Maghulat sang schedule para sa inyo orientasyon. Salamat!'
    )


def message_proceed_to_lot_awarding(applicant, *, orientation_at=None) -> str:
    """
    Hiligaynon lot-awarding notification.
    Fits in a single SMS (160 chars) if head is standard length.
    """
    head = _tha_ref_name_header(applicant)
    return f'{head}: {lot_awarding_notify_body(orientation_at=orientation_at)}'
