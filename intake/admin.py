from django.contrib import admin
from .models import SMSLog, Blacklist, Barangay, Applicant, HouseholdMember, CDRRMOCertification, QueueEntry


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'full_name', 'phone_number', 'status', 'channel', 'created_at')
    list_filter = ('status', 'channel', 'created_at')
    search_fields = ('full_name', 'reference_number', 'phone_number')
    readonly_fields = ('reference_number', 'created_at', 'updated_at', 'eligibility_checked_at')

    fieldsets = (
        ('📋 PERSONAL INFORMATION', {
            'fields': ('full_name', 'sex', 'date_of_birth', 'age', 'place_of_birth', 'phone_number'),
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


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'reason', 'blacklisted_at', 'blacklisted_by')
    list_filter = ('reason', 'blacklisted_at')
    search_fields = ('full_name', 'phone_number')

    fieldsets = (
        ('❌ BLACKLIST ENTRY', {
            'fields': ('full_name', 'phone_number', 'applicant', 'reason'),
        }),
        ('📝 DETAILS', {
            'fields': ('notes',),
        }),
        ('🔏 AUDIT TRAIL', {
            'fields': ('blacklisted_by', 'blacklisted_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'trigger_event', 'status', 'sent_at')
    list_filter = ('status', 'trigger_event', 'sent_at')
    search_fields = ('recipient_phone', 'message_content')
    readonly_fields = ('sent_at',)


@admin.register(CDRRMOCertification)
class CDRRMOCertificationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'status', 'requested_at', 'certified_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('applicant__full_name',)
    readonly_fields = ('requested_at', 'certified_at')

    fieldsets = (
        ('🏛️ CDRRMO CERTIFICATION', {
            'fields': ('applicant', 'declared_location', 'status'),
        }),
        ('📅 TIMELINE', {
            'fields': ('requested_at', 'requested_by', 'certified_at', 'result_recorded_by'),
        }),
        ('📝 NOTES', {
            'fields': ('certification_notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'queue_type', 'position', 'status', 'entered_at')
    list_filter = ('queue_type', 'status', 'entered_at')
    search_fields = ('applicant__full_name',)
    readonly_fields = ('entered_at', 'notified_at', 'completed_at')

    fieldsets = (
        ('⏳ QUEUE ENTRY', {
            'fields': ('applicant', 'queue_type', 'position', 'status'),
        }),
        ('📅 TIMELINE', {
            'fields': ('entered_at', 'notified_at', 'completed_at', 'added_by'),
        }),
    )
