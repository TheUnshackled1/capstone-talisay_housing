from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Main applications list view (Module 2)
    path('staff/<str:position>/', views.applications_list, name='applications_list'),
    path(
        'staff/<str:position>/ready-for-form/',
        views.ready_for_form_queue,
        name='ready_for_form_queue',
    ),
    path('staff/<str:position>/evaluate-precheck/', views.evaluate_precheck, name='evaluate_precheck'),
    path('staff/<str:position>/eligibility-snapshot/', views.eligibility_snapshot, name='eligibility_snapshot'),
    path('staff/<str:position>/save-eligibility-check-decision/', views.save_eligibility_check_decision, name='save_eligibility_check_decision'),
    path('staff/<str:position>/mark-situation-certified/', views.mark_situation_certified, name='mark_situation_certified'),
    path('staff/<str:position>/proceed-to-form-queue/', views.proceed_to_form_queue, name='proceed_to_form_queue'),

    path('staff/<str:position>/update-cdrrmo-certification/', views.update_cdrrmo_certification, name='update_cdrrmo_certification'),
    path('staff/<str:position>/field-verify-cdrrmo/', views.field_verify_cdrrmo, name='field_verify_cdrrmo'),
    path('staff/<str:position>/update-cdrrmo-status/', views.update_cdrrmo_status, name='update_cdrrmo_status'),

    # Form generation (Jocel, Joie)
    path('staff/<str:position>/generate-form/<uuid:applicant_id>/', views.generate_form, name='generate_form'),

    # Move to standby queue (Jocel, Joie)
    path('staff/<str:position>/move-to-standby/', views.move_to_standby, name='move_to_standby'),

    # Lot awarding (Jocel, Joie)
    path('staff/<str:position>/award-lot/', views.award_lot, name='award_lot'),

    # Electricity tracking (Joie, Laarni)
    path('staff/<str:position>/electricity/', views.electricity_list, name='electricity_list'),
    path('staff/<str:position>/electricity/update/', views.update_electricity, name='update_electricity'),
]
