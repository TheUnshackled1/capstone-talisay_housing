from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    # Public landowner portal
    path('landowner-submission/', views.landowner_form, name='landowner_form'),
    
    # Staff review interfaces (Jocel)
    path('staff/submissions/', views.submission_list, name='submission_list'),
    path('staff/submissions/<uuid:submission_id>/', views.submission_review, name='submission_review'),
    path('staff/isf/<uuid:isf_id>/review/', views.isf_review, name='isf_review'),
]
