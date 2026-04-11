from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from django.contrib import messages

from intake.models import QueueEntry, Applicant
from intake.utils import send_sms
from applications.models import Application
from units.models import HousingUnit, LotAward, RelocationSite


@login_required
@require_http_methods(["GET", "POST"])
def lot_awarding_draw(request):
    """
    UI #16: Lot Awarding Draw - Split Screen Interface
    Process 6: Unit Awarding (Days 3-4 of Week 1)

    Actor: Jocel (Fourth Member / Lot Coordinator)
    Purpose: Assign standby applicants to vacant housing units

    GET: Display form with standby queue and vacant units
    POST: Process lot awards and create assignment records
    """

    # Authorization check: Only Jocel (Fourth Member) can access
    if not hasattr(request.user, 'role') or request.user.role.lower() not in ['fourth', 'fourth_member', 'jocel']:
        return render(request, 'common/access_denied.html',
                      {'message': 'Only the Lot Coordinator can access this function.'}, status=403)

    if request.method == 'POST':
        return process_lot_awards(request)

    # GET: Prepare form data
    # Get all active standby applicants (from priority and walk-in queues)
    standby_applicants = (
        QueueEntry.objects
        .filter(status='active')
        .select_related('applicant')
        .order_by('queue_type', 'position')  # Priority first, then walk-in
    )

    # Get all vacant housing units
    vacant_units = (
        HousingUnit.objects
        .filter(status='vacant')
        .select_related('site')
        .order_by('site__name', 'block_number', 'lot_number')
    )

    # Get all relocation sites for grouping
    sites = RelocationSite.objects.all().values('id', 'name')

    context = {
        'standby_applicants': standby_applicants,
        'vacant_units': vacant_units,
        'sites': sites,
        'total_standby': standby_applicants.count(),
        'total_vacant': vacant_units.count(),
    }

    return render(request, 'units/lot_awarding_draw.html', context)


@transaction.atomic
def process_lot_awards(request):
    """
    Handle POST request to create lot awards
    Expects JSON payload with: { 'assignments': [{ 'queue_entry_id': '...', 'unit_id': '...' }, ...] }
    """
    import json

    try:
        data = json.loads(request.body)
        assignments = data.get('assignments', [])

        if not assignments:
            return JsonResponse({'success': False, 'error': 'No assignments provided'})

        created_awards = []

        for assignment in assignments:
            queue_entry_id = assignment.get('queue_entry_id')
            unit_id = assignment.get('unit_id')

            if not queue_entry_id or not unit_id:
                continue

            try:
                # Get or create application
                queue_entry = QueueEntry.objects.get(id=queue_entry_id)
                applicant = queue_entry.applicant

                # Get or create application for this applicant
                application, created = Application.objects.get_or_create(
                    applicant=applicant,
                    defaults={
                        'reference_number': f'APP-{timezone.now().strftime("%Y%m%d")}-{applicant.id}',
                        'status': 'eligible',
                        'submitted_by': request.user,
                    }
                )

                # Get unit
                unit = HousingUnit.objects.get(id=unit_id)

                # Create LotAward
                lot_award = LotAward.objects.create(
                    application=application,
                    unit=unit,
                    awarded_by=request.user,
                    awarded_at=timezone.now(),
                    status='active',
                )

                # Update unit status
                unit.status = 'occupied'
                unit.save()

                # Update queue entry status
                queue_entry.status = 'completed'
                queue_entry.save()

                # Send SMS notification to beneficiary
                if applicant.phone_number:
                    sms_message = (
                        f"🏠 HOUSING AWARD NOTICE\n"
                        f"Congratulations! You have been awarded:\n"
                        f"{unit.site.name} - Block {unit.block_number}, Lot {unit.lot_number}\n"
                        f"Please report to THA office for contract signing and key handover.\n"
                        f"Thank you, Talisay Housing Authority"
                    )
                    send_sms(applicant.phone_number, sms_message, 'lot_award', applicant=applicant)

                created_awards.append({
                    'applicant_name': applicant.full_name,
                    'unit': f"Block {unit.block_number}, Lot {unit.lot_number}",
                    'site': unit.site.name,
                })

            except (QueueEntry.DoesNotExist, HousingUnit.DoesNotExist) as e:
                continue

        return JsonResponse({
            'success': True,
            'message': f'Successfully awarded {len(created_awards)} unit(s)',
            'awards_created': len(created_awards),
            'details': created_awards,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
