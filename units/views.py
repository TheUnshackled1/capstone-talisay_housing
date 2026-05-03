from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction, models
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta, datetime
from collections import OrderedDict
from functools import wraps
import json

from intake.models import Applicant
from applications.models import QueueEntry, Application
from documents.models import ElectricityConnection
from intake.utils import send_sms
from units.models import (
    HousingUnit, LotAward, RelocationSite, CaseRecord, CaseUpdate, WeeklyReport,
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


# ===================================================================
# HOUSING UNITS MONITORING (Module 4 - Housing Units Dashboard)
# ===================================================================

@login_required
@verify_position
def housing_units_monitoring(request, position):
    """
    Housing Unit & Occupancy Monitoring Dashboard
    Displays all housing units grouped by block with status, occupant info,
    and notice tracking. Supports grid and table views.

    URL: /units/<position>/housing-units/

    Actors: Fourth Member (Jocel), Field Team
    Purpose: Monitor unit occupancy, track compliance notices, manage escalations
    """

    # Get site - assume user is assigned to a site
    # For Fourth Member (Jocel), this would be their primary site
    site_id = request.GET.get('site_id')
    site = None
    all_sites = RelocationSite.objects.all()

    if site_id:
        site = RelocationSite.objects.filter(id=site_id).first()
    else:
        # Default: get first site user has access to
        sites = request.user.assigned_sites.all()
        site = sites.first() if sites.exists() else None

    # If no assigned site, allow staff to view all sites
    # If regular user with no assignment, show first available site
    if not site:
        if all_sites.exists():
            site = all_sites.first()
        else:
            return render(request, 'staff/error.html',
                          {'error': 'No relocation sites available in the system.'})

    # Get all units for the site with related data
    units = (
        HousingUnit.objects
        .filter(site=site)
        .select_related('weekly_report')
        .prefetch_related('lot_awards__application__applicant')
        .order_by('block_number', 'lot_number')
    )

    # Count by status
    occupied_count = units.filter(status='Occupied').count()
    vacant_count = units.filter(status='Vacant — available').count()
    notice_30_count = units.filter(status='Under notice (30-day)').count()
    notice_10_count = units.filter(status='Final notice (10-day)').count()
    repossessed_count = units.filter(status='Repossessed').count()

    # Find critical alerts (final notices escalated)
    escalated_units = units.filter(
        status='Final notice (10-day)',
        is_escalated=True
    ).first()

    critical_alert_message = ""
    has_final_notice_alerts = notice_10_count > 0 or units.filter(is_escalated=True).exists()

    if escalated_units:
        critical_alert_message = (
            f"Block {escalated_units.block_number}, Lot {escalated_units.lot_number} — "
            f"{escalated_units.occupant_name or 'Unknown'}. "
            f"Deadline: {escalated_units.notice_deadline}. No response received — case escalated."
        )

    # Group units by block (OrderedDict so template can use .items() like a dict)
    blocks = units.values_list('block_number', flat=True).distinct().order_by('block_number')
    units_by_block = OrderedDict()
    for block in blocks:
        units_by_block[block] = units.filter(block_number=block)

    # Prepare context
    context = {
        'site': site,
        'all_sites': all_sites,
        'total_units': units.count(),
        'occupied_count': occupied_count,
        'vacant_count': vacant_count,
        'notice_30_count': notice_30_count,
        'notice_10_count': notice_10_count,
        'repossessed_count': repossessed_count,
        'units_by_block': units_by_block,
        'all_units': units,
        'has_final_notice_alerts': has_final_notice_alerts,
        'critical_alert_message': critical_alert_message,
        # Aliases for template compatibility
        'has_escalation_alerts': has_final_notice_alerts,
        'escalation_message': critical_alert_message,
        'view_mode': request.GET.get('view', 'grid'),
    }

    return render(request, 'units/housing_units_monitoring.html', context)


@login_required
@verify_position
@require_http_methods(["GET"])
def get_unit_details(request, position, unit_id):
    """
    AJAX endpoint to fetch unit details for modal display
    Returns JSON with unit info, occupant, notices, and weekly report

    URL: /units/<position>/detail/<unit_id>/
    """
    try:
        unit = HousingUnit.objects.prefetch_related('weekly_report').get(id=unit_id)

        # Prepare notice info
        notice_info = None
        if unit.notice_date_issued:
            notice_info = {
                'type': unit.notice_type,
                'issued': unit.notice_date_issued.isoformat(),
                'deadline': unit.notice_deadline.isoformat() if unit.notice_deadline else None,
            }

        # Prepare weekly report
        weekly_report = None
        try:
            if unit.weekly_report:
                weekly_report = {
                    'reported_status': unit.weekly_report.reported_status,
                    'concern_notes': unit.weekly_report.concern_notes,
                    'last_updated': unit.weekly_report.last_updated.isoformat(),
                }
        except HousingUnit.weekly_report.RelatedObjectDoesNotExist:
            weekly_report = None

        return JsonResponse({
            'success': True,
            'unit': {
                'id': str(unit.id),
                'block': unit.block_number,
                'lot': unit.lot_number,
                'status': unit.status,
                'occupant_name': unit.occupant_name or '',
                'occupant_id': unit.occupant_id or '',
                'is_escalated': unit.is_escalated,
                'notice': notice_info,
                'weekly_report': weekly_report,
            }
        })

    except HousingUnit.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Unit not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@verify_position
@require_POST
def issue_compliance_notice(request, position):
    """
    AJAX endpoint to issue a compliance notice to a housing unit
    Updates unit status and sends SMS notification

    URL: /units/<position>/notice/issue/

    POST data:
    - unit_id: UUID
    - notice_type: '30-day' or '10-day'
    - reason: Text reason for notice
    """
    try:
        data = json.loads(request.body)

        unit_id = data.get('unit_id')
        notice_type = data.get('notice_type')
        reason = data.get('reason', '')

        if not all([unit_id, notice_type]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields: unit_id, notice_type'
            })

        if notice_type not in ['30-day', '10-day']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid notice type. Must be "30-day" or "10-day"'
            })

        # Get unit
        unit = HousingUnit.objects.get(id=unit_id)

        # Update unit status and notice
        unit.notice_type = notice_type
        unit.notice_date_issued = timezone.now()

        if notice_type == '30-day':
            unit.status = 'Under notice (30-day)'
            unit.notice_deadline = (timezone.now() + timedelta(days=30)).date()
            days = 30
        else:
            unit.status = 'Final notice (10-day)'
            unit.notice_deadline = (timezone.now() + timedelta(days=10)).date()
            days = 10

        unit.save()

        # Send SMS to occupant if available
        # (Would integrate with send_sms() utility if occupant phone is available)
        message_text = (
            f"Notice: Your unit at Block {unit.block_number} Lot {unit.lot_number} has been flagged. "
            f"You have {days} days to visit the Housing Office and submit an explanation."
        )

        return JsonResponse({
            'success': True,
            'message': f'✓ {notice_type.title()} notice issued to Block {unit.block_number}, Lot {unit.lot_number}',
            'unit': {
                'id': str(unit.id),
                'status': unit.status,
                'notice_deadline': unit.notice_deadline.isoformat(),
            }
        })

    except HousingUnit.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Unit not found'
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


@login_required
@verify_position
def electricity_list(request, position):
    """
    Electricity connection tracking under Housing Units.

    URL: /units/housing-units/<position>/electricity/
    """
    allowed_positions = ['second_member', 'fifth_member']
    if request.user.position not in allowed_positions:
        messages.error(request, 'Access denied. Electricity tracking is for Joie and Laarni only.')
        return redirect('units:housing_units_monitoring', position=position)

    connections = ElectricityConnection.objects.select_related(
        'application', 'application__applicant', 'application__lot_awarding', 'applied_by'
    ).order_by('-created_at')

    status_counts = {
        'pending': connections.filter(status='pending').count(),
        'applied': connections.filter(status='applied').count(),
        'inspection_scheduled': connections.filter(status='inspection_scheduled').count(),
        'inspection_completed': connections.filter(status='inspection_completed').count(),
        'connected': connections.filter(status='connected').count(),
        'issues': connections.filter(status='issues').count(),
    }

    filter_status = request.GET.get('status', 'all')
    if filter_status != 'all':
        connections = connections.filter(status=filter_status)

    overdue_connections = [c for c in connections if c.is_overdue]

    context = {
        'connections': connections,
        'status_counts': status_counts,
        'filter_status': filter_status,
        'overdue_count': len(overdue_connections),
        'total_count': connections.count(),
    }
    return render(request, 'applications/electricity_list.html', context)


