from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    # Public landowner portal
    path('landowner-submission/', views.landowner_form, name='landowner_form'),
    
    # Staff applicants management (Joie - Second Member, Jocel - Fourth Member)
    # Consolidated view for all intake channels (replaces old submission_list)
    path('staff/applicants/', views.applicants_list, name='applicants_list'),
    
    # Walk-in registration (Channel B/C)
    path('staff/register/', views.walkin_register, name='walkin_register'),
    
    # Update eligibility (AJAX endpoint for modal)
    path('staff/update-eligibility/', views.update_eligibility, name='update_eligibility'),
    
    # Update applicant data (AJAX endpoint for edit mode)
    path('staff/update-applicant/', views.update_applicant, name='update_applicant'),
    
    # Channel A review workflow (Landowner submissions)
    path('staff/submissions/<uuid:submission_id>/', views.submission_review, name='submission_review'),
    path('staff/isf/<uuid:isf_id>/review/', views.isf_review, name='isf_review'),
    
    # Channel B/C review workflow (Walk-in and Danger Zone)
    path('staff/walkin/<uuid:applicant_id>/review/', views.walkin_review, name='walkin_review'),
]
