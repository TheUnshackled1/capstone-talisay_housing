from django.contrib import admin
from .models import (
    Requirement, RequirementSubmission, Application, SignatoryRouting,
    QueueEntry, SMSLog, CDRRMOCertificationProxy,
)


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'group', 'is_required_for_form', 'is_active')
    list_filter = ('group', 'is_required_for_form', 'is_active')
    search_fields = ('code', 'name')

    fieldsets = (
        ('📋 REQUIREMENT', {
            'fields': ('code', 'name', 'group'),
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


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_number', 'applicant', 'status', 'form_generated_at')
    list_filter = ('status', 'form_generated_at', 'created_at')
    search_fields = ('application_number', 'applicant__full_name')
    readonly_fields = ('application_number', 'created_at', 'updated_at', 'form_generated_at')

    fieldsets = (
        ('🏠 APPLICATION', {
            'fields': ('application_number', 'applicant', 'status'),
        }),
        ('✍️ APPLICANT SIGNATURE', {
            'fields': ('applicant_signed_at',),
        }),
        ('🔧 FACILITATED SERVICES', {
            'fields': ('notarial_completed', 'notarial_completed_at', 'engineering_completed', 'engineering_completed_at'),
            'classes': ('collapse',),
        }),
        ('✅ APPROVAL & STANDBY', {
            'fields': ('fully_approved_at', 'standby_position', 'standby_entered_at'),
            'classes': ('collapse',),
        }),
        ('📅 AUDIT TRAIL', {
            'fields': ('form_generated_at', 'form_generated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(SignatoryRouting)
class SignatoryRoutingAdmin(admin.ModelAdmin):
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


@admin.register(CDRRMOCertificationProxy)
class CDRRMOCertificationProxyAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'status', 'disposition_source', 'requested_at', 'certified_at')
    list_filter = ('status', 'disposition_source', 'requested_at')
    search_fields = ('applicant__reference_number', 'applicant__full_name', 'declared_location')
    readonly_fields = ('id', 'requested_at', 'certified_at')
    ordering = ('-requested_at',)

    fieldsets = (
        ('🧭 CDRRMO DISPOSITION (MODULE 2 VIEW)', {
            'fields': ('id', 'applicant', 'status', 'disposition_source', 'declared_location'),
        }),
        ('📝 NOTES', {
            'fields': ('certification_notes', 'office_intake_notes'),
        }),
        ('📅 TIMELINE', {
            'fields': ('requested_at', 'certified_at'),
            'classes': ('collapse',),
        }),
    )

    def delete_model(self, request, obj):
        """Override delete to handle cascading deletes through the real model."""
        from intake.models import CDRRMOCertification
        try:
            # Delete the real object, which will cascade to related photos
            CDRRMOCertification.objects.filter(id=obj.id).delete()
        except Exception as e:
            raise e

    def delete_queryset(self, request, queryset):
        """Override bulk delete to handle cascading deletes through the real model."""
        from intake.models import CDRRMOCertification
        cert_ids = list(queryset.values_list('id', flat=True))
        CDRRMOCertification.objects.filter(id__in=cert_ids).delete()


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'queue_type', 'position', 'status', 'entered_at')
    list_filter = ('queue_type', 'status', 'entered_at')
    search_fields = ('applicant__full_name', 'applicant__reference_number')
    readonly_fields = ('entered_at', 'notified_at', 'completed_at')

    fieldsets = (
        ('⏳ QUEUE ENTRY', {
            'fields': ('applicant', 'queue_type', 'position', 'status'),
        }),
        ('📅 TIMELINE', {
            'fields': ('entered_at', 'notified_at', 'completed_at', 'added_by'),
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
