from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Prefetch
from django.http import JsonResponse, HttpResponse, Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_http_methods, require_POST
from collections import defaultdict
from functools import wraps
import json
import mimetypes
import os
from uuid import UUID
from intake.models import Applicant
from units.models import LotAward, MonitoringReport, Blacklist
from applications.models import QueueEntry
from applications.staff_pipeline_status import staff_pipeline_primary_detail
from documents.models import (
    Document,
    DocumentBlob,
    RequirementSubmission,
)
from applications.form_pipeline import applicant_has_signed_application_payload

DOCUMENTS_MANAGEMENT_PER_PAGE = 10

# Vault drawer type_key → intake upload_scanned_requirement (doc_key, requirement code).
VAULT_TYPE_TO_INTAKE_DOC = {
    'barangay_residency': ('doc_brgy_residency', 'R01'),
    'barangay_indigency': ('doc_brgy_indigency', 'R02'),
    'cedula': ('doc_cedula', 'R03'),
    'police_clearance': ('doc_police_clearance', 'R04'),
    'no_property': ('doc_no_property', 'R05'),
    'photo_2x2': ('doc_2x2_picture', 'R06'),
    'house_sketch': ('doc_sketch_location', 'R07'),
    'voter_certification': ('doc_voter_cert', 'RVT'),
    'signed_application': ('doc_signed_application', 'SIGNED'),
    'cdrrmo_cert': ('doc_cdrrmo', 'CDRRMO'),
    'incident_report': ('doc_incident_report', 'INCRPT'),
    'isf_situational_docs': ('doc_isf_situational', 'ISF-SIT'),
}


def _vault_drawer_intake_fields(type_key: str | None) -> dict:
    """Optional intake_doc_key / intake_doc_code for drawer Upload & Scan buttons."""
    if not type_key:
        return {}
    pair = VAULT_TYPE_TO_INTAKE_DOC.get(type_key)
    if not pair:
        return {}
    return {'intake_doc_key': pair[0], 'intake_doc_code': pair[1]}


def _vault_blob_view_url(
    type_key: str | None,
    on_file: bool,
    latest_doc_by_type: dict | None,
    position: str | None,
) -> str | None:
    if not on_file or not type_key or not position or not latest_doc_by_type:
        return None
    doc_id = latest_doc_by_type.get(type_key)
    if not doc_id:
        return None
    return reverse(
        'documents:blob_download',
        kwargs={'position': position, 'doc_id': doc_id},
    )


def _ronda_verification_photos_view_urls(applicant: Applicant, request) -> list[str]:
    """
    Absolute URLs for each FieldVerificationPhoto (oldest first → View 1, View 2, …).
    Same media URLs as Application & Eligibility.
    """
    if not request:
        return []
    cert = getattr(applicant, 'cdrrmo_certification', None)
    if not cert:
        return []
    out: list[str] = []
    for ph in cert.field_photos.exclude(image='').filter(image__isnull=False).order_by(
        'uploaded_at', 'id'
    ):
        if not ph.image:
            continue
        try:
            out.append(request.build_absolute_uri(ph.image.url))
        except (ValueError, AttributeError):
            continue
    return out


def _display_date(value) -> str:
    if not value:
        return '—'
    return date_format(value, 'F j, Y')


def _display_datetime(value) -> str:
    if not value:
        return '—'
    return date_format(timezone.localtime(value), 'F j, Y')


def _monitoring_photo_urls(report: MonitoringReport, request) -> list[str]:
    urls: list[str] = []
    for photo in report.photos.all():
        if not photo.image:
            continue
        try:
            urls.append(request.build_absolute_uri(photo.image.url))
        except (ValueError, AttributeError):
            continue
    if not urls and report.photo_evidence:
        try:
            urls.append(request.build_absolute_uri(report.photo_evidence.url))
        except (ValueError, AttributeError):
            pass
    return urls


def _monitoring_report_document_item(report: MonitoringReport, request) -> dict:
    task = report.task
    unit = report.unit
    lot_label = f"Block {unit.block_number}, Lot {unit.lot_number}"
    task_label = task.get_task_type_display() if task else 'Monitoring report'
    photo_urls = _monitoring_photo_urls(report, request)

    return {
        'type_key': f'monitoring_report_{report.id}',
        'label': f'{task_label} ({_display_date(task.due_date if task else None)})',
        'group_label': 'Post-award monitoring reports',
        'on_file': True,
        'badge_text': 'Completed',
        'is_monitoring_report': True,
        'report': {
            'title': task_label,
            'unit': lot_label,
            'monitoring_day': task.days_from_award if task else '',
            'due_date': _display_date(task.due_date if task else None),
            'submitted_at': _display_datetime(report.submitted_at),
            'submitted_by': report.submitted_by.get_full_name() or report.submitted_by.username if report.submitted_by else '—',
            'occupancy_status': report.get_occupancy_status_display(),
            'occupancy_notes': report.occupancy_notes or '—',
            'construction_status': report.get_construction_status_display(),
            'percent_complete': f'{report.percent_complete}%',
            'progress_notes': report.progress_notes or '—',
            'general_remarks': report.general_remarks or '—',
            'assessment': report.get_progress_assessment_display() if report.progress_assessment else 'Awaiting staff decision',
            'assessed_by': report.assessed_by.get_full_name() or report.assessed_by.username if report.assessed_by else '—',
            'assessed_at': _display_datetime(report.assessed_at),
            'photo_urls': photo_urls,
        },
    }


