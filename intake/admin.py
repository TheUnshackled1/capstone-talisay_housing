from django.contrib import admin
from .models import (
    SMSLog,
    Barangay,
    Applicant,
    HouseholdMember,
    Archive,
)


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'full_name', 'phone_number', 'status', 'channel', 'created_at')
    list_filter = ('status', 'channel', 'created_at')
    search_fields = ('full_name', 'reference_number', 'phone_number')
    readonly_fields = ('reference_number', 'created_at', 'updated_at', 'eligibility_checked_at', 'full_name', 'age')

    fieldsets = (
        ('📋 PERSONAL INFORMATION', {
            'fields': ('full_name', 'last_name', 'first_name', 'middle_name', 'extension_name', 'sex', 'date_of_birth', 'age', 'place_of_birth', 'phone_number'),
        }),
        ('👥 SPOUSE INFORMATION', {
            'fields': ('spouse_name', 'spouse_phone'),
            'classes': ('collapse',),
        }),
        ('🏠 RESIDENCY', {
            'fields': ('barangay', 'current_address', 'years_residing'),
        }),
        ('💰 FINANCIAL', {
            'fields': ('monthly_income', 'household_size', 'occupation', 'employment_status'),
        }),
        ('📝 APPLICATION STATUS', {
            'fields': ('channel', 'status', 'has_property_in_talisay'),
        }),
        ('⚠️ DANGER ZONE (Channel B Only)', {
            'fields': ('danger_zone_type', 'danger_zone_location'),
            'classes': ('collapse',),
            'description': 'Only applies when Channel is "Danger Zone Walk-in"',
        }),
        ('📄 DOCUMENT CHECKLIST (7 Required)', {
            'fields': (
                'doc_brgy_residency',
                'doc_brgy_indigency',
                'doc_cedula',
                'doc_police_clearance',
                'doc_no_property',
                'doc_2x2_picture',
                'doc_sketch_location',
            ),
            'description': 'Check off documents as they are submitted by the applicant',
        }),
        ('⏰ DOCUMENT DEADLINE TRACKING', {
            'fields': ('document_deadline', 'documents_submitted_at'),
            'classes': ('collapse',),
        }),
        ('🔔 SMS NOTIFICATIONS', {
            'fields': ('registration_sms_sent', 'eligibility_sms_sent'),
            'classes': ('collapse',),
        }),
        ('✅ ELIGIBILITY TRACKING', {
            'fields': ('eligibility_checked_by', 'eligibility_checked_at', 'disqualification_reason'),
            'classes': ('collapse',),
        }),
        ('📊 SYSTEM FIELDS (Auto-managed)', {
            'fields': ('reference_number', 'registered_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'relationship', 'applicant', 'date_of_birth')
    list_filter = ('relationship', 'created_at')
    search_fields = ('full_name', 'applicant__full_name')

    fieldsets = (
        ('👤 MEMBER INFORMATION', {
            'fields': ('applicant', 'full_name', 'relationship', 'sex', 'date_of_birth'),
        }),
    )


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'trigger_event', 'status', 'sent_at')
    list_filter = ('status', 'trigger_event', 'sent_at')
    search_fields = ('recipient_phone', 'message_content')
    readonly_fields = ('sent_at',)


@admin.register(Archive)
class ArchiveAdmin(admin.ModelAdmin):
    list_display = ('reference_number_snapshot', 'full_name_snapshot', 'channel', 'archived_by', 'archived_at')
    list_filter = ('channel', 'archived_at', 'queue_type', 'cdrrmo_certified')
    search_fields = ('reference_number_snapshot', 'full_name_snapshot')
    readonly_fields = ('id', 'archived_at', 'reference_number_snapshot', 'full_name_snapshot', 'date_of_birth_snapshot', 'barangay_name_snapshot', 'applicant')

    fieldsets = (
        ('📋 ARCHIVE RECORD', {
            'fields': ('id', 'applicant', 'reference_number_snapshot'),
        }),
        ('👤 APPLICANT SNAPSHOT', {
            'fields': ('full_name_snapshot', 'date_of_birth_snapshot', 'barangay_name_snapshot'),
        }),
        ('🔄 HANDOFF DETAILS', {
            'fields': ('channel', 'queue_type', 'archived_at', 'archived_by'),
        }),
        ('📱 NOTIFICATION', {
            'fields': ('sms_sent', 'sms_sent_at'),
            'classes': ('collapse',),
        }),
        ('🧭 CDRRMO', {
            'fields': ('cdrrmo_certified',),
            'classes': ('collapse',),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )
