from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from intake.models import Applicant
from documents.models import Document


@login_required
def document_management(request):
    """
    Module 3 - Document Management
    Search and manage documents for all applicants and beneficiaries.
    """
    if not request.user.is_staff:
        messages.error(request, 'Access denied. This page is for staff only.')
        return redirect('accounts:dashboard')

    search_query = request.GET.get('search', '').strip()

    # Get all applicants, optionally filtered by search
    applicants = Applicant.objects.all().prefetch_related('documents')

    if search_query:
        applicants = applicants.filter(
            Q(full_name__icontains=search_query) |
            Q(reference_number__icontains=search_query) |
            Q(applicant_lot_award__unit__block_number__icontains=search_query) |
            Q(applicant_lot_award__unit__lot_number__icontains=search_query)
        ).distinct()

    # Document groups and types
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

    # Get selected applicant from session or parameter
    selected_applicant_id = request.GET.get('applicant_id') or request.session.get('selected_applicant_id')
    selected_applicant = None
    applicant_documents = {}

    if selected_applicant_id:
        try:
            selected_applicant = Applicant.objects.prefetch_related('documents').get(id=selected_applicant_id)
            request.session['selected_applicant_id'] = selected_applicant_id

            # Get documents by type for selected applicant
            for doc in selected_applicant.documents.all():
                applicant_documents[doc.document_type] = {
                    'document': doc,
                    'exists': True
                }
        except Applicant.DoesNotExist:
            selected_applicant = None

    context = {
        'applicants': applicants,
        'selected_applicant': selected_applicant,
        'applicant_documents': applicant_documents,
        'doc_groups': doc_groups,
        'search_query': search_query,
    }

    return render(request, 'documents/management.html', context)
