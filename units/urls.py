from django.urls import path
from . import views

app_name = 'units'

urlpatterns = [
    # Housing Units Monitoring Dashboard (Module 4)
    path('housing-units/<str:position>/', views.housing_units_monitoring, name='housing_units_monitoring'),
    path('housing-units/<str:position>/construction/', views.construction_monitoring, name='construction_monitoring'),
    path('housing-units/<str:position>/site/create/', views.create_relocation_site, name='create_relocation_site'),
    path('housing-units/<str:position>/unit/create/', views.create_housing_unit, name='create_housing_unit'),
    path('housing-units/<str:position>/unit/construction/update/', views.add_construction_update, name='add_construction_update'),
    path('housing-units/<str:position>/<uuid:unit_id>/details/', views.get_unit_details, name='get_unit_details'),
    path('housing-units/<str:position>/issue-notice/', views.issue_compliance_notice, name='issue_compliance_notice'),
    path('housing-units/<str:position>/electricity/', views.electricity_list, name='electricity_list'),
    path('housing-units/<str:position>/electricity/update/', views.update_electricity, name='update_electricity'),

    # Case Management (Module 5)
    path('cases/<str:position>/', views.case_management, name='case_management'),
    path('cases/<str:position>/<uuid:case_id>/details/', views.get_case_details, name='get_case_details'),
    path('cases/<str:position>/create/', views.create_case, name='create_case'),
    path('cases/<str:position>/update/', views.update_case, name='update_case'),
]

