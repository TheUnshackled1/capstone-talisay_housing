from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.db import models
from django.utils import timezone
from functools import wraps
import json

from .models import Case, CaseNote


def verify_position(view_func):
    """
    Decorator to verify that URL position parameter matches logged-in user's position.
    Security feature: prevents URL manipulation to access other roles' views.
    """
    @wraps(view_func)
    def wrapper(request, position, *args, **kwargs):
        # Check if position in URL matches user's actual position
        if request.user.position != position:
            from django.contrib import messages
            messages.error(request, f'Access denied. You are logged in as {request.user.get_position_display()}, not {position.replace("_", " ")}.')
            return redirect('accounts:dashboard')
        return view_func(request, position, *args, **kwargs)
    return wrapper


# ===================================================================
# CASE MANAGEMENT - Module 5
# ===================================================================

@login_required
@require_http_methods(["GET"])
@verify_position
def case_management_dashboard(request, position):
    """
    Case Management Dashboard
    Displays all cases with search, filtering, and status tracking

    URL Route: /cases/<position>/

    Actors: All staff
    Purpose: Track complaints, disputes, and case resolutions
    """

    # Get all cases with related data
    cases = (
        Case.objects
        .select_related('received_by', 'investigated_by', 'decided_by', 'complainant_applicant', 'subject_applicant', 'related_unit')
        .prefetch_related('notes')
        .order_by('-received_at')
    )

    # Count by status
    status_counts = {
        'open': cases.filter(status='open').count(),
        'investigation': cases.filter(status='investigation').count(),
        'referred': cases.filter(status='referred').count(),
        'pending_decision': cases.filter(status='pending_decision').count(),
        'resolved': cases.filter(status='resolved').count(),
        'closed': cases.filter(status='closed').count(),
    }

    # Search and filter
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', 'all')
    filter_type = request.GET.get('type', 'all')

    if search_query:
        cases = cases.filter(
            models.Q(complainant_name__icontains=search_query) |
            models.Q(case_number__icontains=search_query) |
            models.Q(initial_description__icontains=search_query) |
            models.Q(subject_name__icontains=search_query)
        )

    if filter_status != 'all':
        cases = cases.filter(status=filter_status)

    if filter_type != 'all':
        cases = cases.filter(case_type=filter_type)

    context = {
        'cases': cases,
        'status_counts': status_counts,
        'search_query': search_query,
        'filter_status': filter_status,
        'filter_type': filter_type,
        'case_type_choices': Case.CASE_TYPE_CHOICES,
    }

    return render(request, 'cases/case_management.html', context)


@login_required
@require_http_methods(["GET"])
@verify_position
def get_case_details(request, position, case_id):
    """
    AJAX endpoint to fetch case details for modal display
    Returns JSON with case info, notes, and timeline

    URL Route: /cases/<position>/<case_id>/details/
    """
    try:
        case = Case.objects.prefetch_related('notes__created_by').get(id=case_id)

        # Prepare notes list
        notes_data = [
            {
                'note': note.note,
                'created_by': note.created_by.get_full_name() if note.created_by else 'System',
                'created_at': note.created_at.isoformat(),
            }
            for note in case.notes.all()
        ]

        return JsonResponse({
            'success': True,
            'case': {
                'id': str(case.id),
                'case_number': case.case_number,
                'status': case.status,
                'status_display': case.get_status_display(),
                'case_type': case.case_type,
                'case_type_display': case.get_case_type_display(),
                'received_at': case.received_at.isoformat(),
                'received_by': case.received_by.get_full_name() if case.received_by else 'Unknown',
                'complainant_name': case.complainant_name,
                'complainant_phone': case.complainant_phone or '',
                'subject_name': case.subject_name or '',
                'initial_description': case.initial_description,
                'investigation_notes': case.investigation_notes or '',
                'investigated_by': case.investigated_by.get_full_name() if case.investigated_by else '',
                'investigated_at': case.investigated_at.isoformat() if case.investigated_at else None,
                'referred_to': case.referred_to or '',
                'referred_at': case.referred_at.isoformat() if case.referred_at else None,
                'referral_notes': case.referral_notes or '',
                'resolution_notes': case.resolution_notes or '',
                'decided_by': case.decided_by.get_full_name() if case.decided_by else '',
                'decided_at': case.decided_at.isoformat() if case.decided_at else None,
                'resolved_at': case.resolved_at.isoformat() if case.resolved_at else None,
                'related_unit': str(case.related_unit) if case.related_unit else None,
                'days_open': case.days_open,
                'is_stale': case.is_stale,
                'notes': notes_data,
            }
        })

    except Case.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Case not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
