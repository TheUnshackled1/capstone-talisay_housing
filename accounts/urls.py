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
    path('dashboard/oic/', views.dashboard_oic, name='dashboard_oic'),
    path('dashboard/second-member/', views.dashboard_second_member, name='dashboard_second_member'),
    path('dashboard/fourth-member/', views.dashboard_fourth_member, name='dashboard_fourth_member'),
    path('dashboard/fifth-member/', views.dashboard_fifth_member, name='dashboard_fifth_member'),
    path('dashboard/caretaker/', views.dashboard_caretaker, name='dashboard_caretaker'),
    path('dashboard/field/', views.dashboard_field, name='dashboard_field'),

    # OIC-Specific Views
    path('oic/applicants/', views.oic_applicants_overview, name='oic_applicants'),
    path('oic/applications/pending/', views.oic_pending_signature, name='oic_pending_sig'),
    path('oic/analytics/', views.dashboard_oic, name='oic_analytics'),

    # Second Member-Specific Views
    path('second-member/analytics/', views.dashboard_second_member, name='second_member_analytics'),
]

