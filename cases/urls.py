from django.urls import path
from . import views

app_name = 'cases'

urlpatterns = [
    # Case Management Dashboard
    path('<str:position>/', views.case_management_dashboard, name='dashboard'),
    path('<str:position>/<uuid:case_id>/details/', views.get_case_details, name='get_details'),
    path('<str:position>/create/', views.create_case, name='create'),
    path('<str:position>/update/', views.update_case, name='update'),
]