@verify_position
def create_case(request, position):
    """
    AJAX endpoint to log a new case

    URL Route: /cases/<position>/create/

    POST data:
    - complainant_name: str
    - complainant_phone: str (optional)
    - case_type: case type code
    - received_at_location: 'office' | 'onsite'
    - initial_description: str
    - subject_name: str (optional)
    """
    try:
        data = json.loads(request.body)

        complainant_name = data.get('complainant_name', '').strip()
        complainant_phone = data.get('complainant_phone', '').strip()
        case_type = data.get('case_type', '').strip()
        received_at_location = data.get('received_at_location', 'office').strip()
        initial_description = data.get('initial_description', '').strip()
        subject_name = data.get('subject_name', '').strip()

        # Validate required fields
        if not all([complainant_name, case_type, initial_description]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        # Validate case type
        valid_types = [code for code, _ in Case.CASE_TYPE_CHOICES]
        if case_type not in valid_types:
            return JsonResponse({
                'success': False,
                'error': 'Invalid case type'
            }, status=400)

        # Create case
        case = Case.objects.create(
            complainant_name=complainant_name,
            complainant_phone=complainant_phone,
            case_type=case_type,
            received_at_location=received_at_location,
            initial_description=initial_description,
            subject_name=subject_name,
            received_by=request.user,
        )

        return JsonResponse({
            'success': True,
            'message': f'✓ Case {case.case_number} created successfully',
            'case': {
                'id': str(case.id),
                'case_number': case.case_number,
                'complainant_name': case.complainant_name,
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
@verify_position
def update_case(request, position):
    """
    AJAX endpoint to update case status and add investigation notes

    URL Route: /cases/<position>/update/

    POST data:
    - case_id: UUID
    - action: 'add_note' | 'change_status' | 'investigate' | 'refer' | 'resolve'
    - note: str (for add_note)
    - new_status: status code (for change_status)
    - investigation_notes: str (for investigate)
    - referred_to: str (for refer)
    - referral_notes: str (for refer)
    - resolution_notes: str (for resolve)
    """
    try:
        data = json.loads(request.body)

        case_id = data.get('case_id')
        action = data.get('action', '').strip()

        # Get case
        case = Case.objects.get(id=case_id)

        if action == 'add_note':
            note_text = data.get('note', '').strip()
            if not note_text:
                return JsonResponse({
                    'success': False,
                    'error': 'Note cannot be empty'
                }, status=400)

            # Create case note
            CaseNote.objects.create(
                case=case,
                note=note_text,
                created_by=request.user,
            )

            return JsonResponse({
                'success': True,
                'message': '✓ Note added to case',
                'case_number': case.case_number,
            })

        elif action == 'change_status':
            new_status = data.get('new_status', '').strip()
            valid_statuses = [code for code, _ in Case.STATUS_CHOICES]

            if new_status not in valid_statuses:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid status'
                }, status=400)

            case.status = new_status
            case.save()

            return JsonResponse({
                'success': True,
                'message': f'✓ Case status changed to {case.get_status_display()}',
                'case_number': case.case_number,
                'new_status': new_status,
            })

        elif action == 'investigate':
            investigation_notes = data.get('investigation_notes', '').strip()
            if not investigation_notes:
                return JsonResponse({
                    'success': False,
                    'error': 'Investigation notes required'
                }, status=400)

            case.status = 'investigation'
            case.investigation_notes = investigation_notes
            case.investigated_by = request.user
            case.investigated_at = timezone.now()
            case.save()

            return JsonResponse({
                'success': True,
                'message': '✓ Case marked as under investigation',
                'case_number': case.case_number,
                'new_status': 'investigation',
            })

        elif action == 'refer':
            referred_to = data.get('referred_to', '').strip()
            referral_notes = data.get('referral_notes', '').strip()

            if not referred_to:
                return JsonResponse({
                    'success': False,
                    'error': 'Referral target required'
                }, status=400)

            case.status = 'referred'
            case.referred_to = referred_to
            case.referral_notes = referral_notes
            case.referred_at = timezone.now()
            case.save()

            return JsonResponse({
                'success': True,
                'message': f'✓ Case referred to {referred_to}',
                'case_number': case.case_number,
                'new_status': 'referred',
            })

        elif action == 'resolve':
            resolution_notes = data.get('resolution_notes', '').strip()
            if not resolution_notes:
                return JsonResponse({
                    'success': False,
                    'error': 'Resolution notes required'
                }, status=400)

            case.status = 'resolved'
            case.resolution_notes = resolution_notes
            case.decided_by = request.user
            case.decided_at = timezone.now()
            case.resolved_at = timezone.now()
            case.save()

            return JsonResponse({
                'success': True,
                'message': '✓ Case marked as resolved',
                'case_number': case.case_number,
                'new_status': 'resolved',
            })

        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            }, status=400)

    except Case.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Case not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
