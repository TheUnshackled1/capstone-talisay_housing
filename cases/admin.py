from django.contrib import admin
from .models import Case, CaseNote


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'case_type', 'status', 'complainant_name', 'received_at')
    list_filter = ('case_type', 'status', 'received_at')
    search_fields = ('case_number', 'complainant_name', 'subject_name')
    readonly_fields = ('case_number', 'received_at')


@admin.register(CaseNote)
class CaseNoteAdmin(admin.ModelAdmin):
    list_display = ('case', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('case__case_number', 'note')