@login_required
@verify_position
@require_POST
def update_electricity(request, position):
    """
    Update electricity connection status from Housing Units.

    URL: /units/housing-units/<position>/electricity/update/
    """
    allowed_positions = ['second_member', 'fifth_member']
    if request.user.position not in allowed_positions:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied. Only Joie or Laarni can update electricity status.'
        }, status=403)

    connection_id = request.POST.get('connection_id')
    new_status = request.POST.get('status')
    negros_power_ref = request.POST.get('negros_power_reference', '')
    inspection_date = request.POST.get('inspection_date')
    inspection_result = request.POST.get('inspection_result', '')
    meter_number = request.POST.get('meter_number', '')
    issue_description = request.POST.get('issue_description', '')
    notes = request.POST.get('notes', '')

    if not connection_id or not new_status:
        return JsonResponse({'success': False, 'error': 'Connection ID and status are required'})

    try:
        connection = ElectricityConnection.objects.select_related('application__applicant').get(id=connection_id)

        old_status = connection.status
        connection.status = new_status
        connection.negros_power_reference = negros_power_ref
        connection.notes = notes

        if inspection_date:
            try:
                connection.inspection_date = datetime.strptime(inspection_date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid inspection date format'})

        if inspection_result:
            connection.inspection_result = inspection_result

        if meter_number:
            connection.meter_number = meter_number

        if issue_description:
            connection.issue_description = issue_description

        if new_status == 'connected' and old_status != 'connected':
            connection.connected_at = timezone.now()

        connection.save()

        return JsonResponse({
            'success': True,
            'message': f'Electricity status updated to {connection.get_status_display()}'
        })

    except ElectricityConnection.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Connection not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ===================================================================
# CASE MANAGEMENT (Module 5 - Case Management Dashboard)
# ===================================================================

@login_required
@verify_position
def case_management(request, position):
    """
    Case Management Dashboard
    Displays all case records with search, filtering, and status tracking

    URL: /units/<position>/cases/

    Actors: All staff
    Purpose: Track complaints, disputes, and case resolutions
    """

    # Get all cases
    cases = (
        CaseRecord.objects
        .select_related('handled_by', 'created_by')
        .prefetch_related('updates')
        .order_by('-date_received')
    )

    # Count by status
    open_count = cases.filter(status='Open').count()
    referred_count = cases.filter(status='Referred').count()
    resolved_count = cases.filter(status='Resolved').count()

    # Search and filter
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', 'all')
    filter_type = request.GET.get('type', 'all')

    if search_query:
        cases = cases.filter(
            models.Q(complainant_name__icontains=search_query) |
            models.Q(case_number__icontains=search_query) |
            models.Q(description__icontains=search_query)
        )

    if filter_status != 'all':
        cases = cases.filter(status=filter_status)

    if filter_type != 'all':
        cases = cases.filter(complaint_type=filter_type)

    context = {
        'cases': cases,
        'open_count': open_count,
        'referred_count': referred_count,
        'resolved_count': resolved_count,
        'search_query': search_query,
        'filter_status': filter_status,
        'filter_type': filter_type,
    }

    return render(request, 'units/case_management.html', context)


@login_required
@verify_position
@require_http_methods(["GET"])
def get_case_details(request, position, case_id):
    """
    AJAX endpoint to fetch case details for modal display
    Returns JSON with case info, updates, and timeline

    URL: /units/<position>/case/<case_id>/
    """
    try:
        case = CaseRecord.objects.prefetch_related('updates').get(id=case_id)

        # Prepare updates list
        updates = [
            {
                'notes': update.notes,
                'updated_by': update.updated_by.get_full_name() if update.updated_by else 'Unknown',
                'updated_at': update.updated_at.isoformat(),
            }
            for update in case.updates.all()
        ]

        return JsonResponse({
            'success': True,
            'case': {
                'id': str(case.id),
                'case_number': case.case_number,
                'status': case.status,
                'date_received': case.date_received.isoformat(),
                'complainant_name': case.complainant_name,
                'complainant_id': case.complainant_id or '',
                'complaint_type': case.complaint_type,
                'description': case.description,
                'handled_by': case.handled_by.get_full_name() if case.handled_by else 'Unassigned',
                'referred_to': case.referred_to or None,
                'referral_date': case.referral_date.isoformat() if case.referral_date else None,
                'outcome': case.outcome or '',
                'resolved_date': case.resolved_date.isoformat() if case.resolved_date else None,
                'updates': updates,
            }
        })

    except CaseRecord.DoesNotExist:
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
@verify_position
@require_POST
def create_case(request, position):
    """
    AJAX endpoint to create a new case record

    URL: /units/<position>/case/create/

    POST data:
    - complainant_name: str
    - complainant_id: str (optional)
    - complaint_type: 'Boundary Dispute' | 'Structural Issue' | 'Interpersonal Conflict' | 'Other'
    - date_received: date string (YYYY-MM-DD)
    - description: str
    - handled_by_user_id: UUID (user to assign as handler)
    """
    try:
        data = json.loads(request.body)

        complainant_name = data.get('complainant_name', '').strip()
        complainant_id = data.get('complainant_id', '').strip()
        complaint_type = data.get('complaint_type', '').strip()
        date_received = data.get('date_received', '').strip()
        description = data.get('description', '').strip()
        handled_by_user_id = data.get('handled_by_user_id')

        # Validate required fields
        if not all([complainant_name, complaint_type, date_received, description]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        if complaint_type not in ['Boundary Dispute', 'Structural Issue', 'Interpersonal Conflict', 'Other']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid complaint type'
            }, status=400)

        # Get handler user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        handled_by = None
        if handled_by_user_id:
            try:
                handled_by = User.objects.get(id=handled_by_user_id)
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Handler user not found'
                }, status=404)

        # Create case
        case = CaseRecord.objects.create(
            complainant_name=complainant_name,
            complainant_id=complainant_id,
            complaint_type=complaint_type,
            date_received=date_received,
            description=description,
            handled_by=handled_by,
            created_by=request.user,
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
@verify_position
@require_POST
def update_case(request, position):
    """
    AJAX endpoint to update case status, add notes, or resolve

    URL: /units/<position>/case/update/

    POST data:
    - case_id: UUID
    - action: 'add_note' | 'change_status' | 'refer' | 'resolve'
    - notes: str (for add_note)
    - new_status: 'Open' | 'Referred' | 'Resolved' (for change_status)
    - referred_to: str (for refer)
    - outcome: str (for resolve)
    """
    try:
        data = json.loads(request.body)

        case_id = data.get('case_id')
        action = data.get('action', '').strip()

        # Get case
        case = CaseRecord.objects.get(id=case_id)

        if action == 'add_note':
            notes = data.get('notes', '').strip()
            if not notes:
                return JsonResponse({
                    'success': False,
                    'error': 'Notes cannot be empty'
                }, status=400)

            # Create case update
            CaseUpdate.objects.create(
                case=case,
                notes=notes,
                updated_by=request.user,
            )

            return JsonResponse({
                'success': True,
                'message': '✓ Note added to case',
                'case_number': case.case_number,
            })

        elif action == 'change_status':
            new_status = data.get('new_status', '').strip()
            if new_status not in ['Open', 'Referred', 'Resolved']:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid status'
                }, status=400)

            case.status = new_status
            case.save()

            return JsonResponse({
                'success': True,
                'message': f'✓ Case status changed to {new_status}',
                'case_number': case.case_number,
                'new_status': new_status,
            })

        elif action == 'refer':
            referred_to = data.get('referred_to', '').strip()
            if not referred_to:
                return JsonResponse({
                    'success': False,
                    'error': 'Referral target required'
                }, status=400)

            case.referred_to = referred_to
            case.referral_date = timezone.now().date()
            case.status = 'Referred'
            case.save()

            return JsonResponse({
                'success': True,
                'message': f'✓ Case referred to {referred_to}',
                'case_number': case.case_number,
                'new_status': 'Referred',
            })

        elif action == 'resolve':
            outcome = data.get('outcome', '').strip()
            if not outcome:
                return JsonResponse({
                    'success': False,
                    'error': 'Outcome/resolution required'
                }, status=400)

            case.status = 'Resolved'
            case.outcome = outcome
            case.resolved_date = timezone.now().date()
            case.save()

            return JsonResponse({
                'success': True,
                'message': '✓ Case resolved and closed',
                'case_number': case.case_number,
                'new_status': 'Resolved',
            })

        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            }, status=400)

    except CaseRecord.DoesNotExist:
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
