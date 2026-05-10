from django.contrib import admin
from .models import (
    Document,
    SMSLog,
    LotAwarding,
    Requirement,
    RequirementSubmission,
    SignatoryRouting,
    FieldInspection,
    FieldInspectionPhoto,
)


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


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'vault_document_type', 'group', 'is_required_for_form', 'is_active')
    list_filter = ('group', 'is_required_for_form', 'is_active')
    search_fields = ('code', 'name')

    fieldsets = (
        ('📋 REQUIREMENT', {
            'fields': ('code', 'name', 'group'),
        }),
        ('📎 DIGITAL VAULT LINK', {
            'fields': ('vault_document_type',),
            'description': 'Set to match an uploaded Document type for scan checklist / Module 2 tracking.',
        }),
        ('⚙️ SETTINGS', {
            'fields': ('is_required_for_form', 'is_active', 'order'),
        }),
        ('📝 DESCRIPTION', {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
    )


@admin.register(RequirementSubmission)
class RequirementSubmissionAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'requirement', 'status', 'verified_at')
    list_filter = ('status', 'verified_at')
    search_fields = ('applicant__full_name', 'requirement__code')
    readonly_fields = ('submitted_at', 'verified_at')

    fieldsets = (
        ('📄 SUBMISSION', {
            'fields': ('applicant', 'requirement', 'status'),
        }),
        ('✅ VERIFICATION', {
            'fields': ('verified_at', 'verified_by', 'rejection_reason'),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(SignatoryRouting)
class SignatoryRoutingStepAdmin(admin.ModelAdmin):
    list_display = ('application', 'step', 'action_at', 'action_by')
    list_filter = ('step', 'action_at')
    search_fields = ('application__application_number', 'application__applicant__full_name')
    readonly_fields = ('action_at',)

    fieldsets = (
        ('📋 ROUTING STEP', {
            'fields': ('application', 'step'),
        }),
        ('🔏 ACTION', {
            'fields': ('action_at', 'action_by'),
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


class FieldInspectionPhotoInline(admin.TabularInline):
    model = FieldInspectionPhoto
    extra = 0


@admin.register(FieldInspection)
class FieldInspectionAdmin(admin.ModelAdmin):
    list_display = ('application', 'status', 'submitted_by', 'submitted_at', 'confirmed_by', 'confirmed_at')
    list_filter = ('status', 'submitted_at', 'confirmed_at')
    search_fields = ('application__application_number', 'application__applicant__full_name')
    readonly_fields = ('submitted_at',)
    inlines = [FieldInspectionPhotoInline]


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
