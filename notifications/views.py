from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone

from notifications.models import UserNotification


def staff_notification_badge_json(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return JsonResponse({"error": "unauthenticated"}, status=401)
    if not user.is_staff:
        return JsonResponse({"error": "forbidden"}, status=403)

    unread = UserNotification.objects.filter(user=user, read_at__isnull=True).count()
    preview = []
    for n in UserNotification.objects.filter(user=user).order_by("-created_at")[:8]:
        preview.append(
            {
                "id": n.id,
                "title": n.title,
                "body": (n.body or "")[:400],
                "unread": n.read_at is None,
                "created_at": timezone.localtime(n.created_at).strftime("%d/%m/%Y %H:%M"),
                "change_url": reverse("admin:notifications_usernotification_change", args=[n.pk]),
            }
        )

    return JsonResponse(
        {
            "unread": unread,
            "preview": preview,
            "admin_changelist": reverse("admin:notifications_usernotification_changelist"),
            "panel_list_url": "/panel/notifications/",
        }
    )
