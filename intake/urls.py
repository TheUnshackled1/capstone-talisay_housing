from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    # Public landowner portal
    path('landowner-submission/', views.landowner_form, name='landowner_form'),
    
    # Staff applicants management (Joie - Second Member, Jocel - Fourth Member)
    # Consolidated view for all intake channels (replaces old submission_list)
    path('staff/applicants/', views.applicants_list, name='applicants_list'),
    
    # Individual review pages (kept for specific ISF review workflow)
    path('staff/submissions/<uuid:submission_id>/', views.submission_review, name='submission_review'),
    path('staff/isf/<uuid:isf_id>/review/', views.isf_review, name='isf_review'),
]
