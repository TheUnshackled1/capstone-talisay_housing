from django.urls import path
from . import views

app_name = 'cases'

urlpatterns = [
    # Case Management Dashboard
    path('', views.case_management_dashboard, name='dashboard'),
    path('<uuid:case_id>/details/', views.get_case_details, name='get_details'),
    path('create/', views.create_case, name='create'),
    path('update/', views.update_case, name='update'),
]
