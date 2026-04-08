from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Main applications list view (Module 2)
    path('staff/', views.applications_list, name='applications_list'),
    
    # Application detail (AJAX endpoint for modal)
    path('staff/<uuid:application_id>/', views.application_detail, name='application_detail'),
    
    # Update requirement status (AJAX)
    path('staff/update-requirement/', views.update_requirement, name='update_requirement'),
    
    # Generate application form
    path('staff/generate-form/<uuid:applicant_id>/', views.generate_form, name='generate_form'),
    
    # Update signatory routing (AJAX)
    path('staff/update-routing/', views.update_routing, name='update_routing'),
    
    # Update application stage (AJAX)
    path('staff/update-stage/', views.update_stage, name='update_stage'),
]
