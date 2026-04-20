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
    user = request.user
    role = getattr(user, "role", None)

    if path.startswith("/anetar/") and role == UserRole.MEMBER:
        list_url = "/anetar/notifications/"
    elif path.startswith("/panel/") and (
        role in (UserRole.ADMIN, UserRole.STAFF)
        or getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    ):
        list_url = "/panel/notifications/"
    else:
        return empty

    unread = UserNotification.objects.filter(user=user, read_at__isnull=True).count()
    preview = list(UserNotification.objects.filter(user=user).order_by("-created_at")[:8])
    return {
        "sl_notif_unread": unread,
        "sl_notif_preview": preview,
        "sl_notif_list_url": list_url,
    }
