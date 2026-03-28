from django.conf import settings
from django.db import models


class AuditSeverity(models.TextChoices):
    INFO = "INFO", "Informative"
    INCIDENT = "INCIDENT", "Incident"


class AuditEntry(models.Model):
    ACTION_TYPE_LABELS = {
        "AUTH_LOGIN_SUCCESS": "Hyrje e suksesshme",
        "AUTH_LOGIN_FAILED": "Hyrje e dështuar",
        "AUTH_LOGOUT": "Dalje nga sistemi",
        "MEMBER_PROFILE_UPDATED": "Anëtari përditësoi profilin",
        "MEMBER_PROFILE_UPDATE_FAILED": "Dështoi përditësimi i profilit të anëtarit",
        "MEMBER_PASSWORD_CHANGED": "Anëtari ndryshoi fjalëkalimin",
        "MEMBER_PASSWORD_CHANGE_FAILED": "Dështoi ndryshimi i fjalëkalimit të anëtarit",
        "MEMBER_RESERVATION_REQUEST_CANCELLED": "Anëtari anuloi kërkesën e rezervimit",
        "LOAN_CREATED_DIRECT": "Huazim i krijuar (direkt)",
        "LOAN_CREATED_QUICK": "Huazim i krijuar (modal i shpejtë)",
        "LOAN_CREATED_MANUAL": "Huazim i krijuar manualisht",
        "LOAN_CREATED_FROM_RESERVATION": "Huazim i krijuar nga rezervimi",
        "LOAN_UPDATED_MANUAL": "Huazim i përditësuar manualisht",
        "LOAN_RENEWED": "Huazim i zgjatur",
        "LOAN_RETURNED": "Huazim i dorëzuar",
        "RESERVATION_CREATED": "Rezervim i krijuar",
        "RESERVATION_CREATED_MANUAL": "Rezervim i krijuar manualisht",
        "RESERVATION_UPDATED_MANUAL": "Rezervim i përditësuar manualisht",
        "RESERVATION_AUTO_EXPIRED": "Rezervim i skaduar automatikisht",
        "RESERVATION_BORROWED": "Rezervimi u kthye në huazim",
        "RESERVATION_REQUEST_CREATED": "Kërkesë rezervimi e krijuar",
        "RESERVATION_REQUEST_CREATED_MANUAL": "Kërkesë rezervimi e krijuar manualisht",
        "RESERVATION_REQUEST_UPDATED_MANUAL": "Kërkesë rezervimi e përditësuar manualisht",
        "RESERVATION_REQUEST_APPROVED": "Kërkesë rezervimi e miratuar",
        "RESERVATION_REQUEST_REJECTED": "Kërkesë rezervimi e refuzuar",
        "FINE_CREATED_MANUAL": "Gjobë e krijuar manualisht",
        "FINE_UPDATED_MANUAL": "Gjobë e përditësuar manualisht",
        "POLICY_CREATED_MANUAL": "Politikë e krijuar manualisht",
        "POLICY_UPDATED_MANUAL": "Politikë e përditësuar manualisht",
        "CONTACT_MESSAGE_REPLIED": "Përgjigje e dërguar për mesazhin e kontaktit",
    }

    SCREEN_LABELS = {
        "auth.login": "Hyrje",
        "auth.logout": "Dalje",
        "member.profile.update": "Anëtar > Profili > Përditëso",
        "member.password.change": "Anëtar > Fjalëkalimi > Ndrysho",
        "member.request.cancel": "Anëtar > Kërkesat > Anulo",
        "/hyr/": "Faqja e hyrjes",
        "/dil/": "Dalje",
        "/admin/login/": "Admin > Hyrje",
        "/admin/logout/": "Admin > Dalje",
        "admin.loan.quick_modal": "Admin > Huazime > Modal i shpejtë",
        "admin.loan.quick_form": "Admin > Huazime > Forma e shpejtë",
        "admin.loan.change_form": "Admin > Huazime > Ndrysho",
        "admin.loan.list.return_early": "Admin > Huazime > Lista (Dorëzo)",
        "admin.reservation.change_form": "Admin > Rezervime > Ndrysho",
        "admin.reservation.list.borrow_now": "Admin > Rezervime > Lista (Huazo)",
        "admin.reservation.list.auto_expire": "Admin > Rezervime > Lista (Skadim automatik)",
        "system.reservation.auto_expire": "Sistem > Rezervime > Skadim automatik",
        "admin.reservationrequest.quick_modal": "Admin > Kërkesa > Modal i shpejtë",
        "admin.reservationrequest.change_form": "Admin > Kërkesa > Ndrysho",
        "admin.reservationrequest.list.approve_now": "Admin > Kërkesa > Lista (Mirato)",
        "admin.reservationrequest.list.reject_now": "Admin > Kërkesa > Lista (Refuzo)",
        "admin.fine.change_form": "Admin > Gjoba > Ndrysho",
        "admin.policy.change_form": "Admin > Politika > Ndrysho",
        "admin.contactmessage.reply": "Admin > Mesazhet > Përgjigju",
        "member.book_detail.reserve": "Anëtar > Libri > Rezervo",
        "api.circulation.checkout": "API > Checkout",
        "api.circulation.return": "API > Return",
        "api.circulation.renew": "API > Renew",
    }

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
        verbose_name="Përdoruesi",
    )
    action_type = models.CharField(max_length=64, verbose_name="Veprimi")
    severity = models.CharField(
        max_length=16,
        choices=AuditSeverity.choices,
        default=AuditSeverity.INFO,
        verbose_name="Niveli",
    )

    app_label = models.CharField(max_length=64, verbose_name="Aplikacioni")
    model_name = models.CharField(max_length=64, verbose_name="Modeli")
    object_id = models.CharField(max_length=64, verbose_name="ID objekti")
    object_repr = models.CharField(max_length=255, blank=True, default="", verbose_name="Objekti")

    loan = models.ForeignKey(
        "circulation.Loan",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="audit_entries",
        verbose_name="Huazimi",
    )

    source_screen = models.CharField(max_length=128, blank=True, default="", verbose_name="Ekrani burim")
    reason = models.CharField(max_length=255, blank=True, default="", verbose_name="Arsye")

    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    user_agent = models.CharField(max_length=512, blank=True, default="", verbose_name="User-Agent / Browser")
    changes = models.JSONField(default=dict, blank=True, verbose_name="Ndryshimet")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadata")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Krijuar më")

    class Meta:
        verbose_name = "Auditim"
        verbose_name_plural = "Auditime"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["app_label", "model_name", "object_id"]),
            models.Index(fields=["action_type", "severity"]),
            models.Index(fields=["loan", "created_at"]),
        ]

    def __str__(self) -> str:
        base = f"{self.action_type} • {self.app_label}.{self.model_name}#{self.object_id}"
        if self.actor_id:
            return f"{base} nga {self.actor}"
        return base

    @property
    def action_type_sq(self) -> str:
        return self.ACTION_TYPE_LABELS.get(self.action_type, self.action_type.replace("_", " ").title())

    @property
    def screen_sq(self) -> str:
        if not self.source_screen:
            return "—"
        return self.SCREEN_LABELS.get(self.source_screen, self.source_screen)

    @property
    def browser_display(self) -> str:
        ua = (self.user_agent or "").strip() or (self.metadata or {}).get("user_agent", "")
        if not ua:
            return "—"
        ua_lower = ua.lower()
        if "edg/" in ua_lower or "edge/" in ua_lower:
            return "Edge"
        if "opr/" in ua_lower or "opera" in ua_lower:
            return "Opera"
        if "chrome/" in ua_lower and "chromium" not in ua_lower:
            return "Chrome"
        if "firefox/" in ua_lower or "fxios" in ua_lower:
            return "Firefox"
        if "safari/" in ua_lower and "chrome" not in ua_lower:
            return "Safari"
        return ua[:50] + ("…" if len(ua) > 50 else "")
