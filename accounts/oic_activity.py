"""
OIC dashboard: cross-module recent activity from intake, applications, field desk, and cases.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from applications.models import Application, FieldVerificationPhoto
from cases.models import Case, CaseAction
from documents.models import Document
from intake.models import Applicant, Archive
from units.models import Blacklist, LotAward, MonitoringReport

OIC_ACTIVITY_STAFF_POSITIONS = frozenset({
    'second_member',
    'fourth_member',
    'ronda',
    'field',
})

OIC_ACTIVITY_PAGE_SIZE = 10
OIC_ACTIVITY_MAX_ITEMS = 50


def paginate_oic_activity(items: list, page_size: int = OIC_ACTIVITY_PAGE_SIZE) -> list[list]:
    """Split activity feed into fixed-size pages for the OIC dashboard carousel."""
    if not items:
        return []
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]


def _relative_time_ago(dt) -> str:
    if not dt:
        return ''
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return 'just now'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    hours = minutes // 60
    if hours < 24:
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    days = hours // 24
    if days < 30:
        return f'{days} day{"s" if days != 1 else ""} ago'
    return timezone.localtime(dt).strftime('%b %d, %Y')


def _staff_in_scope(user) -> bool:
    return bool(user and getattr(user, 'position', None) in OIC_ACTIVITY_STAFF_POSITIONS)


def _staff_display(user) -> tuple[str, str]:
    if not user:
        return ('Staff', '')
    name = user.get_full_name() or 'Staff'
    role = (
        user.get_position_display_short()
        if hasattr(user, 'get_position_display_short')
        else (user.get_position_display() if hasattr(user, 'get_position_display') else '')
    )
    return (name, role)


def _push_event(events, *, at, title, detail, module, user) -> None:
    if not at or not _staff_in_scope(user):
        return
    staff_name, staff_role = _staff_display(user)
    events.append({
        'at': at,
        'title': title,
        'detail': detail,
        'module': module,
        'staff_name': staff_name,
        'staff_role': staff_role,
        'ago': _relative_time_ago(at),
    })


def build_oic_recent_activity(limit: int = 50) -> list[dict]:
    """Merge recent staff actions across Module 1–5 for the OIC dashboard feed."""
    events: list[dict] = []
    cutoff = timezone.now() - timedelta(days=120)

    for applicant in (
        Applicant.objects.filter(created_at__gte=cutoff)
        .select_related('registered_by')
        .order_by('-created_at')[:120]
    ):
        _push_event(
            events,
            at=applicant.created_at,
            title='Applicant registered',
            detail=f'{applicant.full_name} · {applicant.reference_number}',
            module='Intake · 2nd / 4th Member',
            user=applicant.registered_by,
        )

    for applicant in (
        Applicant.objects.filter(module2_handoff_at__gte=cutoff)
        .select_related('module2_handoff_by')
        .order_by('-module2_handoff_at')[:80]
    ):
        _push_event(
            events,
            at=applicant.module2_handoff_at,
            title='Handoff to Application & Eligibility',
            detail=f'{applicant.full_name} · {applicant.reference_number}',
            module='Applications · 2nd / 4th Member',
            user=applicant.module2_handoff_by,
        )

    for applicant in (
        Applicant.objects.filter(form_queue_routed_at__gte=cutoff)
        .select_related('form_queue_routed_by')
        .order_by('-form_queue_routed_at')[:60]
    ):
        _push_event(
            events,
            at=applicant.form_queue_routed_at,
            title='Routed to Ready for Form queue',
            detail=applicant.full_name,
            module='Applications · 2nd / 4th Member',
            user=applicant.form_queue_routed_by,
        )

    for archive in (
        Archive.objects.filter(archived_at__gte=cutoff)
        .select_related('archived_by')
        .order_by('-archived_at')[:100]
    ):
        _push_event(
            events,
            at=archive.archived_at,
            title='Proceeded to LIST OF APPLICATIONS',
            detail=f'{archive.full_name_snapshot} · {archive.reference_number_snapshot}',
            module='Intake · 2nd / 4th Member',
            user=archive.archived_by,
        )

    for app in (
        Application.objects.filter(form_generated_at__gte=cutoff)
        .select_related('form_generated_by', 'applicant')
        .order_by('-form_generated_at')[:80]
    ):
        _push_event(
            events,
            at=app.form_generated_at,
            title='Housing application form generated',
            detail=f'{app.application_number} · {app.applicant.full_name}',
            module='Applications · 2nd / 4th Member',
            user=app.form_generated_by,
        )

    for award in (
        LotAward.objects.filter(awarded_at__gte=cutoff)
        .select_related('awarded_by', 'application__applicant', 'unit')
        .order_by('-awarded_at')[:80]
    ):
        unit = award.unit
        applicant = award.application.applicant
        loc = f'Block {unit.block_number}, Lot {unit.lot_number}'
        _push_event(
            events,
            at=award.awarded_at,
            title='Lot awarded',
            detail=f'{loc} · {applicant.full_name}',
            module='Applications · 2nd / 4th Member',
            user=award.awarded_by,
        )

    for doc in (
        Document.objects.filter(uploaded_at__gte=cutoff)
        .select_related('uploaded_by', 'applicant')
        .order_by('-uploaded_at')[:60]
    ):
        dtype = doc.get_document_type_display() if hasattr(doc, 'get_document_type_display') else doc.document_type
        _push_event(
            events,
            at=doc.uploaded_at,
            title='Document filed',
            detail=f'{dtype} · {doc.applicant.full_name}',
            module='Documents · 2nd / 4th Member',
            user=doc.uploaded_by,
        )

    for case in (
        Case.objects.filter(received_at__gte=cutoff)
        .select_related('received_by', 'complainant_applicant')
        .order_by('-received_at')[:80]
    ):
        name = case.complainant_name or (
            case.complainant_applicant.full_name if case.complainant_applicant else '—'
        )
        _push_event(
            events,
            at=case.received_at,
            title='Case recorded',
            detail=f'{case.case_number} · {name}',
            module='Cases · 2nd Member',
            user=case.received_by,
        )

    for action in (
        CaseAction.objects.filter(created_at__gte=cutoff)
        .select_related('created_by', 'case')
        .order_by('-created_at')[:60]
    ):
        label = (
            action.get_action_type_display()
            if hasattr(action, 'get_action_type_display')
            else action.action_type
        )
        _push_event(
            events,
            at=action.created_at,
            title=f'Case action: {label}',
            detail=action.case.case_number,
            module='Cases · 2nd Member',
            user=action.created_by,
        )

    for photo in (
        FieldVerificationPhoto.objects.filter(uploaded_at__gte=cutoff)
        .select_related('uploaded_by', 'certification__applicant')
        .order_by('-uploaded_at')[:40]
    ):
        applicant = photo.certification.applicant
        _push_event(
            events,
            at=photo.uploaded_at,
            title='Field verification photo uploaded',
            detail=f'{applicant.full_name} · danger-zone evidence',
            module='Field verification desk',
            user=photo.uploaded_by,
        )

    for report in (
        MonitoringReport.objects.filter(submitted_at__gte=cutoff)
        .select_related('submitted_by', 'unit', 'lot_award__application__applicant')
        .order_by('-submitted_at')[:60]
    ):
        applicant = report.lot_award.application.applicant
        unit = report.unit
        _push_event(
            events,
            at=report.submitted_at,
            title='Unit monitoring report submitted',
            detail=(
                f'Block {unit.block_number}, Lot {unit.lot_number} · '
                f'{applicant.full_name}'
            ),
            module='Field verification desk',
            user=report.submitted_by,
        )

    for entry in (
        Blacklist.objects.filter(blacklisted_at__gte=cutoff)
        .select_related('blacklisted_by', 'applicant')
        .order_by('-blacklisted_at')[:30]
    ):
        _push_event(
            events,
            at=entry.blacklisted_at,
            title='Beneficiary blacklisted',
            detail=entry.applicant.full_name,
            module='Property custodian · 4th Member',
            user=entry.blacklisted_by,
        )

    events.sort(key=lambda row: row['at'], reverse=True)
    return events[:limit]
