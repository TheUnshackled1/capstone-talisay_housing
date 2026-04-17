from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'document_type', 'file_name', 'uploaded_at', 'uploaded_by')
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('applicant__full_name', 'file_name', 'title')
    readonly_fields = ('uploaded_at', 'file_size_display')

    fieldsets = (
        ('📄 DOCUMENT', {
            'fields': ('applicant', 'document_type', 'title', 'requirement_submission'),
        }),
        ('📝 DESCRIPTION', {
            'fields': ('description',),
        }),
        ('📎 FILE DETAILS', {
            'fields': ('file', 'file_name', 'file_size_display', 'mime_type'),
        }),
        ('🔏 UPLOADED BY', {
            'fields': ('uploaded_by', 'uploaded_at'),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )
