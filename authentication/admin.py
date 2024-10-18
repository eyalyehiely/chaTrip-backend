# authentication/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, OTP

class OTPInline(admin.TabularInline):
    """
    Inline display of OTPs within the CustomUser admin page.
    """
    model = OTP
    fields = ('created_at', 'is_used', 'is_expired')
    readonly_fields = ('created_at', 'is_used', 'is_expired')
    extra = 0
    can_delete = False
    show_change_link = False

    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired?'

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    Custom admin for CustomUser model with OTP inline.
    """

    list_display = ('username', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'date_joined')
    search_fields = ('username',)
    ordering = ('username',)
    filter_horizontal = ()

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )

    inlines = [OTPInline]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('username',)
        return self.readonly_fields

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """
    Admin interface for OTP model.
    """
    list_display = ('user', 'created_at', 'is_used', 'is_expired')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__username', 'code_hash')
    ordering = ('-created_at',)
    readonly_fields = ('user', 'code_hash', 'created_at', 'is_used')

    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired?'