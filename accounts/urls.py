from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Main Dashboard (redirects to position-specific dashboard)
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    
    # Position-Specific Dashboards
    path('dashboard/head/', views.dashboard_head, name='dashboard_head'),
    path('dashboard/oic/', views.dashboard_oic, name='dashboard_oic'),
    path('dashboard/second-member/', views.dashboard_second_member, name='dashboard_second_member'),
    path('dashboard/third-member/', views.dashboard_third_member, name='dashboard_third_member'),
    path('dashboard/fourth-member/', views.dashboard_fourth_member, name='dashboard_fourth_member'),
    path('dashboard/fifth-member/', views.dashboard_fifth_member, name='dashboard_fifth_member'),
    path('dashboard/caretaker/', views.dashboard_caretaker, name='dashboard_caretaker'),
    path('dashboard/field/', views.dashboard_field, name='dashboard_field'),
]
