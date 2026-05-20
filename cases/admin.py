from django.contrib import admin
from .models import Case, CaseAction, CaseEvidence


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
            'fields': ('follow_up_at',),
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


