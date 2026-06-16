from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('login/google/', views.google_login_start, name='google_login_start'),
    path('logout/', views.logout_view, name='logout'),

    # Main Dashboard (redirects to position-specific dashboard)
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # Position-Specific Dashboards
    path('dashboard/second-member/', views.dashboard_second_member, name='dashboard_second_member'),
    path('dashboard/fourth-member/', views.dashboard_fourth_member, name='dashboard_fourth_member'),
    path('dashboard/caretaker/', views.dashboard_caretaker, name='dashboard_caretaker'),
    path('dashboard/field/', views.dashboard_field, name='dashboard_field'),
    path(
        'dashboard/field/cdrrmo-meta/<uuid:applicant_id>/',
        views.field_applicant_cdrrmo_meta,
        name='field_applicant_cdrrmo_meta',
    ),

    # Case management (Module 5) — UI pages; JSON API stays under /cases/<position>/
    path('second-member/cases/', views.second_member_case_management, name='second_member_cases'),
    path('fourth-member/cases/', views.fourth_member_case_management, name='fourth_member_cases'),
    path('field/cases/', views.field_case_management, name='field_cases'),

    # Second Member-Specific Views
    path('second-member/analytics/', views.second_member_analytics, name='second_member_analytics'),

    # Fourth Member — reports (same datasets as Second Member)
    path('fourth-member/analytics/', views.fourth_member_analytics, name='fourth_member_analytics'),
]

