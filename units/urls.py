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
]
