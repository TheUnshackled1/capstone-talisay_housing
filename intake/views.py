from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import LandownerSubmission, ISFRecord
import json


def landowner_form(request):
    """
    Public form for landowners to submit ISF records.
    No login required - accessible to anyone.
    """
    # Talisay City barangays
    barangays = [
        'Abuanan', 'Bago', 'Cabatangan', 'Caradio-an', 'Concordia Sur',
        'Dos Hermanas', 'Efigenio Lizares', 'Esperanza', 'Guimbala-on',
        'Himoga-an Baybay', 'Lag-asan', 'Matab-ang', 'Nabitasan',
        'Rizal', 'San Fernando', 'San Francisco', 'San Jose',
        'San Juan', 'San Roque', 'Tabao', 'Taloc', 'Tamlang', 
        'Tangub', 'Tanjay', 'Tigbao', 'Zone 1', 'Zone 2'
    ]
    
    if request.method == 'POST':
        return handle_landowner_submission(request)
    
    return render(request, 'intake/landowner_form.html', {
        'barangays': sorted(barangays),
    })


@require_http_methods(["POST"])
def handle_landowner_submission(request):
    """Process the landowner submission form."""
    try:
        # Get landowner details
        landowner_name = request.POST.get('landowner_name', '').strip()
        landowner_phone = request.POST.get('landowner_phone', '').strip()
        landowner_email = request.POST.get('landowner_email', '').strip()
        property_address = request.POST.get('property_address', '').strip()
        barangay = request.POST.get('barangay', '').strip()
        
        # Validate required fields
        if not all([landowner_name, property_address, barangay]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('landowner_form')
        
        # Get ISF data from JSON field
        isf_data_json = request.POST.get('isf_data', '[]')
        try:
            isf_records_data = json.loads(isf_data_json)
        except json.JSONDecodeError:
            messages.error(request, 'Invalid ISF data format.')
            return redirect('landowner_form')
        
        if not isf_records_data:
            messages.error(request, 'Please add at least one ISF record.')
            return redirect('landowner_form')
        
        # Create the submission
        submission = LandownerSubmission.objects.create(
            landowner_name=landowner_name,
            landowner_phone=landowner_phone,
            landowner_email=landowner_email,
            property_address=property_address,
            barangay=barangay,
        )
        
        # Create ISF records
        isf_references = []
        for isf_data in isf_records_data:
            isf_record = ISFRecord.objects.create(
                submission=submission,
                full_name=isf_data.get('full_name', '').strip(),
                household_members=int(isf_data.get('household_members', 1)),
                monthly_income=float(isf_data.get('monthly_income', 0)),
                years_residing=int(isf_data.get('years_residing', 0)),
                phone_number=isf_data.get('phone_number', '').strip(),
            )
            isf_references.append(isf_record.reference_number)
        
        # Success - redirect to confirmation page
        return render(request, 'intake/submission_success.html', {
            'submission': submission,
            'isf_references': isf_references,
        })
        
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return redirect('landowner_form')
