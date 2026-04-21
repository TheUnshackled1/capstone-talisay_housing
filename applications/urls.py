from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Main applications list view (Module 2)
    path('staff/<str:position>/', views.applications_list, name='applications_list'),

    # Application detail (AJAX endpoint for modal)
    path('staff/<str:position>/<uuid:application_id>/', views.application_detail, name='application_detail'),

    # Document verification (Jocel, Joie)
    path('staff/<str:position>/update-requirement/', views.update_requirement, name='update_requirement'),
    path('staff/<str:position>/evaluate-applicant/', views.evaluate_applicant, name='evaluate_applicant'),

    # Form generation (Jocel, Joie)
    path('staff/<str:position>/generate-form/<uuid:applicant_id>/', views.generate_form, name='generate_form'),

    # Signatory routing (Jay, OIC, Head)
    path('staff/<str:position>/update-routing/', views.update_routing, name='update_routing'),

    # Move to standby queue (Jocel, Joie)
    path('staff/<str:position>/move-to-standby/', views.move_to_standby, name='move_to_standby'),

    # Lot awarding (Jocel, Joie)
    path('staff/<str:position>/award-lot/', views.award_lot, name='award_lot'),

    # Electricity tracking (Joie, Laarni)
    path('staff/<str:position>/electricity/', views.electricity_list, name='electricity_list'),
    path('staff/<str:position>/electricity/update/', views.update_electricity, name='update_electricity'),

    # Supporting Services Coordinator (Jocel - Day 5 Week 1)
    path('staff/<str:position>/services/', views.supporting_services_coordinator, name='supporting_services'),
    path('staff/<str:position>/services/complete/', views.process_service_completion, name='process_service'),
    path('staff/<str:position>/services/routing/', views.send_to_signatory_routing, name='send_to_routing'),
]