def _build_situation_vault_block(
    applicant: Applicant,
    types_set: set,
    *,
    latest_doc_by_type: dict | None = None,
    position: str | None = None,
    request=None,
) -> dict:
    """
    Vault drawer: Applicant Situation (Options A–D) summary + situation-specific slots.

    Option A: CDRRMO cert (vault); inspection report as vault ``Document(incident_report)``;
    Ronda/CDRRMO on-site verification photos on FieldVerificationPhoto (not vault Documents).

    Options B/C: single ISF situational documentation bundle (isf_situational_docs).

    Option D: message only, no extra checklist rows.
    """
    dr = (getattr(applicant, 'displacement_reason', None) or '').strip()

    option_a_blurb = (
        'Applicant resides in a flood-prone, landslide, storm-surge, riverbank, '
        'cliff-edge, or coastal hazard area requiring relocation for safety.'
    )
    option_b_blurb = (
        'Applicant has been evicted or displaced through private land eviction, court order, '
        'landowner recovery, or analogous proceedings.'
    )
    option_c_blurb = (
        'Applicant is required to relocate due to a road-widening, drainage, infrastructure, '
        'or other government-initiated project.'
    )
    option_d_blurb = (
        'The situation does not fall under a hazard area, ejection, or a government project. '
        'The applicant is recorded for the walk-in path (no priority on this ground).'
    )

    def _dz_detail(applicant):
        zt = (applicant.danger_zone_type or '').strip()
        loc = (applicant.danger_zone_location or '').strip()
        zt_disp = zt.replace('_', ' ').title() if zt else ''
        parts = [p for p in (zt_disp, loc) if p]
        return ' · '.join(parts) if parts else '—'

    if dr == 'danger_zone':
        cert = getattr(applicant, 'cdrrmo_certification', None)
        has_cdrrmo = ('cdrrmo_cert' in types_set) or bool(
            cert and getattr(cert, 'status', '') == 'certified'
        )
        has_inspection_report = 'incident_report' in types_set
        inspection_note = (
            'Written or scanned inspection report on file in this vault.'
            if has_inspection_report
            else (
                'No inspection report in the vault yet. Upload the written or scanned '
                'report here (Inspection Report), or complete the site-inspection workflow in Application & Eligibility.'
            )
        )
        n_ronda = 0
        if cert:
            n_ronda = cert.field_photos.count()
        has_ronda_photos = n_ronda > 0
        ronda_note = (
            f'{n_ronda} on-site photo(s) on file.'
            if has_ronda_photos
            else 'No on-site verification photos yet.'
        )
        ronda_view_urls = (
            _ronda_verification_photos_view_urls(applicant, request)
            if has_ronda_photos
            else []
        )
        return {
            'letter': 'A',
            'title': 'Option A — Resident of Danger Zone or Hazard Area',
            'blurb': option_a_blurb,
            'detail_line': _dz_detail(applicant),
            'option_d_message': None,
            'rows': [
                {
                    'slot_id': 'cdrrmo_cert',
                    'label': 'CDRRMO certification',
                    'kind': 'document',
                    'on_file': has_cdrrmo,
                    'type_key': 'cdrrmo_cert',
                    'add_file': not has_cdrrmo,
                    'note': '',
                    'view_url': _vault_blob_view_url(
                        'cdrrmo_cert', has_cdrrmo, latest_doc_by_type, position
                    ),
                    **_vault_drawer_intake_fields('cdrrmo_cert'),
                },
                {
                    'slot_id': 'inspection_report',
                    'label': 'Inspection report (field / Ronda site visit)',
                    'kind': 'document',
                    'on_file': has_inspection_report,
                    'type_key': 'incident_report',
                    'add_file': not has_inspection_report,
                    'note': inspection_note,
                    'view_url': _vault_blob_view_url(
                        'incident_report',
                        has_inspection_report,
                        latest_doc_by_type,
                        position,
                    ),
                    **_vault_drawer_intake_fields('incident_report'),
                },
                {
                    'slot_id': 'ronda_verification',
                    'label': 'Ronda on-site verification (photos)',
                    'kind': 'image',
                    'on_file': has_ronda_photos,
                    'type_key': None,
                    'add_file': False,
                    'note': ronda_note,
                    'view_url': None,
                    'view_urls': ronda_view_urls,
                },
            ],
        }

    if dr == 'ejected':
        et = ''
        if getattr(applicant, 'ejection_type', None):
            try:
                et = applicant.get_ejection_type_display()
            except Exception:
                et = str(applicant.ejection_type)
        ed = applicant.ejection_date
        ed_s = ed.strftime('%Y-%m-%d') if ed else ''
        detail_bits = [b for b in (et, f'Date: {ed_s}' if ed_s else '') if b]
        detail = ' · '.join(detail_bits) if detail_bits else '—'
        has_isf = 'isf_situational_docs' in types_set
        return {
            'letter': 'B',
            'title': 'Option B — Ejected or Evicted from Prior Residence',
            'blurb': option_b_blurb,
            'detail_line': detail,
            'option_d_message': None,
            'rows': [
                {
                    'slot_id': 'isf_ejection',
                    'label': (
                        'Proof of ejection — court order, legal office certification, '
                        'or barangay certification (any applicable)'
                    ),
                    'kind': 'document',
                    'on_file': has_isf,
                    'type_key': 'isf_situational_docs',
                    'add_file': not has_isf,
                    'note': '',
                    'view_url': _vault_blob_view_url(
                        'isf_situational_docs', has_isf, latest_doc_by_type, position
                    ),
                    **_vault_drawer_intake_fields('isf_situational_docs'),
                },
            ],
        }

    if dr == 'relocated':
        proj = (getattr(applicant, 'project_name', None) or '').strip() or '—'
        has_isf = 'isf_situational_docs' in types_set
        return {
            'letter': 'C',
            'title': 'Option C — Displaced by Government Project or Infrastructure',
            'blurb': option_c_blurb,
            'detail_line': f'Project / work: {proj}',
            'option_d_message': None,
            'rows': [
                {
                    'slot_id': 'isf_project',
                    'label': (
                        'Proof of displacement — notice of relocation, right-of-way documentation, '
                        'or project order (any applicable)'
                    ),
                    'kind': 'document',
                    'on_file': has_isf,
                    'type_key': 'isf_situational_docs',
                    'add_file': not has_isf,
                    'note': '',
                    'view_url': _vault_blob_view_url(
                        'isf_situational_docs', has_isf, latest_doc_by_type, position
                    ),
                    **_vault_drawer_intake_fields('isf_situational_docs'),
                },
            ],
        }

    if dr == 'not_abc':
        return {
            'letter': 'D',
            'title': 'Option D — None of A, B, or C (Other / not listed)',
            'blurb': option_d_blurb,
            'detail_line': 'Walk-in path — no hazard / ejection / government-project classification.',
            'option_d_message': (
                'This applicant is not under Options A, B, or C. No situational documents or '
                'field verification items are required in this section.'
            ),
            'rows': [],
        }

    return {
        'letter': None,
        'title': 'Applicant situation not declared',
        'blurb': 'Options A–D are recorded in Application & Eligibility (displacement / situation).',
        'detail_line': '—',
        'option_d_message': None,
        'rows': [],
    }


