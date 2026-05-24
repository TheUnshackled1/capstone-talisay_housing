from django.urls import path
from . import views

app_name = 'cases'

urlpatterns = [
    # Case Management Dashboard
    path('<str:position>/', views.case_dashboard_redirect, name='case_dashboard'),
    path('<str:position>/beneficiary-search/', views.beneficiary_search, name='beneficiary_search'),
    path('<str:position>/<uuid:case_id>/details/', views.get_case_details, name='get_details'),
    path('<str:position>/<uuid:case_id>/evidence/upload/', views.upload_case_evidence, name='upload_evidence'),
    path('<str:position>/<uuid:case_id>/settlement/save/', views.save_field_settlement, name='save_field_settlement'),
    path('<str:position>/create/', views.create_case, name='create'),
    path('<str:position>/settled-log/create/', views.create_settled_incident_log, name='create_settled_log'),
    path('<str:position>/update/', views.update_case, name='update'),
]
