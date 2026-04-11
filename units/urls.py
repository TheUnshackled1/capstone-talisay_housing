from django.urls import path
from . import views

app_name = 'units'

urlpatterns = [
    path('awarding-draw/', views.lot_awarding_draw, name='lot_awarding_draw'),

    # Compliance Notice Issuance (UI #25 - Week 2)
    path('compliance-notice/', views.compliance_notice_issuance, name='compliance_notice_issuance'),
    path('compliance-notice/issue/', views.process_compliance_notice, name='process_compliance_notice'),

    # Occupancy Report Form (UI #22 - Week 2 Day 3-4)
    path('occupancy-report/', views.occupancy_report_form, name='occupancy_report_form'),
    path('occupancy-report/submit/', views.submit_occupancy_report, name='submit_occupancy_report'),

    # Occupancy Review Form (UI #23 - Week 2 Day 5)
    path('occupancy-review/', views.occupancy_review_list, name='occupancy_review_list'),
    path('occupancy-review/<uuid:report_id>/', views.occupancy_review_detail, name='occupancy_review_detail'),
    path('occupancy-review/submit/', views.submit_occupancy_review, name='submit_occupancy_review'),

    # Housing Units Monitoring Dashboard (Module 4)
    path('housing-units/', views.housing_units_monitoring, name='housing_units_monitoring'),
    path('housing-units/<uuid:unit_id>/details/', views.get_unit_details, name='get_unit_details'),
    path('housing-units/issue-notice/', views.issue_compliance_notice, name='issue_compliance_notice'),

    # Case Management (Module 5)
    path('cases/', views.case_management, name='case_management'),
    path('cases/<uuid:case_id>/details/', views.get_case_details, name='get_case_details'),
    path('cases/create/', views.create_case, name='create_case'),
    path('cases/update/', views.update_case, name='update_case'),
]

