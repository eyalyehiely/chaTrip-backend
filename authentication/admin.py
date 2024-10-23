from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Otp, Conversation

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    Custom admin for CustomUser model.
    """

    list_display = ('username', 'saving_places', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'date_joined')
    search_fields = ('username',)
    ordering = ('username',)
    filter_horizontal = ()

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'saving_places')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )

@admin.register(Otp)
class OtpAdmin(admin.ModelAdmin):
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

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Admin interface for Conversation model.
    """
    list_display = ('user', 'title', 'timestamp')
    search_fields = ('user__username', 'title')
    list_filter = ('timestamp',)
    ordering = ('-timestamp',)
    readonly_fields = ('user', 'messages', 'timestamp')

    def has_add_permission(self, request):
        """ Prevent adding conversations via the admin panel. """
        return False

    def has_change_permission(self, request, obj=None):
        """ Prevent editing conversations via the admin panel. """
        return False