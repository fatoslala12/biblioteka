from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from audit.services import log_audit_event
from .models import LibraryPolicy, LoanRule


class LoanRuleInline(admin.TabularInline):
    model = LoanRule
    extra = 0


def _build_audit_timeline_html(*, app_label: str, model_name: str, object_id: str) -> str:
    from audit.models import AuditEntry

    entries = (
        AuditEntry.objects.select_related("actor")
        .filter(app_label=app_label, model_name=model_name, object_id=str(object_id))
        .order_by("-created_at")[:12]
    )
    if not entries:
        return "—"
    rows = []
    for e in entries:
        actor = e.actor.get_username() if e.actor_id else "Sistem"
        when = timezone.localtime(e.created_at).strftime("%d/%m/%Y %H:%M")
        rows.append(
            format_html(
                (
                    "<li style='padding:9px 11px;border:1px solid rgba(148,163,184,.25);"
                    "border-radius:12px;background:#fff;'>"
                    "<div style='display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;'>"
                    "<b>{}</b><small style='opacity:.78'>{}</small></div>"
                    "<div style='margin-top:4px;font-size:12px;opacity:.86'>Aktor: <b>{}</b></div>"
                    "</li>"
                ),
                e.action_type_sq,
                when,
                actor,
            )
        )
    timeline_items = format_html_join("", "{}", ((row,) for row in rows))
    return format_html("<ul style='list-style:none;padding:0;margin:0;display:grid;gap:8px;'>{}</ul>", timeline_items)


@admin.register(LibraryPolicy)
class LibraryPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "fine_per_day",
        "fine_cap",
        "hold_window_hours",
        "max_renewals",
        "reservation_grace_days",
        "reservation_warning_hours",
        "fine_block_threshold",
    )
    readonly_fields = ("audit_timeline_display",)
    fields = (
        "name",
        "fine_per_day",
        "fine_cap",
        "hold_window_hours",
        "max_renewals",
        "default_loan_period_days",
        "default_max_active_loans",
        "reservation_grace_days",
        "reservation_warning_hours",
        "fine_block_threshold",
        "audit_timeline_display",
    )
    inlines = [LoanRuleInline]

    @admin.display(description="Timeline")
    def audit_timeline_display(self, obj: LibraryPolicy):
        return _build_audit_timeline_html(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            object_id=str(obj.pk),
        )

    def save_model(self, request, obj, form, change):
        before = None
        if change and obj.pk:
            before = LibraryPolicy.objects.get(pk=obj.pk)
        super().save_model(request, obj, form, change)
        if not change:
            log_audit_event(
                target=obj,
                action_type="POLICY_CREATED_MANUAL",
                actor=request.user,
                source_screen="admin.policy.change_form",
                metadata={"policy_id": obj.id},
            )
            return
        if before:
            changed = {}
            fields = (
                "fine_per_day",
                "fine_cap",
                "hold_window_hours",
                "max_renewals",
                "default_loan_period_days",
                "default_max_active_loans",
                "reservation_grace_days",
                "reservation_warning_hours",
                "fine_block_threshold",
            )
            for field in fields:
                old_v = getattr(before, field, None)
                new_v = getattr(obj, field, None)
                if old_v != new_v:
                    changed[field] = {"old": str(old_v), "new": str(new_v)}
            if changed:
                log_audit_event(
                    target=obj,
                    action_type="POLICY_UPDATED_MANUAL",
                    actor=request.user,
                    source_screen="admin.policy.change_form",
                    changes=changed,
                )
