from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Main applications list view (Module 2)
    path('staff/', views.applications_list, name='applications_list'),
    
    # Application detail (AJAX endpoint for modal)
    path('staff/<uuid:application_id>/', views.application_detail, name='application_detail'),
    
    # Document verification (Jocel, Joie)
    path('staff/update-requirement/', views.update_requirement, name='update_requirement'),
    
    # Form generation (Jocel, Joie)
    path('staff/generate-form/<uuid:applicant_id>/', views.generate_form, name='generate_form'),
    
    # Signatory routing (Jay, OIC, Head)
    path('staff/update-routing/', views.update_routing, name='update_routing'),
    
    # Move to standby queue (Jocel, Joie)
    path('staff/move-to-standby/', views.move_to_standby, name='move_to_standby'),
    
    # Lot awarding (Jocel, Joie)
    path('staff/award-lot/', views.award_lot, name='award_lot'),
    
    # Electricity tracking (Joie, Laarni)
    path('staff/electricity/', views.electricity_list, name='electricity_list'),
    path('staff/electricity/update/', views.update_electricity, name='update_electricity'),

    # Supporting Services Coordinator (Jocel - Day 5 Week 1)
    path('staff/services/', views.supporting_services_coordinator, name='supporting_services'),
    path('staff/services/complete/', views.process_service_completion, name='process_service'),
    path('staff/services/routing/', views.send_to_signatory_routing, name='send_to_routing'),

    # Legacy endpoint (backwards compatibility)
    path('staff/update-stage/', views.update_stage, name='update_stage'),
]
