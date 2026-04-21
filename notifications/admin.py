from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from notifications.models import UserNotification


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("title_display", "user", "kind", "status_display", "created_at")
    list_filter = ("kind", "read_at")
    search_fields = ("title", "body", "user__username", "user__email")
    readonly_fields = ("user", "kind", "title", "body", "link_url", "read_at", "created_at")
    ordering = ("-created_at",)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if object_id and request.GET.get("mark_read") == "1":
            UserNotification.objects.filter(pk=object_id, read_at__isnull=True).update(read_at=timezone.now())
        extra_context = extra_context or {}
        extra_context.update(
            {
                "show_save": False,
                "show_save_and_continue": False,
                "show_save_and_add_another": False,
                "show_delete": False,
            }
        )
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

    @admin.display(description="Titulli")
    def title_display(self, obj: UserNotification):
        if obj.read_at is None:
            return format_html("<strong>{}</strong>", obj.title)
        return format_html('<span style="opacity:.82;">{}</span>', obj.title)

    @admin.display(description="Statusi")
    def status_display(self, obj: UserNotification):
        if obj.read_at is None:
            return format_html(
                '<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;background:#dcfce7;color:#065f46;font-weight:800;">E palexuar</span>'
            )
        return format_html(
            '<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;background:#e2e8f0;color:#334155;font-weight:700;">E lexuar</span>'
        )
