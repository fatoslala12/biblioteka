from django.contrib import admin

from notifications.models import UserNotification


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "read_at", "created_at")
    list_filter = ("kind", "read_at")
    search_fields = ("title", "body", "user__username", "user__email")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
