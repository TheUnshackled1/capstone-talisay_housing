from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from functools import wraps
import json
from intake.models import Applicant
from units.models import LotAward
from documents.models import Document


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
    Module 3 - Document Management
    Search and manage documents for all applicants and beneficiaries.

    URL: /documents/<position>/management/
    """
    if not request.user.is_staff:
        messages.error(request, 'Access denied. This page is for staff only.')
        return redirect('accounts:dashboard')

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all').strip()

    # Get all applicants
    applicants_qs = Applicant.objects.prefetch_related('application__lot_awards__unit', 'documents').all()

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

    # Prepare applicants with lot info and document count
    applicants_list = []
    for applicant in applicants_qs:
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
        })

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
        'documents': Document.objects.select_related('applicant').order_by('-uploaded_at'),
        'total_documents': Document.objects.count(),
        'total_applicants': Applicant.objects.filter(documents__isnull=False).distinct().count(),
        'total_size_gb': round(sum(doc.file_size for doc in Document.objects.all()) / (1024*1024*1024), 2),
    }

    return render(request, 'documents/management.html', context)


@login_required
@verify_position
@require_http_methods(["POST"])
def upload_document(request, position):
    """
    AJAX endpoint to upload a document for an applicant.
    Returns JSON response with upload status.

    URL: /documents/<position>/upload/
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

        # Check if document of this type already exists
        existing_doc = Document.objects.filter(applicant=applicant, document_type=doc_type).first()

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
                'url': doc.file.url if doc.file else None,
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
