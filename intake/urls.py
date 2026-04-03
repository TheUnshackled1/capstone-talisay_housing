from django.urls import path
from . import views

app_name = 'intake'

urlpatterns = [
    path('landowner-submission/', views.landowner_form, name='landowner_form'),
]
