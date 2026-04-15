from django.contrib import admin
from .models import ISFRecord


class ISFRecordInline(admin.TabularInline):
    """Inline display of ISF records."""
    model = ISFRecord
    extra = 0
    readonly_fields = ['reference_number', 'created_at']
    fields = [
        'reference_number', 'full_name', 'household_members',
        'monthly_income', 'years_residing', 'phone_number',
        'status', 'disqualification_reason'
    ]


@admin.register(ISFRecord)
class ISFRecordAdmin(admin.ModelAdmin):
    """Admin for individual ISF Records."""
    list_display = [
        'reference_number', 'full_name',
        'monthly_income', 'status', 'created_at'
    ]
    list_filter = ['status', 'barangay', 'created_at']
    search_fields = ['reference_number', 'full_name', 'phone_number']
    readonly_fields = ['reference_number', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Record Info', {
            'fields': ('reference_number', 'created_at', 'updated_at')
        }),
        ('ISF Details', {
            'fields': ('full_name', 'household_members', 'monthly_income', 'years_residing', 'phone_number', 'barangay')
        }),
        ('Eligibility', {
            'fields': ('status', 'disqualification_reason', 'eligibility_checked_by', 'eligibility_checked_at')
        }),
        ('Staff Entry', {
            'fields': ('submitted_by_staff',),
            'classes': ('collapse',)
        }),
    )
