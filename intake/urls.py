from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    # Public landowner portal
    path('landowner-submission/', views.landowner_form, name='landowner_form'),

    # Staff applicants management (consolidated modal-based interface)
    path('staff/applicants/', views.applicants_list, name='applicants_list'),

    # Applicant registration from modal
    path('staff/register/', views.walkin_register, name='walkin_register'),

    # AJAX endpoints for modal operations
    path('staff/update-eligibility/', views.update_eligibility, name='update_eligibility'),
    path('staff/update-applicant/', views.update_applicant, name='update_applicant'),
    path('staff/delete-applicant/', views.delete_applicant, name='delete_applicant'),
    path('staff/resend-sms/', views.resend_sms, name='resend_sms'),
    path('staff/register-landowner-walkin/', views.register_landowner_walkin, name='register_landowner_walkin'),

    # ISF review endpoint (AJAX POST for modal)
    path('staff/isf/<uuid:isf_id>/review/', views.isf_review, name='isf_review'),
    path('staff/isf/<uuid:isf_id>/edit/', views.edit_isf_record, name='edit_isf_record'),
]
