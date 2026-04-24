from django.contrib import admin
from .models import Document, SMSLog, FacilitatedService, ElectricityConnection, LotAwarding


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


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'trigger_event', 'status', 'sent_at')
    list_filter = ('trigger_event', 'status', 'sent_at')
    search_fields = ('recipient_phone', 'message_content')
    readonly_fields = ('sent_at', 'id')

    fieldsets = (
        ('SMS DETAILS', {
            'fields': ('recipient_phone', 'message_content', 'trigger_event'),
        }),
        ('STATUS', {
            'fields': ('status', 'error_message', 'external_id'),
        }),
        ('RECIPIENT', {
            'fields': ('applicant',),
            'classes': ('collapse',),
        }),
        ('AUDIT TRAIL', {
            'fields': ('id', 'sent_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(FacilitatedService)
class FacilitatedServiceAdmin(admin.ModelAdmin):
    list_display = ('application', 'service_type', 'status', 'initiated_at')
    list_filter = ('service_type', 'status', 'initiated_at')
    search_fields = ('application__application_number',)
    readonly_fields = ('initiated_at', 'completed_at')

    fieldsets = (
        ('🔧 SERVICE', {
            'fields': ('application', 'service_type', 'status'),
        }),
        ('📅 TIMELINE', {
            'fields': ('initiated_at', 'initiated_by', 'completed_at', 'completed_by'),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(ElectricityConnection)
class ElectricityConnectionAdmin(admin.ModelAdmin):
    list_display = ('application', 'status', 'applied_at', 'connected_at')
    list_filter = ('status', 'applied_at')
    search_fields = ('application__application_number',)
    readonly_fields = ('applied_at', 'connected_at')

    fieldsets = (
        ('💡 ELECTRICITY CONNECTION', {
            'fields': ('application', 'status'),
        }),
        ('📝 NEGROS POWER APPLICATION', {
            'fields': ('applied_at', 'applied_by', 'negros_power_reference'),
        }),
        ('🔍 INSPECTION', {
            'fields': ('inspection_date', 'inspection_result'),
            'classes': ('collapse',),
        }),
        ('✅ CONNECTION COMPLETION', {
            'fields': ('connected_at', 'meter_number'),
            'classes': ('collapse',),
        }),
        ('⚠️ ISSUES', {
            'fields': ('issue_description', 'issue_resolved_at'),
            'classes': ('collapse',),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(LotAwarding)
class LotAwardingAdmin(admin.ModelAdmin):
    list_display = ('application', 'lot_number', 'block_number', 'awarded_at')
    list_filter = ('awarded_at', 'contract_signed', 'keys_turned_over')
    search_fields = ('application__application_number', 'lot_number')
    readonly_fields = ('awarded_at',)

    fieldsets = (
        ('🏡 LOT AWARD', {
            'fields': ('application', 'lot_number', 'block_number', 'site_name'),
        }),
        ('🎖️ AWARD CEREMONY', {
            'fields': ('awarded_at', 'awarded_by'),
        }),
        ('📜 CONTRACT', {
            'fields': ('contract_signed', 'contract_signed_at'),
            'classes': ('collapse',),
        }),
        ('🔑 KEY TURNOVER', {
            'fields': ('keys_turned_over', 'keys_turned_over_at'),
            'classes': ('collapse',),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )
