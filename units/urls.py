from django.urls import path
from . import views
from cases import views as cases_views

app_name = 'units'

urlpatterns = [
    # Housing Units Monitoring Dashboard (Module 4)
    path('housing-units/<str:position>/', views.housing_units_monitoring, name='housing_units_monitoring'),
    path('housing-units/<str:position>/gk-masterlist/', views.gk_masterlist, name='gk_masterlist'),
    path(
        'housing-units/<str:position>/historical-beneficiaries/template.csv',
        views.historical_beneficiary_template,
        name='historical_beneficiary_template',
    ),
    path(
        'housing-units/<str:position>/historical-beneficiaries/import/',
        views.historical_beneficiary_import,
        name='historical_beneficiary_import',
    ),
    path(
        'housing-units/<str:position>/historical-beneficiaries/register/',
        views.historical_beneficiary_register,
        name='historical_beneficiary_register',
    ),
    path('housing-units/<str:position>/site/create/', views.create_relocation_site, name='create_relocation_site'),
    path('housing-units/<str:position>/unit/create/', views.create_housing_unit, name='create_housing_unit'),
    path('housing-units/<str:position>/<uuid:unit_id>/update/', views.update_housing_unit, name='update_housing_unit'),
    path(
        'housing-units/<str:position>/<uuid:unit_id>/link-plan-polygon/',
        views.link_housing_unit_plan_polygon,
        name='link_housing_unit_plan_polygon',
    ),
    path('housing-units/<str:position>/<uuid:unit_id>/delete/', views.delete_housing_unit, name='delete_housing_unit'),
    path('housing-units/<str:position>/unit/construction/update/', views.add_construction_update, name='add_construction_update'),
    path('housing-units/<str:position>/<uuid:unit_id>/details/', views.get_unit_details, name='get_unit_details'),
    path('housing-units/<str:position>/<uuid:unit_id>/household-member/add/',
        views.add_household_member_for_unit,
        name='add_household_member_for_unit',
    ),
    path(
        'housing-units/<str:position>/<uuid:unit_id>/lot-award/validate/',
        views.validate_lot_award_document,
        name='validate_lot_award_document',
    ),
    path(
        'housing-units/<str:position>/<uuid:unit_id>/explanation-letter/deadline/',
        views.set_explanation_letter_deadline,
        name='set_explanation_letter_deadline',
    ),
    path(
        'housing-units/<str:position>/<uuid:unit_id>/sms/',
        views.send_unit_beneficiary_sms,
        name='send_unit_beneficiary_sms',
    ),
    path(
        'housing-units/<str:position>/<uuid:unit_id>/explanation-letter/sms/',
        views.send_unit_beneficiary_sms,
        name='send_explanation_letter_sms',
    ),
    path(
        'housing-units/<str:position>/<uuid:unit_id>/explanation-letter/upload/',
        views.upload_explanation_letter,
        name='upload_explanation_letter',
    ),
    path(
        'housing-units/<str:position>/<uuid:unit_id>/disqualify-beneficiary/',
        views.disqualify_beneficiary_monitoring,
        name='disqualify_beneficiary_monitoring',
    ),
    path('housing-units/<str:position>/issue-notice/', views.issue_compliance_notice, name='issue_compliance_notice'),

    # Phase 3: Caretaker Monitoring Dashboard
    path('monitoring-dashboard/', views.caretaker_monitoring_dashboard, name='caretaker_monitoring_dashboard'),
    path('monitoring-task/<uuid:task_id>/notify/', views.notify_monitoring_task, name='notify_monitoring_task'),
    path('monitoring-task/<uuid:task_id>/assess/', views.assess_monitoring_report, name='assess_monitoring_report'),

    # Phase 4: Report Submission
    path('monitoring-report/<uuid:task_id>/submit/', views.submit_monitoring_report, name='submit_monitoring_report'),

    # Case Management (Module 5) — UI at /cases/; legacy /units/cases/ paths proxy to cases app
    path('cases/<str:position>/', views.case_management, name='case_management'),
    path('cases/<str:position>/<uuid:case_id>/details/', cases_views.get_case_details, name='get_case_details'),
    path('cases/<str:position>/create/', cases_views.create_case, name='create_case'),
    path('cases/<str:position>/update/', cases_views.update_case, name='update_case'),

    # Blacklist Management
    path('blacklists/<str:position>/', views.blacklist_management, name='blacklist_management'),
]

