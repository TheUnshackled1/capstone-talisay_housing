from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    # Staff applicants management (consolidated modal-based interface)
    # Role-based URL structure: /intake/staff/<position>/applicants/
    path('staff/<str:position>/applicants/', views.applicants_list, name='applicants_list'),

    # Applicant registration from modal
    path('staff/<str:position>/register/', views.walkin_register, name='walkin_register'),
    path('staff/<str:position>/duplicate-preview/', views.duplicate_preview, name='duplicate_preview'),

    # AJAX endpoints for modal operations
    path('staff/<str:position>/update-eligibility/', views.update_eligibility, name='update_eligibility'),
    path('staff/<str:position>/update-applicant/', views.update_applicant, name='update_applicant'),
    path('staff/<str:position>/proceed-to-applications/', views.proceed_to_applications, name='proceed_to_applications'),
    path('staff/<str:position>/delete-applicant/', views.delete_applicant, name='delete_applicant'),
    path('staff/<str:position>/resend-sms/', views.resend_sms, name='resend_sms'),
]
