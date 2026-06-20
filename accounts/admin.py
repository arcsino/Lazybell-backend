from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'nickname', 'is_active', 'is_staff', 'is_admin', 'registered_at']
    list_filter = ['is_active', 'is_staff', 'is_admin']
    search_fields = ['username', 'nickname']
    ordering = ['-registered_at']
    readonly_fields = ['id', 'registered_at', 'last_login_at', 'token_version']

    fieldsets = (
        (None, {'fields': ('id', 'username', 'password')}),
        ('Personal info', {'fields': ('nickname', 'biography')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_admin')}),
        ('Metadata', {'fields': ('last_login_at', 'registered_at', 'token_version')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'nickname', 'password1', 'password2'),
        }),
    )

    filter_horizontal = []
