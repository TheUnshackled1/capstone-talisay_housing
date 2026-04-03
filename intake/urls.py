from django.urls import path
from . import views

urlpatterns = [
    path('landowner-submission/', views.landowner_form, name='landowner_form'),
]