def _normalize_blob_content_type(declared: str, filename: str) -> str:
    """Fill in a concrete MIME type when stored value is missing or octet-stream."""
    ct = (declared or '').strip()
    base = ct.split(';')[0].strip().lower() if ct else ''
    if base and base != 'application/octet-stream':
        return ct.split(';')[0].strip()
    guessed, _ = mimetypes.guess_type(os.path.basename(filename or ''))
    if guessed:
        return guessed
    return base or 'application/octet-stream'


def _signed_application_upload_file_error(file) -> str | None:
    """
    Signed application vault: PDF, Word, or plain text only — not images.
    Returns an error message if invalid, otherwise None.
    """
    name = (getattr(file, 'name', None) or '').strip()
    ext = os.path.splitext(name)[1].lower()
    allowed_ext = {'.pdf', '.doc', '.docx', '.txt'}
    ct = (getattr(file, 'content_type', None) or '').lower()
    if ct.startswith('image/'):
        return (
            'Signed application must be a PDF, Word file, or text — not an image.'
        )
    if ext in allowed_ext:
        return None
    return (
        'Signed application must be a PDF, Word document (.doc or .docx), '
        'or plain text (.txt).'
    )


def _blob_disposition_inline_ok(content_type: str, filename: str) -> bool:
    """Whether the browser can reasonably display this inline (new tab / embedded)."""
    ct = (content_type or '').split(';')[0].strip().lower()
    if ct.startswith('image/'):
        return True
    if ct in ('application/pdf', 'text/plain'):
        return True
    ext = os.path.splitext(filename or '')[1].lower()
    return ext in (
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
        '.bmp', '.tif', '.tiff',
    )


