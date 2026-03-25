from __future__ import annotations

from typing import Any

from audit.models import AuditEntry, AuditSeverity


def get_client_ip(request) -> str:
    """IP-ja reale e klientit – kontrollon X-Forwarded-For, X-Real-IP, etj."""
    if not request:
        return ""
    # Headers që përdorin reverse proxy-t (nginx, Apache, Cloudflare, etj.)
    for key in ("HTTP_X_FORWARDED_FOR", "HTTP_X_REAL_IP", "HTTP_CF_CONNECTING_IP", "HTTP_X_CLIENT_IP"):
        val = request.META.get(key, "")
        if val:
            ip = val.split(",")[0].strip() if "," in val else val.strip()
            if ip and ip not in ("127.0.0.1", "::1", ""):
                return ip
    addr = (request.META.get("REMOTE_ADDR") or "").strip()
    return addr or ""


def log_audit_event(
    *,
    target: Any | None = None,
    action_type: str,
    actor=None,
    source_screen: str = "",
    reason: str = "",
    changes: dict | None = None,
    metadata: dict | None = None,
    severity: str = AuditSeverity.INFO,
    loan=None,
    app_label: str = "",
    model_name: str = "",
    object_id: str = "",
    object_repr: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> AuditEntry:
    if target is not None:
        model_meta = target._meta
        resolved_app_label = app_label or model_meta.app_label
        resolved_model_name = model_name or model_meta.model_name
        resolved_object_id = object_id or str(getattr(target, "pk", "") or "")
        resolved_object_repr = object_repr or str(target)[:255]
    else:
        resolved_app_label = (app_label or "system")[:64]
        resolved_model_name = (model_name or "event")[:64]
        resolved_object_id = (object_id or "—")[:64]
        resolved_object_repr = (object_repr or action_type or "Ngjarje sistemi")[:255]

    resolved_loan = loan
    if (
        resolved_loan is None
        and target is not None
        and target._meta.app_label == "circulation"
        and target._meta.model_name == "loan"
    ):
        resolved_loan = target

    ip = ip_address
    ua = (user_agent or "").strip()[:512]
    if metadata and not ip:
        ip = metadata.get("ip") or None
    if metadata and not ua:
        ua = (metadata.get("user_agent") or "")[:512]

    return AuditEntry.objects.create(
        actor=actor,
        action_type=(action_type or "").strip()[:64] or "UNKNOWN",
        severity=severity if severity in {AuditSeverity.INFO, AuditSeverity.INCIDENT} else AuditSeverity.INFO,
        app_label=resolved_app_label,
        model_name=resolved_model_name,
        object_id=resolved_object_id,
        object_repr=resolved_object_repr,
        loan=resolved_loan,
        source_screen=(source_screen or "").strip()[:128],
        reason=(reason or "").strip()[:255],
        changes=changes or {},
        metadata=metadata or {},
        ip_address=ip if ip else None,
        user_agent=ua,
    )
