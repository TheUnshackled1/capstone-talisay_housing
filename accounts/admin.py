from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for custom User model."""
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'position', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'position')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('last_name', 'first_name')
    
    fieldsets = UserAdmin.fieldsets + (
        ('THA Information', {
            'fields': ('position', 'phone'),
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('THA Information', {
            'fields': ('position', 'phone'),
        }),
    )
