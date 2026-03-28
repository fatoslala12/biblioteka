from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from accounts.models import MemberProfile
from audit.services import log_audit_event
from .models import Fine, Payment
from smart_library.reports import export_fines_excel, export_fines_pdf


def _export_members_choices():
    out = []
    for mp in MemberProfile.objects.select_related("user").order_by("full_name", "member_no")[:400]:
        label = (mp.full_name or "").strip() or (mp.user.get_full_name() if mp.user_id else "") or mp.member_no or f"Anëtar #{mp.id}"
        if (mp.member_no or "").strip():
            label = f"{mp.member_no} — {label}"
        out.append((mp.id, label))
    return out


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


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    change_list_template = "admin/fines/fine/change_list.html"
    list_display = ("id", "member", "amount", "status", "last_activity_display", "created_at")
    list_filter = ("status",)
    search_fields = ("member__member_no", "member__user__username", "loan__copy__barcode")
    readonly_fields = ("created_at", "updated_at", "audit_timeline_display")
    fields = (
        "loan",
        "member",
        "amount",
        "status",
        "reason",
        "waived_by",
        "waived_reason",
        "created_at",
        "updated_at",
        "audit_timeline_display",
    )

    @admin.display(description="Aktiviteti i fundit")
    def last_activity_display(self, obj: Fine):
        from audit.models import AuditEntry

        entry = (
            AuditEntry.objects.filter(
                app_label=obj._meta.app_label,
                model_name=obj._meta.model_name,
                object_id=str(obj.pk),
            )
            .order_by("-created_at")
            .first()
        )
        if not entry:
            return "—"
        return entry.action_type_sq

    @admin.display(description="Timeline")
    def audit_timeline_display(self, obj: Fine):
        return _build_audit_timeline_html(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            object_id=str(obj.pk),
        )

    def save_model(self, request, obj, form, change):
        before = None
        if change and obj.pk:
            before = Fine.objects.get(pk=obj.pk)
        super().save_model(request, obj, form, change)
        if not change:
            log_audit_event(
                target=obj,
                action_type="FINE_CREATED_MANUAL",
                actor=request.user,
                source_screen="admin.fine.change_form",
                metadata={"fine_id": obj.id},
            )
            return
        if before:
            changed = {}
            for field in ("amount", "status", "reason", "waived_reason", "waived_by_id"):
                old_v = getattr(before, field, None)
                new_v = getattr(obj, field, None)
                if old_v != new_v:
                    changed[field] = {"old": old_v, "new": new_v}
            if changed:
                log_audit_event(
                    target=obj,
                    action_type="FINE_UPDATED_MANUAL",
                    actor=request.user,
                    source_screen="admin.fine.change_form",
                    changes=changed,
                )

    def _apply_export_filters_fine(self, request, qs):
        date_from = (request.GET.get("date_from") or "").strip()
        date_to = (request.GET.get("date_to") or "").strip()
        member_id = (request.GET.get("member_id") or "").strip()
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs

    def get_urls(self):
        urls = super().get_urls()

        def export_excel(request):
            qs = self.get_queryset(request)
            qs = self._apply_export_filters_fine(request, qs)
            wb = export_fines_excel(qs)
            resp = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="raport_gjoba.xlsx"'},
            )
            wb.save(resp)
            return resp

        def export_pdf(request):
            qs = self.get_queryset(request)
            qs = self._apply_export_filters_fine(request, qs)
            pdf_bytes = export_fines_pdf(qs)
            return HttpResponse(
                pdf_bytes,
                content_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="raport_gjoba.pdf"'},
            )

        custom = [
            path("eksporto-excel/", self.admin_site.admin_view(export_excel), name="fines_fine_export_excel"),
            path("eksporto-pdf/", self.admin_site.admin_view(export_pdf), name="fines_fine_export_pdf"),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        base = "?" + request.GET.urlencode() if request.GET else ""
        extra_context["export_excel_url"] = "/admin/fines/fine/eksporto-excel/" + base
        extra_context["export_pdf_url"] = "/admin/fines/fine/eksporto-pdf/" + base
        extra_context["export_excel_base"] = "/admin/fines/fine/eksporto-excel/"
        extra_context["export_pdf_base"] = "/admin/fines/fine/eksporto-pdf/"
        extra_context["export_modal_report_label"] = "Gjoba"
        extra_context["export_modal_has_book"] = False
        extra_context["export_modal_has_author"] = False
        extra_context["export_modal_has_member"] = True
        extra_context["export_modal_has_dates"] = True
        extra_context["export_members"] = _export_members_choices()
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "fine", "amount", "method", "recorded_by", "created_at")
    list_filter = ("method",)
