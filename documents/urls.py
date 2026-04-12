from django.urls import path
from documents import views

app_name = 'documents'

urlpatterns = [
    path('<str:position>/management/', views.document_management, name='management'),
    path('<str:position>/api/upload/', views.upload_document, name='upload'),
    path('<str:position>/api/mark-present/', views.mark_document_present, name='mark_present'),
    path('<str:position>/api/applicant-documents/', views.get_applicant_documents, name='get_documents'),
    path('<str:position>/<uuid:doc_id>/delete/', views.delete_document, name='delete'),
]
