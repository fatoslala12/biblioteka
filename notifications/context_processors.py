from notifications.models import UserNotification


def notification_bell(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            "sl_notif_unread": 0,
            "sl_notif_preview": [],
            "sl_notif_list_url": "",
        }
    user = request.user
    unread = UserNotification.objects.filter(user=user, read_at__isnull=True).count()
    preview = list(UserNotification.objects.filter(user=user).order_by("-created_at")[:8])
    from accounts.models import UserRole

    if getattr(user, "role", None) == UserRole.MEMBER:
        list_url = "/anetar/njoftime/"
    else:
        list_url = "/panel/njoftime/"
    return {
        "sl_notif_unread": unread,
        "sl_notif_preview": preview,
        "sl_notif_list_url": list_url,
    }
