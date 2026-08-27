from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    # Staff applicants management (consolidated modal-based interface)
    # Role-based URL structure: /intake/staff/<position>/applicants/
    path('staff/<str:position>/applicants/', views.applicants_list, name='applicants_list'),

    # Archive / receipt records (proceeded to Module 2)
    path('staff/<str:position>/archives/', views.archive_list, name='archive_list'),

    # Applicant registration from modal
    path('staff/<str:position>/register/', views.walkin_register, name='walkin_register'),
    path('staff/<str:position>/duplicate-preview/', views.duplicate_preview, name='duplicate_preview'),

    # AJAX endpoints for modal operations
    path('staff/<str:position>/update-eligibility/', views.update_eligibility, name='update_eligibility'),
    path('staff/<str:position>/update-applicant/', views.update_applicant, name='update_applicant'),
    path('staff/<str:position>/upload-scanned-requirement/', views.upload_scanned_requirement, name='upload_scanned_requirement'),
    path('staff/<str:position>/remove-scanned-requirement/', views.remove_scanned_requirement, name='remove_scanned_requirement'),
    path(
        'staff/<str:position>/applicant-requirement-scan-status/',
        views.applicant_requirement_scan_status,
        name='applicant_requirement_scan_status',
    ),
    path('staff/<str:position>/proceed-to-applications/', views.proceed_to_applications, name='proceed_to_applications'),
    path('staff/<str:position>/delete-applicant/', views.delete_applicant, name='delete_applicant'),
    path('staff/<str:position>/unarchive-applicant/', views.unarchive_applicant, name='unarchive_applicant'),

    # --- Public (no login required) ---
    # Applicant status tracker — deep-linked from SMS messages.
    # Example: /status/APP-20260827-1234/
    path('status/<str:ref>/', views.applicant_status_tracker, name='applicant_status_tracker'),
]
