from django.conf import settings
from django.db import models


class NotificationKind(models.TextChoices):
    MEMBER_NEW_STAFF = "member_new_staff", "Anëtar i ri (staf)"
    RESERVATION_NEW_STAFF = "reservation_new_staff", "Kërkesë e re (staf)"
    RESERVATION_CANCELLED_STAFF = "reservation_cancelled_staff", "Kërkesë e anuluar (staf)"
    RESERVATION_SUBMITTED_MEMBER = "reservation_submitted_member", "Kërkesa u dërgua"
    RESERVATION_APPROVED_MEMBER = "reservation_approved_member", "Rezervim i pranuar"
    RESERVATION_REJECTED_MEMBER = "reservation_rejected_member", "Kërkesa u refuzua"
    HOLD_READY_MEMBER = "hold_ready_member", "Gati për marrje"
    LOAN_ACTIVE_MEMBER = "loan_active_member", "Huazim aktiv"
    LOAN_RETURNED_MEMBER = "loan_returned_member", "Libri u kthye"
    LOAN_RENEWED_MEMBER = "loan_renewed_member", "Afati u zgjat"
    LOAN_DUE_TOMORROW_MEMBER = "loan_due_tomorrow_member", "Afati nesër (huazim)"
    RESERVATION_PICKUP_TOMORROW_MEMBER = "reservation_pickup_tomorrow_member", "Marrje nesër (rezervim)"
    RESERVATION_EXPIRED_MEMBER = "reservation_expired_member", "Rezervimi skadoi"


class UserNotification(models.Model):
    """Njoftim në-app për një përdorues (anëtar ose staf)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="in_app_notifications",
    )
    kind = models.CharField(max_length=64, choices=NotificationKind.choices, db_index=True)
    title = models.CharField(max_length=220)
    body = models.TextField(blank=True, default="")
    link_url = models.CharField(max_length=500, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "read_at"]),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        return f"{self.title} → {self.user_id}"
