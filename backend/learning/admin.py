from django.contrib import admin
from .models import Notification, NotificationPreference, PushSubscription

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'priority', 'title', 'status', 'scheduled_for', 'read')
    list_filter = ('status', 'type', 'priority', 'read')
    search_fields = ('user__username', 'title', 'body')
    readonly_fields = ('id', 'created_at')

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'academic_enabled', 'community_enabled', 'system_enabled')
    search_fields = ('user__username',)

@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint', 'is_active', 'last_used_at', 'created_at')
    search_fields = ('user__username', 'endpoint')
    list_filter = ('is_active',)
