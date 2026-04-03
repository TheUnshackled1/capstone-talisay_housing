from django.contrib import admin
from .models import LandownerSubmission, ISFRecord


class ISFRecordInline(admin.TabularInline):
    """Inline display of ISF records within a submission."""
    model = ISFRecord
    extra = 0
    readonly_fields = ['reference_number', 'created_at']
    fields = [
        'reference_number', 'full_name', 'household_members',
        'monthly_income', 'years_residing', 'phone_number',
        'status', 'disqualification_reason'
    ]


@admin.register(LandownerSubmission)
class LandownerSubmissionAdmin(admin.ModelAdmin):
    """Admin for Landowner Submissions."""
    list_display = [
        'reference_number', 'landowner_name', 'barangay',
        'isf_count', 'status', 'submitted_at'
    ]
    list_filter = ['status', 'barangay', 'submitted_at']
    search_fields = ['reference_number', 'landowner_name', 'property_address']
    readonly_fields = ['reference_number', 'submitted_at']
    ordering = ['-submitted_at']
    inlines = [ISFRecordInline]
    
    fieldsets = (
        ('Submission Info', {
            'fields': ('reference_number', 'status', 'submitted_at')
        }),
        ('Landowner Details', {
            'fields': ('landowner_name', 'landowner_phone', 'landowner_email')
        }),
        ('Property', {
            'fields': ('property_address', 'barangay')
        }),
        ('Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'notes'),
            'classes': ('collapse',)
        }),
    )

    def isf_count(self, obj):
        return obj.isf_count
    isf_count.short_description = 'ISF Count'


@admin.register(ISFRecord)
class ISFRecordAdmin(admin.ModelAdmin):
    """Admin for individual ISF Records."""
    list_display = [
        'reference_number', 'full_name', 'submission',
        'monthly_income', 'status', 'created_at'
    ]
    list_filter = ['status', 'submission__barangay', 'created_at']
    search_fields = ['reference_number', 'full_name', 'submission__landowner_name']
    readonly_fields = ['reference_number', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Record Info', {
            'fields': ('reference_number', 'submission')
        }),
        ('ISF Details', {
            'fields': ('full_name', 'household_members', 'monthly_income', 'years_residing', 'phone_number')
        }),
        ('Eligibility', {
            'fields': ('status', 'disqualification_reason', 'eligibility_checked_by', 'eligibility_checked_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
