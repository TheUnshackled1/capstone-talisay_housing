from django.shortcuts import render
from intake.models import Barangay, Applicant
from units.models import HousingUnit
from applications.models import Application

def home(request):
    """Homepage with dynamic stats from database."""
    # Get counts from database
    barangays_count = Barangay.objects.filter(is_active=True).count()
    applicants_count = Applicant.objects.count()
    housing_units_count = HousingUnit.objects.count()
    applications_count = Application.objects.count()

    context = {
        'barangays_count': barangays_count,
        'applicants_count': applicants_count,
        'housing_units_count': housing_units_count,
        'applications_count': applications_count,
    }

    return render(request, 'index.html', context)
