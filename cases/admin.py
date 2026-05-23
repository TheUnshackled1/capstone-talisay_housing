from django.contrib import admin
from .models import (
    Case,
    CaseAction,
    CaseEvidence,
    CaseFieldUpdate,
    CaseYearSequence,
    FieldReport,
    FieldSettledIncidentLog,
)


@admin.register(CaseYearSequence)
class CaseYearSequenceAdmin(admin.ModelAdmin):
    list_display = ('year', 'last_number', 'next_case_preview')
    readonly_fields = ('year', 'last_number', 'next_case_preview')
    ordering = ('-year',)

    @admin.display(description='Next case ID')
    def next_case_preview(self, obj):
        return f'CASE-{obj.year}-{obj.last_number + 1:04d}'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'case_type', 'status', 'complainant_name', 'received_at')
    list_filter = ('case_type', 'status', 'received_at')
    search_fields = ('case_number', 'complainant_name', 'subject_name')
    readonly_fields = ('case_number', 'received_at', 'days_open')

    fieldsets = (
        ('📋 CASE INFORMATION', {
            'fields': ('case_number', 'case_type', 'status'),
        }),
        ('👤 COMPLAINANT', {
            'fields': ('complainant_name', 'complainant_phone', 'complainant_applicant'),
        }),
        ('🎯 COMPLAINT DETAILS', {
            'fields': ('initial_description', 'received_at_location', 'received_at', 'received_by'),
        }),
        ('⚠️ SUBJECT OF COMPLAINT (if different)', {
            'fields': ('subject_name', 'subject_applicant', 'related_unit'),
            'classes': ('collapse',),
        }),
        ('🔍 INVESTIGATION', {
            'fields': ('investigation_notes', 'investigated_by', 'investigated_at'),
            'classes': ('collapse',),
        }),
        ('📤 REFERRAL', {
            'fields': ('referred_to', 'referred_at', 'referral_notes'),
            'classes': ('collapse',),
        }),
        ('✅ DECISION & RESOLUTION', {
            'fields': ('decided_by', 'decided_at', 'resolution_notes', 'resolved_at', 'closure_outcome'),
            'classes': ('collapse',),
        }),
        ('📡 MONITORING', {
            'fields': ('monitored_by', 'follow_up_at'),
            'classes': ('collapse',),
        }),
        ('📅 AUDIT TRAIL', {
            'fields': ('updated_at', 'days_open'),
            'classes': ('collapse',),
        }),
    )


@admin.register(CaseAction)
class CaseActionAdmin(admin.ModelAdmin):
    list_display = ('case', 'action_type', 'created_by', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('case__case_number', 'details')


@admin.register(CaseEvidence)
class CaseEvidenceAdmin(admin.ModelAdmin):
    list_display = ('case', 'caption', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('case__case_number', 'caption')
    readonly_fields = ('uploaded_at',)


@admin.register(FieldReport)
class FieldReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'ronda', 'related_unit', 'complaint_type', 'status', 'is_urgent', 'case', 'created_at')
    list_filter = ('status', 'complaint_type', 'is_urgent', 'created_at')
    search_fields = ('subject_name', 'description', 'ronda__username')
    raw_id_fields = ('ronda', 'related_unit', 'subject_applicant', 'reviewed_by', 'case')


@admin.register(FieldSettledIncidentLog)
class FieldSettledIncidentLogAdmin(admin.ModelAdmin):
    list_display = ('related_unit', 'case_type', 'logged_by', 'logged_at')
    list_filter = ('case_type', 'logged_at')
    search_fields = ('description', 'subject_name')
    raw_id_fields = ('related_unit', 'subject_applicant', 'logged_by')


@admin.register(CaseFieldUpdate)
class CaseFieldUpdateAdmin(admin.ModelAdmin):
    list_display = ('case', 'submitted_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('case__case_number', 'note')
    raw_id_fields = ('case', 'submitted_by')

