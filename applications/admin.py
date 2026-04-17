from django.contrib import admin
from .models import Requirement, RequirementSubmission, Application, SignatoryRouting, FacilitatedService, ElectricityConnection, LotAwarding


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
