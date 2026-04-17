from django.contrib import admin
from .models import Requirement, RequirementSubmission, Application, SignatoryRouting, FacilitatedService, ElectricityConnection, LotAwarding


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'group', 'is_required_for_form', 'is_active')
    list_filter = ('group', 'is_required_for_form', 'is_active')
    search_fields = ('code', 'name')


@admin.register(RequirementSubmission)
class RequirementSubmissionAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'requirement', 'status', 'verified_at')
    list_filter = ('status', 'verified_at')
    search_fields = ('applicant__full_name', 'requirement__code')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_number', 'applicant', 'status', 'form_generated_at')
    list_filter = ('status', 'form_generated_at', 'created_at')
    search_fields = ('application_number', 'applicant__full_name')
    readonly_fields = ('application_number', 'created_at', 'updated_at')


@admin.register(SignatoryRouting)
class SignatoryRoutingAdmin(admin.ModelAdmin):
    list_display = ('application', 'step', 'action_at', 'action_by')
    list_filter = ('step', 'action_at')
    search_fields = ('application__application_number', 'application__applicant__full_name')


@admin.register(FacilitatedService)
class FacilitatedServiceAdmin(admin.ModelAdmin):
    list_display = ('application', 'service_type', 'status', 'initiated_at')
    list_filter = ('service_type', 'status', 'initiated_at')
    search_fields = ('application__application_number',)


@admin.register(ElectricityConnection)
class ElectricityConnectionAdmin(admin.ModelAdmin):
    list_display = ('application', 'status', 'applied_at', 'connected_at')
    list_filter = ('status', 'applied_at')
    search_fields = ('application__application_number',)


@admin.register(LotAwarding)
class LotAwardingAdmin(admin.ModelAdmin):
    list_display = ('application', 'lot_number', 'block_number', 'awarded_at')
    list_filter = ('awarded_at', 'contract_signed', 'keys_turned_over')
    search_fields = ('application__application_number', 'lot_number')
