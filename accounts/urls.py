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

    # HEAD-Specific Views
    path('head/applicants/', views.head_applicants_overview, name='head_applicants'),
    path('head/applications/pending/', views.head_pending_signature, name='head_pending_sig'),
    path('head/analytics/', views.head_analytics_dashboard, name='head_analytics'),
    path('head/reports/', views.head_monthly_reports, name='head_reports'),

    # OIC-Specific Views
    path('oic/applicants/', views.oic_applicants_overview, name='oic_applicants'),
    path('oic/applications/pending/', views.oic_pending_signature, name='oic_pending_sig'),
    path('oic/analytics/', views.head_analytics_dashboard, name='oic_analytics'),

    # Second Member-Specific Views
    path('second-member/analytics/', views.head_analytics_dashboard, name='second_member_analytics'),
    path('second-member/reports/', views.head_monthly_reports, name='second_member_reports'),

    # Third Member-Specific Views
    path('third-member/applicants/', views.third_member_applicants_overview, name='third_member_applicants'),
    path('third-member/analytics/', views.head_analytics_dashboard, name='third_member_analytics'),
    path('third-member/reports/', views.head_monthly_reports, name='third_member_reports'),

    # Fourth Member-Specific Views
    path('fourth-member/analytics/', views.head_analytics_dashboard, name='fourth_member_analytics'),
    path('fourth-member/reports/', views.head_monthly_reports, name='fourth_member_reports'),

    # Fifth Member-Specific Views
    path('fifth-member/analytics/', views.head_analytics_dashboard, name='fifth_member_analytics'),
    path('fifth-member/reports/', views.head_monthly_reports, name='fifth_member_reports'),
]

