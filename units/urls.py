from django.urls import path
from . import views

app_name = 'units'

urlpatterns = [
    path('awarding-draw/', views.lot_awarding_draw, name='lot_awarding_draw'),
]
