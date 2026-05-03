from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from functools import wraps
import json
import mimetypes
import os
from intake.models import Applicant
from units.models import LotAward
from applications.models import QueueEntry
from documents.models import (
    Document,
    DocumentBlob,
    RequirementSubmission,
    EndorsementRoutingStep,
)


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

    # Vault list scope: anyone on Intake "LIST OF APPLICATIONS" (has an Archive row) and/or
    # anyone with Intake Archive or legacy Module 2 handoff timestamp. Union covers both:
    # before staff proceed to Application & Eligibility.
    # Ordering: Module 2 queue first when present — priority, then walk-in, then no queue.
    applicants_qs = (
        Applicant.objects
        .prefetch_related(
            'application__lot_awards__unit',
            'documents',
            'requirement_submissions__requirement',
            'application__endorsement_routing_steps',
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

    # Filter by search query
    if search_query:
        applicants_qs = applicants_qs.filter(
            Q(full_name__icontains=search_query) |
            Q(reference_number__icontains=search_query) |
            Q(application__lot_awards__unit__block_number__icontains=search_query) |
            Q(application__lot_awards__unit__lot_number__icontains=search_query)
        ).distinct()

    # Queue priority ordering: priority queue first, then walk-in, then none.
    QUEUE_RANK = {'priority': 0, 'walk_in': 1}
    QUEUE_LABEL = {'priority': 'Priority', 'walk_in': 'Walk-in'}

    # Prepare applicants with lot info and document count
    applicants_list = []
    for applicant in applicants_qs:
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
                lot_award = applicant.application.lot_awards.filter(unit__isnull=False).first()
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

        field_inspection = getattr(app_obj, 'field_inspection', None) if app_obj else None
        phase_b_complete = bool(field_inspection and field_inspection.status == 'confirmed' and field_inspection.confirmed_at)

        committee = getattr(app_obj, 'committee_interview', None) if app_obj else None
        committee_result = getattr(committee, 'result', 'pending') if committee else 'pending'
        phase_c_complete = committee_result == 'passed'

        routing_steps = list(getattr(app_obj, 'endorsement_routing_steps', []).all()) if app_obj else []
        completed_routing_count = sum(1 for step in routing_steps if step.is_completed)
        phase_d_complete = completed_routing_count >= 7

        module3_ready_for_module4 = phase_a_complete and phase_b_complete and phase_c_complete and phase_d_complete

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
            'phase_b_complete': phase_b_complete,
            'phase_c_complete': phase_c_complete,
            'phase_d_complete': phase_d_complete,
            'phase_d_completed_steps': completed_routing_count,
            'module3_ready_for_module4': module3_ready_for_module4,
            'committee_result': committee_result,
            'signed_form_confirmed': signed_form_confirmed,
            'queue_type': queue_type,
            'queue_position': queue_position,
            'queue_label_short': queue_label_short,
            'queue_label': queue_label,
            '_queue_rank': queue_rank,
            '_queue_position_sort': queue_position if queue_position is not None else 10**9,
        })

    # Final ordering: priority queue first (by position), then walk-in (by position), then no-queue.
    applicants_list.sort(key=lambda a: (a['_queue_rank'], a['_queue_position_sort'], a['full_name']))

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
            ]
        },
        'B': {
            'label': 'Group B — Office-Generated / Facilitated',
            'color_bg': 'bg-teal-100',
            'color_text': 'text-teal-700',
            'documents': [
                ('application_form', 'Application Form'),
                ('notarized_docs', 'Notarized Documents'),
                ('engineering_assessment', 'Engineering Assessment'),
                ('signed_application', 'Signed Application (Head-Approved)'),
            ]
        },
        'C': {
            'label': 'Group C — Post-Award Documents',
            'color_bg': 'bg-purple-100',
            'color_text': 'text-purple-700',
            'documents': [
                ('lot_award', 'Lot Award Document'),
                ('electricity_app', 'Electricity Connection Application'),
                ('cdrrmo_cert', 'CDRRMO Certification'),
                ('explanation_letter', 'Explanation Letter (compliance)'),
            ]
        }
    }

    applicant_ids = [a['id'] for a in applicants_list]
    documents_qs = (
        Document.objects
        .select_related('applicant')
        .filter(applicant_id__in=applicant_ids)
        .order_by('applicant__created_at', '-uploaded_at')
    )
    disqualified_count = (
        Applicant.objects.filter(status='disqualified')
        .filter(Q(archives__isnull=False) | Q(module2_handoff_at__isnull=False))
        .distinct()
        .count()
    )

    context = {
        'page_title': 'Document Management',
        'user_position': request.user.position,
        'applicants': applicants_list,
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
        'total_documents': documents_qs.count(),
        'total_applicants': len(applicants_list),
        'total_size_gb': round(sum(doc.file_size for doc in documents_qs) / (1024*1024*1024), 2),
        'disqualified_count': disqualified_count,
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
    try:
        blob = doc.blob_record
    except DocumentBlob.DoesNotExist:
        raise Http404('No file payload for this document')

    fname_raw = doc.file_name or 'document'
    fname_safe = (
        os.path.basename(fname_raw)
        .replace('"', "'")
        .replace('\r', '')
        .replace('\n', '')
    ) or 'document'

    ctype = _normalize_blob_content_type(doc.mime_type or '', fname_safe)
    force_download = request.GET.get('download') in ('1', 'true', 'yes')

    response = HttpResponse(blob.data, content_type=ctype)
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

    Staff-facing: ``incident_report`` is for the incident report document only; field verification
    photos belong on the CDRRMO record as FieldVerificationPhoto, not this vault type.
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    try:
        applicant_id = request.POST.get('applicant_id')
        doc_type = request.POST.get('doc_type')
        file = request.FILES.get('file')

        if not all([applicant_id, doc_type, file]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)

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
            }
        )

        return JsonResponse({
            'success': True,
            'message': f"Document {'updated' if not created else 'uploaded'} successfully",
            'document_id': str(doc.id),
            'file_name': doc.file_name,
            'file_size': doc.file_size_display,
        })

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


@login_required
@verify_position
@require_POST
def update_signatory_routing(request, position):
    """
    Documents-module alias for Module 2 signatory routing updates.
    Delegates to applications logic to preserve behavior.
    """
    from applications.views import update_routing
    return update_routing(request, position)
