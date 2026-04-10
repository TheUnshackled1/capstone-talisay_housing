from django.urls import path
from documents import views

app_name = 'documents'

urlpatterns = [
    path('management/', views.document_management, name='management'),
]
