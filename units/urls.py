from django.urls import path
from . import views

app_name = 'units'

urlpatterns = [
    # Housing Units Monitoring Dashboard (Module 4)
    path('housing-units/<str:position>/', views.housing_units_monitoring, name='housing_units_monitoring'),
    path('housing-units/<str:position>/site/create/', views.create_relocation_site, name='create_relocation_site'),
    path('housing-units/<str:position>/unit/create/', views.create_housing_unit, name='create_housing_unit'),
    path('housing-units/<str:position>/unit/construction/update/', views.add_construction_update, name='add_construction_update'),
    path('housing-units/<str:position>/<uuid:unit_id>/details/', views.get_unit_details, name='get_unit_details'),
    path('housing-units/<str:position>/issue-notice/', views.issue_compliance_notice, name='issue_compliance_notice'),

    # Phase 3: Caretaker Monitoring Dashboard
    path('monitoring-dashboard/', views.caretaker_monitoring_dashboard, name='caretaker_monitoring_dashboard'),

    # Phase 4: Report Submission
    path('monitoring-report/<uuid:task_id>/submit/', views.submit_monitoring_report, name='submit_monitoring_report'),

    # Phase 6: Staff Explanation Review
    path('explanation-review/<str:position>/', views.review_explanation, name='review_explanation'),

    # Phase 7: Final Notice Monitoring
    path('final-notice-units/<str:position>/', views.get_final_notice_units, name='get_final_notice_units'),

    # Phase 8: Repossession Confirmation
    path('repossession/<str:position>/confirm/', views.confirm_repossession, name='confirm_repossession'),

    # Staff Dashboard Data Aggregation
    path('staff-dashboard-data/<str:position>/', views.get_staff_monitoring_dashboard_data, name='get_staff_monitoring_dashboard_data'),

    # Case Management (Module 5)
    path('cases/<str:position>/', views.case_management, name='case_management'),
    path('cases/<str:position>/<uuid:case_id>/details/', views.get_case_details, name='get_case_details'),
    path('cases/<str:position>/create/', views.create_case, name='create_case'),
    path('cases/<str:position>/update/', views.update_case, name='update_case'),

    # Blacklist Management
    path('blacklists/<str:position>/', views.blacklist_management, name='blacklist_management'),
]

