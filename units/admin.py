from django.contrib import admin
from .models import (
    RelocationSite, HousingUnit, WeeklyReport, LotAward,
    ElectricityConnection, ComplianceNotice, Blacklist,
    OccupancyReport, OccupancyReportDetail, CaseRecord, CaseUpdate, SMSLog
)


@admin.register(RelocationSite)
class RelocationSiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'barangay', 'total_lots', 'is_active')
    list_filter = ('is_active', 'barangay')
    search_fields = ('name', 'code', 'address')

    fieldsets = (
        ('🏗️ SITE INFORMATION', {
            'fields': ('name', 'code', 'barangay'),
        }),
        ('📍 LOCATION', {
            'fields': ('address',),
        }),
        ('📦 CAPACITY', {
            'fields': ('total_blocks', 'total_lots'),
        }),
        ('⚙️ STATUS', {
            'fields': ('is_active', 'caretaker'),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(HousingUnit)
class HousingUnitAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'occupant_name', 'area_sqm')
    list_filter = ('status', 'site', 'created_at')
    search_fields = ('occupant_name', 'occupant_id', 'site__name')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('📍 UNIT LOCATION', {
            'fields': ('site', 'block_number', 'lot_number'),
        }),
        ('📏 UNIT DETAILS', {
            'fields': ('area_sqm', 'status'),
        }),
        ('👤 OCCUPANCY', {
            'fields': ('occupant_name', 'occupant_id'),
        }),
        ('⚠️ NOTICE TRACKING', {
            'fields': ('notice_type', 'notice_date_issued', 'notice_deadline'),
            'classes': ('collapse',),
        }),
        ('🚨 ESCALATION', {
            'fields': ('is_escalated', 'escalation_reason'),
            'classes': ('collapse',),
        }),
        ('📝 LOCATION NOTES', {
            'fields': ('location_notes',),
            'classes': ('collapse',),
        }),
        ('📅 AUDIT TRAIL', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ('unit', 'reported_status', 'last_updated', 'reported_by')
    list_filter = ('reported_status', 'last_updated')
    search_fields = ('unit__lot_number', 'concern_notes')
    readonly_fields = ('last_updated',)

    fieldsets = (
        ('📋 WEEKLY REPORT', {
            'fields': ('unit', 'reported_status'),
        }),
        ('🚨 CONCERNS', {
            'fields': ('concern_notes',),
        }),
        ('🔏 SUBMITTED BY', {
            'fields': ('reported_by', 'last_updated'),
        }),
    )


@admin.register(LotAward)
class LotAwardAdmin(admin.ModelAdmin):
    list_display = ('unit', 'application', 'status', 'awarded_at')
    list_filter = ('status', 'awarded_at', 'via_draw_lots')
    search_fields = ('application__applicant__full_name', 'unit__lot_number')
    readonly_fields = ('awarded_at',)

    fieldsets = (
        ('🏡 LOT ASSIGNMENT', {
            'fields': ('application', 'unit', 'status'),
        }),
        ('🎖️ AWARD DETAILS', {
            'fields': ('awarded_at', 'awarded_by', 'via_draw_lots', 'draw_lots_date'),
        }),
        ('📋 END TRACKING', {
            'fields': ('ended_at', 'end_reason'),
            'classes': ('collapse',),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(ElectricityConnection)
class ElectricityConnectionAdmin(admin.ModelAdmin):
    list_display = ('lot_award', 'status', 'initiated_at', 'completed_at')
    list_filter = ('status', 'initiated_at')
    search_fields = ('lot_award__application__applicant__full_name', 'negros_power_reference')
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('💡 ELECTRICITY CONNECTION', {
            'fields': ('lot_award', 'status'),
        }),
        ('📝 NEGROS POWER', {
            'fields': ('initiated_at', 'initiated_by', 'negros_power_reference'),
        }),
        ('📋 TIMELINE', {
            'fields': ('docs_submitted_at', 'approved_at', 'completed_at'),
            'classes': ('collapse',),
        }),
        ('📝 NOTES', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )


@admin.register(ComplianceNotice)
class ComplianceNoticeAdmin(admin.ModelAdmin):
    list_display = ('unit', 'notice_type', 'status', 'deadline', 'issued_at')
    list_filter = ('notice_type', 'status', 'issued_at', 'deadline')
    search_fields = ('unit__lot_number', 'reason')
    readonly_fields = ('issued_at',)

    fieldsets = (
        ('📜 COMPLIANCE NOTICE', {
            'fields': ('lot_award', 'unit', 'notice_type', 'status'),
        }),
        ('📝 REASON', {
            'fields': ('reason',),
        }),
        ('⏰ TIMELINE', {
            'fields': ('issued_at', 'issued_by', 'days_granted', 'deadline'),
        }),
        ('📋 RESPONSE', {
            'fields': ('response_received_at', 'response_received_by', 'response_notes'),
            'classes': ('collapse',),
        }),
        ('✅ RESOLUTION', {
            'fields': ('resolved_at', 'resolution_decision', 'decided_by'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'reason', 'blacklisted_at', 'blacklisted_by')
    list_filter = ('reason', 'blacklisted_at')
    search_fields = ('applicant__full_name', 'reason_details')
    readonly_fields = ('blacklisted_at',)

    fieldsets = (
        ('❌ BLACKLIST ENTRY', {
            'fields': ('applicant', 'reason'),
        }),
        ('📋 RELATED RECORDS', {
            'fields': ('original_lot_award', 'original_unit'),
        }),
        ('📝 REASON DETAILS', {
            'fields': ('reason_details',),
        }),
        ('🔏 AUDIT TRAIL', {
            'fields': ('blacklisted_at', 'blacklisted_by', 'supporting_notes'),
            'classes': ('collapse',),
        }),
    )


@admin.register(OccupancyReport)
class OccupancyReportAdmin(admin.ModelAdmin):
    list_display = ('site', 'report_week_start', 'status', 'submitted_by')
    list_filter = ('status', 'report_week_start')
    search_fields = ('site__name',)
    readonly_fields = ('submitted_at',)

    fieldsets = (
        ('📋 OCCUPANCY REPORT', {
            'fields': ('site', 'report_week_start', 'report_week_end', 'status'),
        }),
        ('📊 CARETAKER COUNTS', {
            'fields': ('reported_occupied', 'reported_vacant', 'reported_concerns'),
        }),
        ('🔍 FIELD TEAM REVIEW', {
            'fields': ('reviewed_at', 'reviewed_by', 'confirmed_occupied', 'confirmed_vacant'),
            'classes': ('collapse',),
        }),
        ('📝 NOTES', {
            'fields': ('notes', 'discrepancy_notes'),
            'classes': ('collapse',),
        }),
        ('🔏 AUDIT', {
            'fields': ('submitted_at', 'submitted_by'),
            'classes': ('collapse',),
        }),
    )


@admin.register(OccupancyReportDetail)
class OccupancyReportDetailAdmin(admin.ModelAdmin):
    list_display = ('report', 'unit', 'reported_status')
    list_filter = ('reported_status',)
    search_fields = ('report__site__name', 'unit__lot_number')

    fieldsets = (
        ('📋 REPORT DETAIL', {
            'fields': ('report', 'unit', 'reported_status'),
        }),
        ('📝 NOTES', {
            'fields': ('concern_notes',),
        }),
    )


@admin.register(CaseRecord)
class CaseRecordAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'complaint_type', 'status', 'complainant_name', 'date_received')
    list_filter = ('complaint_type', 'status', 'date_received')
    search_fields = ('case_number', 'complainant_name', 'description')
    readonly_fields = ('case_number', 'created_at', 'updated_at')

    fieldsets = (
        ('📋 CASE INFORMATION', {
            'fields': ('case_number', 'site', 'complaint_type', 'status'),
        }),
        ('👤 COMPLAINANT', {
            'fields': ('complainant_name', 'complainant_id'),
        }),
        ('🎯 COMPLAINT DETAILS', {
            'fields': ('description', 'date_received'),
        }),
        ('⚠️ SUBJECT (if different)', {
            'fields': ('subject_name', 'subject_applicant'),
            'classes': ('collapse',),
        }),
        ('🔏 HANDLER ASSIGNMENT', {
            'fields': ('handled_by', 'created_by'),
        }),
        ('📤 REFERRAL', {
            'fields': ('referred_to', 'referral_date'),
            'classes': ('collapse',),
        }),
        ('✅ RESOLUTION', {
            'fields': ('outcome', 'resolved_date'),
            'classes': ('collapse',),
        }),
        ('📅 AUDIT TRAIL', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(CaseUpdate)
class CaseUpdateAdmin(admin.ModelAdmin):
    list_display = ('case', 'updated_by', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('case__case_number', 'notes')
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('📋 CASE UPDATE', {
            'fields': ('case', 'notes'),
        }),
        ('🔏 TRACKED BY', {
            'fields': ('updated_by', 'updated_at'),
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
