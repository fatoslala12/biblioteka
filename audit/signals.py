from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from audit.models import AuditSeverity
from audit.services import get_client_ip, log_audit_event


def _meta_from_request(request):
    if not request:
        return {}
    return {
        "ip": get_client_ip(request),
        "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:255],
        "path": (request.path or "")[:255],
    }


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    meta = _meta_from_request(request)
    log_audit_event(
        target=user,
        action_type="AUTH_LOGIN_SUCCESS",
        actor=user,
        source_screen=(request.path if request else "") or "auth.login",
        metadata=meta,
        severity=AuditSeverity.INFO,
        ip_address=meta.get("ip") or None,
        user_agent=meta.get("user_agent", ""),
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    meta = _meta_from_request(request)
    if user is not None:
        log_audit_event(
            target=user,
            action_type="AUTH_LOGOUT",
            actor=user,
            source_screen=(request.path if request else "") or "auth.logout",
            metadata=meta,
            severity=AuditSeverity.INFO,
            ip_address=meta.get("ip") or None,
            user_agent=meta.get("user_agent", ""),
        )
        return

    log_audit_event(
        target=None,
        action_type="AUTH_LOGOUT",
        actor=None,
        app_label="accounts",
        model_name="user",
        object_id="—",
        object_repr="Logout pa përdorues aktiv",
        source_screen=(request.path if request else "") or "auth.logout",
        metadata=meta,
        severity=AuditSeverity.INFO,
        ip_address=meta.get("ip") or None,
        user_agent=meta.get("user_agent", ""),
    )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    username = (credentials or {}).get("username") or (credentials or {}).get("email") or ""
    username = str(username).strip()

    User = get_user_model()
    existing_user = User.objects.filter(username=username).first() if username else None

    meta = _meta_from_request(request)
    if existing_user is not None:
        log_audit_event(
            target=existing_user,
            action_type="AUTH_LOGIN_FAILED",
            actor=None,
            source_screen=(request.path if request else "") or "auth.login",
            reason="Fjalëkalim ose kredenciale të pasakta.",
            metadata=meta,
            severity=AuditSeverity.INCIDENT,
            ip_address=meta.get("ip") or None,
            user_agent=meta.get("user_agent", ""),
        )
        return

    log_audit_event(
        target=None,
        action_type="AUTH_LOGIN_FAILED",
        actor=None,
        app_label="accounts",
        model_name="user",
        object_id=username or "unknown",
        object_repr=f"Përdorues i panjohur: {username or '—'}",
        source_screen=(request.path if request else "") or "auth.login",
        reason="Tentativë hyrjeje me llogari që nuk ekziston ose kredenciale të pasakta.",
        metadata=meta,
        severity=AuditSeverity.INCIDENT,
        ip_address=meta.get("ip") or None,
        user_agent=meta.get("user_agent", ""),
    )
