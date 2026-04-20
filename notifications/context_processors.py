from accounts.models import UserRole
from notifications.models import UserNotification


def notification_bell(request):
    empty = {
        "sl_notif_unread": 0,
        "sl_notif_preview": [],
        "sl_notif_list_url": "",
    }
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return empty
    path = getattr(request, "path", "") or ""
    if not path.startswith("/anetar/"):
        return empty
    user = request.user
    if getattr(user, "role", None) != UserRole.MEMBER:
        return empty

    unread = UserNotification.objects.filter(user=user, read_at__isnull=True).count()
    preview = list(UserNotification.objects.filter(user=user).order_by("-created_at")[:8])
    return {
        "sl_notif_unread": unread,
        "sl_notif_preview": preview,
        "sl_notif_list_url": "/anetar/notifications/",
    }
