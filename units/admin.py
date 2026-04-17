from django.contrib import admin
from .models import (
    RelocationSite, HousingUnit, WeeklyReport, LotAward,
    ElectricityConnection, ComplianceNotice, Blacklist,
    OccupancyReport, OccupancyReportDetail, CaseRecord, CaseUpdate
)


@admin.register(RelocationSite)
class RelocationSiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'barangay', 'total_lots', 'is_active')
    list_filter = ('is_active', 'barangay')
    search_fields = ('name', 'code', 'address')


@admin.register(HousingUnit)
class HousingUnitAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'occupant_name', 'area_sqm')
    list_filter = ('status', 'site', 'created_at')
    search_fields = ('occupant_name', 'occupant_id', 'site__name')


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ('unit', 'reported_status', 'last_updated', 'reported_by')
    list_filter = ('reported_status', 'last_updated')
    search_fields = ('unit__lot_number', 'concern_notes')


@admin.register(LotAward)
class LotAwardAdmin(admin.ModelAdmin):
    list_display = ('unit', 'application', 'status', 'awarded_at')
    list_filter = ('status', 'awarded_at', 'via_draw_lots')
    search_fields = ('application__applicant__full_name', 'unit__lot_number')


@admin.register(ElectricityConnection)
class ElectricityConnectionAdmin(admin.ModelAdmin):
    list_display = ('lot_award', 'status', 'initiated_at', 'completed_at')
    list_filter = ('status', 'initiated_at')
    search_fields = ('lot_award__application__applicant__full_name', 'negros_power_reference')


@admin.register(ComplianceNotice)
class ComplianceNoticeAdmin(admin.ModelAdmin):
    list_display = ('unit', 'notice_type', 'status', 'deadline', 'issued_at')
    list_filter = ('notice_type', 'status', 'issued_at', 'deadline')
    search_fields = ('unit__lot_number', 'reason')


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'reason', 'blacklisted_at', 'blacklisted_by')
    list_filter = ('reason', 'blacklisted_at')
    search_fields = ('applicant__full_name', 'reason_details')


@admin.register(OccupancyReport)
class OccupancyReportAdmin(admin.ModelAdmin):
    list_display = ('site', 'report_week_start', 'status', 'submitted_by')
    list_filter = ('status', 'report_week_start')
    search_fields = ('site__name',)


@admin.register(OccupancyReportDetail)
class OccupancyReportDetailAdmin(admin.ModelAdmin):
    list_display = ('report', 'unit', 'reported_status')
    list_filter = ('reported_status',)
    search_fields = ('report__site__name', 'unit__lot_number')


@admin.register(CaseRecord)
class CaseRecordAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'complaint_type', 'status', 'complainant_name', 'date_received')
    list_filter = ('complaint_type', 'status', 'date_received')
    search_fields = ('case_number', 'complainant_name', 'description')
    readonly_fields = ('case_number', 'created_at', 'updated_at')


@admin.register(CaseUpdate)
class CaseUpdateAdmin(admin.ModelAdmin):
    list_display = ('case', 'updated_by', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('case__case_number', 'notes')
