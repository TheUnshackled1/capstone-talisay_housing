from django.urls import path
from documents import views

app_name = 'documents'

urlpatterns = [
    path('management/', views.document_management, name='management'),
    path('api/upload/', views.upload_document, name='upload'),
    path('api/mark-present/', views.mark_document_present, name='mark_present'),
    path('api/applicant-documents/', views.get_applicant_documents, name='get_documents'),
]