# =============================================================================
# POSITION VERIFICATION DECORATOR
# =============================================================================

def verify_position(view_func):
    """
    Decorator to verify that URL position parameter matches logged-in user's position.
    Security feature: prevents URL manipulation to access other roles' views.
    """
    @wraps(view_func)
    def wrapper(request, position, *args, **kwargs):
        # Check if position in URL matches user's actual position
        if request.user.position != position:
            messages.error(request, f'Access denied. You are logged in as {request.user.get_position_display()}, not {position.replace("_", " ")}.')
            return redirect('accounts:dashboard')
        return view_func(request, position, *args, **kwargs)
    return wrapper


@login_required
@verify_position
def document_management(request, position):
    """
    Document vault (Module 3 UI) — search and manage files per applicant.

    Includes applicants who appear on Intake LIST OF APPLICATIONS (Intake Archive exists)
    and/or have an Intake Archive (and legacy rows may still set module2_handoff_at).

    URL: /documents/<position>/management/
    """
    if not request.user.is_staff:
        messages.error(request, 'Access denied. This page is for staff only.')
        return redirect('accounts:dashboard')

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all').strip()
    open_vault_deep_link = request.GET.get('open_vault') == '1'

    # Vault list scope: anyone on Intake "LIST OF APPLICATIONS" (has an Archive row) and/or
    # anyone with Intake Archive or legacy Module 2 handoff timestamp. Union covers both:
    # before staff proceed to Application & Eligibility.
    # Ordering: Module 2 queue first when present — priority, then walk-in, then no queue.
    applicants_qs = (
        Applicant.objects
        .prefetch_related(
            Prefetch(
                'application__lot_awards',
                queryset=LotAward.objects.select_related('unit', 'construction_progress'),
            ),
            'documents',
            'requirement_submissions__requirement',
            Prefetch(
                'queue_entries',
                queryset=QueueEntry.objects.filter(status='active').order_by('position'),
                to_attr='active_queue_entries',
            ),
        )
        .filter(
            Q(archives__isnull=False) | Q(module2_handoff_at__isnull=False)
        )
        .distinct()
    )

    # Filter by status
    if status_filter != 'all' and status_filter:
        applicants_qs = applicants_qs.filter(status=status_filter)

    # Filter by search query (skip when opening vault drawer — reference # is not in table row text)
    if search_query and not open_vault_deep_link:
        search_q = (
            Q(full_name__icontains=search_query) |
            Q(reference_number__icontains=search_query) |
            Q(application__lot_awards__unit__block_number__icontains=search_query) |
            Q(application__lot_awards__unit__lot_number__icontains=search_query) |
            Q(documents__document_type__icontains=search_query)
        )
        doc_type_codes = [
            code
            for code, label in Document.DOCUMENT_TYPE_CHOICES
            if search_query.lower() in label.lower()
            or search_query.lower() in code.replace('_', ' ')
        ]
        if doc_type_codes:
            search_q |= Q(documents__document_type__in=doc_type_codes)
        if 'blacklist' in search_query.lower():
            search_q |= Q(blacklist_record__isnull=False)
        applicants_qs = applicants_qs.filter(search_q).distinct()

    # Queue priority ordering: priority queue first, then walk-in, then none.
    QUEUE_RANK = {'priority': 0, 'walk_in': 1}
    QUEUE_LABEL = {'priority': 'Priority', 'walk_in': 'Walk-in'}

    # Evaluate once so we can bulk-load Module 4 blacklist rows (why disqualified).
    applicants_ordered = list(applicants_qs)
    bl_applicant_ids = [a.pk for a in applicants_ordered]
    blacklist_map = {
        str(b.applicant_id): b
        for b in Blacklist.objects.filter(applicant_id__in=bl_applicant_ids).only(
            'applicant_id', 'supporting_notes', 'reason_details'
        )
    }

    # Prepare applicants with lot info and document count
    applicants_list = []
    for applicant in applicants_ordered:
        # Resolve active queue entry from the prefetched list (lowest position wins).
        active_entries = getattr(applicant, 'active_queue_entries', None) or []
        active_queue_entry = active_entries[0] if active_entries else None
        if active_queue_entry:
            queue_type = active_queue_entry.queue_type
            queue_position = active_queue_entry.position
            queue_label_short = QUEUE_LABEL.get(queue_type, queue_type or '—')
            queue_label = f"{queue_label_short} #{queue_position}"
            queue_rank = QUEUE_RANK.get(queue_type, 99)
        else:
            queue_type = ''
            queue_position = None
            queue_label_short = ''
            queue_label = '—'
            queue_rank = 99
        # Count uploaded documents
        doc_count = applicant.documents.count()
        total_docs = 15  # Total possible documents

        # Get lot assignment if exists
        lot_info = None
        try:
            if hasattr(applicant, 'application') and applicant.application:
                qs = applicant.application.lot_awards.filter(unit__isnull=False)
                lot_award = qs.filter(status='active').first() or qs.first()
                if lot_award and lot_award.unit:
                    lot_info = {
                        'block': str(lot_award.unit.block_number) if lot_award.unit.block_number else 'N/A',
                        'lot': str(lot_award.unit.lot_number) if lot_award.unit.lot_number else 'N/A',
                        'site': 'GK Cabatangan'
                    }
        except:
            lot_info = None

        group_a_verified = sum(
            1 for sub in applicant.requirement_submissions.all()
            if getattr(sub.requirement, 'group', '') == 'A' and sub.status == 'verified'
        )
        has_danger_zone_requirement = applicant.channel == 'danger_zone'
        cdrrmo_verified = bool(
            has_danger_zone_requirement and
            getattr(getattr(applicant, 'cdrrmo_certification', None), 'status', '') == 'certified'
        )
        phase_a_required_docs = 7 + (1 if has_danger_zone_requirement else 0)
        phase_a_verified_docs = group_a_verified + (1 if cdrrmo_verified else 0)

        app_obj = getattr(applicant, 'application', None)
        signed_form_confirmed = bool(app_obj and app_obj.applicant_signed_at)
        phase_a_complete = phase_a_verified_docs >= phase_a_required_docs and signed_form_confirmed

        bl_row = blacklist_map.get(str(applicant.pk))
        why_disqualified = ''
        if bl_row and (bl_row.supporting_notes or '').strip():
            why_disqualified = bl_row.supporting_notes.strip()
        elif (applicant.disqualification_reason or '').strip():
            why_disqualified = applicant.disqualification_reason.strip()
        elif bl_row and (bl_row.reason_details or '').strip():
            why_disqualified = bl_row.reason_details.strip()

        applicant_workflow_status, applicant_status_detail = staff_pipeline_primary_detail(
            applicant, app_obj, bl_row
        )

        # Module 4 handoff: vault Phase A complete (no separate FieldInspection ORM gate).
        module3_ready_for_module4 = phase_a_complete

        applicants_list.append({
            'id': str(applicant.id),
            'full_name': applicant.full_name,
            'reference_number': applicant.reference_number,
            'status': applicant.status,
            'status_display': applicant.get_status_display() if hasattr(applicant, 'get_status_display') else applicant.status,
            'barangay': applicant.barangay.name if applicant.barangay else 'N/A',
            'monthly_income': applicant.monthly_income or 0,
            'household_members': applicant.household_member_count,
            'lot_assignment': lot_info,
            'doc_count': doc_count,
            'total_docs': total_docs,
            'doc_percentage': int((doc_count / total_docs) * 100) if total_docs > 0 else 0,
            'phase_a_verified_docs': phase_a_verified_docs,
            'phase_a_required_docs': phase_a_required_docs,
            'phase_a_complete': phase_a_complete,
            'module3_ready_for_module4': module3_ready_for_module4,
            'signed_form_confirmed': signed_form_confirmed,
            'applicant_workflow_status': applicant_workflow_status,
            'applicant_status_detail': applicant_status_detail,
            'why_disqualified': why_disqualified,
            'has_blacklist_record': bool(bl_row),
            'queue_type': queue_type,
            'queue_position': queue_position,
            'queue_label_short': queue_label_short,
            'queue_label': queue_label,
            '_queue_rank': queue_rank,
            '_queue_position_sort': queue_position if queue_position is not None else 10**9,
        })

    # Final ordering: priority queue first (by position), then walk-in (by position), then no-queue.
    applicants_list.sort(key=lambda a: (a['_queue_rank'], a['_queue_position_sort'], a['full_name']))

    applicants_total = len(applicants_list)
    deep_link_applicant_id = (request.GET.get('applicant_id') or '').strip().lower()

    paginator = Paginator(applicants_list, DOCUMENTS_MANAGEMENT_PER_PAGE)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    page_applicants = list(page_obj)
    page_applicant_ids = {str(a['id']).lower() for a in page_applicants}
    if open_vault_deep_link and deep_link_applicant_id and deep_link_applicant_id not in page_applicant_ids:
        for idx, row in enumerate(applicants_list):
            if str(row['id']).lower() == deep_link_applicant_id:
                correct_page = (idx // DOCUMENTS_MANAGEMENT_PER_PAGE) + 1
                if page_obj.number != correct_page:
                    _redirect_q = request.GET.copy()
                    _redirect_q['page'] = correct_page
                    return redirect(f'{request.path}?{_redirect_q.urlencode()}')
                break

    _q = request.GET.copy()
    _q.pop('page', None)
    pagination_query = _q.urlencode()

    # Document group definitions
    doc_groups = {
        'A': {
            'label': 'Group A — Applicant Requirements',
            'color_bg': 'bg-blue-100',
            'color_text': 'text-blue-700',
            'documents': [
                ('barangay_residency', 'Brgy. Certificate of Residency'),
                ('barangay_indigency', 'Brgy. Certificate of Indigency'),
                ('cedula', 'Cedula'),
                ('police_clearance', 'Police Clearance'),
                ('no_property', 'Certificate of No Property'),
                ('photo_2x2', '2x2 Picture'),
                ('house_sketch', 'Sketch of House Location'),
                (
                    'voter_certification',
                    'Voter certification (COMELEC / Barangay voter record)',
                ),
            ]
        },
    }

    all_applicant_ids = [a['id'] for a in applicants_list]
    page_row_ids = [a['id'] for a in page_applicants]
    documents_qs = (
        Document.objects
        .select_related('applicant')
        .filter(applicant_id__in=all_applicant_ids)
        .order_by('applicant__created_at', '-uploaded_at')
    )

    types_on_file = defaultdict(set)
    # Newest upload per (applicant, document_type) — documents_qs is ordered with -uploaded_at per applicant.
    latest_doc_id_by_applicant_type = {}
    for doc in documents_qs:
        rid_d = str(doc.applicant_id).lower()
        types_on_file[rid_d].add(doc.document_type)
        key = (rid_d, doc.document_type)
        if key not in latest_doc_id_by_applicant_type:
            latest_doc_id_by_applicant_type[key] = str(doc.id)

    monitoring_reports_by_applicant = defaultdict(list)
    total_monitoring_report_documents = 0
    if position == 'second_member' and page_row_ids:
        monitoring_reports_qs = (
            MonitoringReport.objects
            .select_related(
                'task',
                'unit',
                'lot_award__application__applicant',
                'submitted_by',
                'assessed_by',
            )
            .prefetch_related('photos')
            .filter(
                lot_award__application__applicant_id__in=page_row_ids,
                task__status='completed',
                is_complete=True,
            )
            .order_by('task__due_date', 'task__days_from_award', 'submitted_at')
        )
        for report in monitoring_reports_qs:
            rid_r = str(report.lot_award.application.applicant_id).lower()
            monitoring_reports_by_applicant[rid_r].append(
                _monitoring_report_document_item(report, request)
            )
            total_monitoring_report_documents += 1

    for row in page_applicants:
        rid = str(row['id']).lower()
        monitoring_report_items = monitoring_reports_by_applicant.get(rid, [])
        if monitoring_report_items:
            row['monitoring_report_count'] = len(monitoring_report_items)
            row['doc_count'] += len(monitoring_report_items)
            row['doc_percentage'] = int((row['doc_count'] / row['total_docs']) * 100) if row['total_docs'] > 0 else 0
        checklist = []
        for _gk, group in doc_groups.items():
            for type_key, label in group['documents']:
                on_file = type_key in types_on_file[rid]
                lk = (rid, type_key)
                view_url = None
                if on_file and lk in latest_doc_id_by_applicant_type:
                    view_url = reverse(
                        'documents:blob_download',
                        kwargs={
                            'position': request.user.position,
                            'doc_id': latest_doc_id_by_applicant_type[lk],
                        },
                    )
                checklist.append({
                    'type_key': type_key,
                    'label': label,
                    'group_label': group['label'],
                    'on_file': on_file,
                    'view_url': view_url,
                    **_vault_drawer_intake_fields(type_key),
                })
        row['vault_checklist'] = checklist

    _va_ids = [UUID(x['id']) for x in page_applicants]
    applicant_map = {
        str(a.id).lower(): a
        for a in (
            Applicant.objects.filter(id__in=_va_ids)
            .select_related('application', 'barangay')
            .prefetch_related(
                'cdrrmo_certification__field_photos',
            )
        )
    }

    # Keys normalized to lowercase so JSON + onclick IDs always match (UUID string casing).
    vault_drawer_data = {}
    for row in page_applicants:
        rid = str(row['id']).lower()
        ap = applicant_map.get(rid)
        ts = types_on_file[rid]
        latest_by = {
            doc_type: doc_id
            for (r, doc_type), doc_id in latest_doc_id_by_applicant_type.items()
            if r == rid
        }
        situation = (
            _build_situation_vault_block(
                ap,
                ts,
                latest_doc_by_type=latest_by,
                position=request.user.position,
                request=request,
            )
            if ap
            else None
        )
        checklist = list(row['vault_checklist'])
        signed_on_file = bool(ap and applicant_has_signed_application_payload(ap))
        signed_view_url = None
        if signed_on_file:
            doc_id = latest_doc_id_by_applicant_type.get((rid, 'signed_application'))
            if doc_id:
                signed_view_url = reverse(
                    'documents:blob_download',
                    kwargs={'position': request.user.position, 'doc_id': doc_id},
                )
        app_obj = getattr(ap, 'application', None) if ap else None
        signed_item = {
            'type_key': 'signed_application',
            'label': 'Physically signed THA application form (scan / upload)',
            'group_label': 'Housing application (Module 2)',
            'on_file': signed_on_file,
            'view_url': signed_view_url,
            **_vault_drawer_intake_fields('signed_application'),
        }
        if not signed_on_file:
            if app_obj and app_obj.status == 'draft':
                signed_item['badge_variant'] = 'pending'
                signed_item['badge_text'] = 'Awaiting signed scan'
            elif app_obj is None:
                signed_item['badge_variant'] = 'waiting'
                signed_item['badge_text'] = 'Awaiting form release'
                signed_item['hide_add_file'] = True
        checklist.append(signed_item)
        checklist.extend(monitoring_reports_by_applicant.get(rid, []))

        vault_drawer_data[rid] = {
            'full_name': row['full_name'],
            'reference_number': row['reference_number'] or '',
            'barangay': row['barangay'],
            'status': row['status'],
            'status_display': row['status_display'],
            'applicant_workflow_status': row.get('applicant_workflow_status') or '',
            'applicant_status_detail': row.get('applicant_status_detail') or '',
            'why_disqualified': row.get('why_disqualified') or '',
            'vault_checklist': checklist,
            'situation': situation,
        }

    blacklisted_registry_count = (
        Blacklist.objects.filter(Q(applicant__archives__isnull=False) | Q(applicant__module2_handoff_at__isnull=False))
        .distinct()
        .count()
    )

    context = {
        'page_title': 'Document Management',
        'user_position': request.user.position,
        'applicants': page_applicants,
        'applicants_upload_choices': [
            {'id': a['id'], 'full_name': a['full_name']}
            for a in applicants_list
        ],
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'applicants_total': applicants_total,
        'doc_groups': doc_groups,
        'search_query': search_query,
        'status_filter': status_filter,
        'applicant_statuses': [
            ('all', 'All Applicants'),
            ('registered', 'Registered'),
            ('eligible', 'Eligible'),
            ('disqualified', 'Disqualified'),
            ('pending_cdrrmo', 'Pending CDRRMO'),
            ('in_queue', 'In Queue'),
            ('standby', 'On Standby'),
            ('awarded', 'Awarded'),
        ],
        # New template context variables
        'documents': documents_qs,
        'total_documents': documents_qs.count() + total_monitoring_report_documents,
        'total_applicants': applicants_total,
        'total_size_gb': round(sum(doc.file_size for doc in documents_qs) / (1024*1024*1024), 2),
        'blacklisted_registry_count': blacklisted_registry_count,
        'vault_drawer_data': vault_drawer_data,
        'vault_drawer_can_intake_scan': request.user.position in ('second_member', 'fourth_member'),
    }

    return render(request, 'documents/management.html', context)


@login_required
@verify_position
@require_http_methods(["GET"])
def download_document_blob(request, position, doc_id):
    """Serve vault bytes stored on DocumentBlob (intake scans).

    PDF and images open inline in the browser by default so staff can review uploads.
    Append ``?download=1`` to force a download (``Content-Disposition: attachment``).
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    doc = get_object_or_404(
        Document.objects.select_related('blob_record'),
        id=doc_id,
    )
    fname_raw = doc.file_name or 'document'
    fname_safe = (
        os.path.basename(fname_raw)
        .replace('"', "'")
        .replace('\r', '')
        .replace('\n', '')
    ) or 'document'

    ctype = _normalize_blob_content_type(doc.mime_type or '', fname_safe)
    force_download = request.GET.get('download') in ('1', 'true', 'yes')
    payload_bytes = None
    try:
        payload_bytes = doc.blob_record.data
    except DocumentBlob.DoesNotExist:
        if doc.file:
            try:
                with doc.file.open('rb') as fh:
                    payload_bytes = fh.read()
            except FileNotFoundError:
                payload_bytes = None
    if payload_bytes is None:
        raise Http404('No file payload for this document')

    response = HttpResponse(payload_bytes, content_type=ctype)
    if force_download or not _blob_disposition_inline_ok(ctype, fname_safe):
        response['Content-Disposition'] = f'attachment; filename="{fname_safe}"'
    else:
        response['Content-Disposition'] = f'inline; filename="{fname_safe}"'
    return response


@login_required
@verify_position
@require_http_methods(["POST"])
def upload_document(request, position):
    """
    AJAX endpoint to upload a document for an applicant.
    Returns JSON response with upload status.

    URL: /documents/<position>/upload/

    Staff-facing: ``incident_report`` is for the Inspection Report document only; field verification
    photos belong on the CDRRMO record as FieldVerificationPhoto, not this vault type.
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    try:
        applicant_id = (request.POST.get('applicant_id') or request.POST.get('applicant') or '').strip()
        doc_type = (request.POST.get('doc_type') or request.POST.get('document_type') or '').strip()
        file = request.FILES.get('file')

        if not all([applicant_id, doc_type, file]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)

        if doc_type == 'signed_application':
            sa_err = _signed_application_upload_file_error(file)
            if sa_err:
                return JsonResponse({'success': False, 'error': sa_err}, status=400)

        # Get applicant
        applicant = Applicant.objects.get(id=applicant_id)

        existing_doc = Document.objects.filter(applicant=applicant, document_type=doc_type).first()
        if existing_doc:
            DocumentBlob.objects.filter(document_id=existing_doc.pk).delete()

        # Create or update document
        doc, created = Document.objects.update_or_create(
            applicant=applicant,
            document_type=doc_type,
            defaults={
                'title': f"{applicant.full_name} - {dict(Document.DOCUMENT_TYPE_CHOICES).get(doc_type, doc_type)}",
                'file': file,
                'file_name': file.name,
                'file_size': file.size,
                'mime_type': file.content_type,
                'uploaded_by': request.user,
                'capture_method': Document.CAPTURE_UPLOAD,
            }
        )

        pipeline_note = ''
        application_advanced = False
        if doc_type == 'signed_application':
            from applications.form_pipeline import apply_signed_application_scan_if_ready

            info = apply_signed_application_scan_if_ready(applicant.id)
            application_advanced = bool(info.get('updated'))
            if application_advanced:
                pipeline_note = (
                    'Physically signed application scan recorded. '
                    'Application status is now Completed — Signed by Applicant.'
                )

        payload = {
            'success': True,
            'message': f"Document {'updated' if not created else 'uploaded'} successfully",
            'document_id': str(doc.id),
            'file_name': doc.file_name,
            'file_size': doc.file_size_display,
            'application_advanced': application_advanced,
            'pipeline_note': pipeline_note,
        }
        return JsonResponse(payload)

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@verify_position
@require_http_methods(["POST"])
def mark_document_present(request, position, doc_type=None):
    """
    Mark a specific document type as present (verified) for an applicant.

    URL: /documents/<position>/mark-present/ or /documents/<position>/mark-present/<doc_type>/
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        doc_type = request.POST.get('doc_type')

        if not all([applicant_id, doc_type]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)

        # Get applicant
        applicant = Applicant.objects.get(id=applicant_id)

        # Create document record without file (marked as verified by staff)
        doc, created = Document.objects.get_or_create(
            applicant=applicant,
            document_type=doc_type,
            defaults={
                'title': f"{applicant.full_name} - {dict(Document.DOCUMENT_TYPE_CHOICES).get(doc_type, doc_type)}",
                'file_name': 'verified_by_staff',
                'file_size': 0,
                'uploaded_by': request.user,
            }
        )

        return JsonResponse({
            'success': True,
            'message': 'Document marked as present',
            'document_id': str(doc.id),
        })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@verify_position
@require_http_methods(["GET"])
def get_applicant_documents(request, position):
    """
    Get all documents for an applicant as JSON.

    URL: /documents/<position>/applicant-documents/
    """
    try:
        applicant_id = request.GET.get('applicant_id')
        applicant = Applicant.objects.prefetch_related('documents').get(id=applicant_id)

        # Build document dict by type
        docs_by_type = {}
        for doc in applicant.documents.all():
            docs_by_type[doc.document_type] = {
                'id': str(doc.id),
                'file_name': doc.file_name,
                'file_size': doc.file_size_display,
                'uploaded_at': doc.uploaded_at.isoformat(),
                'uploaded_by': doc.uploaded_by.get_full_name() if doc.uploaded_by else 'Unknown',
                'url': doc.absolute_download_url(request) or None,
            }

        return JsonResponse({
            'success': True,
            'documents': docs_by_type,
        })

    except Applicant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Applicant not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@verify_position
@require_http_methods(["POST"])
def delete_document(request, position, doc_id):
    """
    AJAX endpoint to delete a document.
    Staff only - requires authentication.

    URL: /documents/<position>/delete/<doc_id>/
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    try:
        doc = Document.objects.get(id=doc_id)

        # Delete the file if it exists
        if doc.file:
            doc.file.delete(save=False)

        # Delete the document record
        doc.delete()

        return JsonResponse({
            'success': True,
            'message': 'Document deleted successfully'
        })

    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@verify_position
@require_POST
def update_requirement_submission(request, position):
    """
    Documents-module alias for Module 2 requirement submission updates.
    Delegates to applications logic to preserve behavior.
    """
    from applications.views import update_requirement
    return update_requirement(request, position)
