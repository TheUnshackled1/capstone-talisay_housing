from django.contrib import admin
from .models import SMSLog, Blacklist, Barangay, Applicant, HouseholdMember, CDRRMOCertification, QueueEntry


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'full_name', 'phone_number', 'status', 'channel', 'created_at')
    list_filter = ('status', 'channel', 'created_at')
    search_fields = ('full_name', 'reference_number', 'phone_number')
    readonly_fields = ('reference_number', 'created_at', 'updated_at')


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'relationship', 'applicant', 'date_of_birth')
    list_filter = ('relationship', 'created_at')
    search_fields = ('full_name', 'applicant__full_name')


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'reason', 'blacklisted_at', 'blacklisted_by')
    list_filter = ('reason', 'blacklisted_at')
    search_fields = ('full_name', 'phone_number')


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


@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'queue_type', 'position', 'status', 'entered_at')
    list_filter = ('queue_type', 'status', 'entered_at')
    search_fields = ('applicant__full_name',)
