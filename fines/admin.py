from django import forms
from django.contrib import admin
from django.http import HttpResponse
from django.http import JsonResponse
from django.db.models import Sum
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from decimal import Decimal

from accounts.models import MemberProfile
from audit.services import log_audit_event
from circulation.models import Loan, LoanStatus
from .models import Fine, FineStatus, Payment
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


def _paid_total_for_fine(fine: Fine, *, exclude_payment_id: int | None = None) -> Decimal:
    qs = fine.payments.all()
    if exclude_payment_id:
        qs = qs.exclude(pk=exclude_payment_id)
    return qs.aggregate(total=Sum("amount")).get("total") or Decimal("0")


def _remaining_for_fine(fine: Fine, *, exclude_payment_id: int | None = None) -> Decimal:
    paid_total = _paid_total_for_fine(fine, exclude_payment_id=exclude_payment_id)
    return max(Decimal("0"), (fine.amount or Decimal("0")) - paid_total)


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    change_list_template = "admin/fines/fine/change_list.html"
    change_form_template = "admin/fines/fine/change_form.html"

    class LoanChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            book_title = getattr(getattr(getattr(obj, "copy", None), "book", None), "title", f"Huazim #{obj.id}")
            due_at = timezone.localtime(obj.due_at).strftime("%d/%m/%Y")
            return f"{book_title} — afati {due_at}"

    class FineAdminForm(forms.ModelForm):
        class Meta:
            model = Fine
            fields = "__all__"
            labels = {
                "loan": "Huazimi",
                "member": "Anëtari",
                "amount": "Shuma e gjobës",
                "status": "Statusi",
                "reason": "Arsyeja e gjobës",
                "waived_by": "Falur nga",
                "waived_reason": "Arsyeja e faljes",
            }
            help_texts = {
                "reason": "P.sh. Vonesë, dëmtim i kopjes, humbje e kopjes.",
                "waived_reason": "Plotëso vetëm kur gjoba falet.",
            }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            overdue_qs = (
                Loan.objects.select_related("copy", "copy__book", "member")
                .filter(status=LoanStatus.ACTIVE, due_at__lt=timezone.now(), fine__isnull=True)
                .order_by("due_at")
            )
            if self.instance and self.instance.pk and self.instance.loan_id:
                overdue_qs = Loan.objects.select_related("copy", "copy__book", "member").filter(
                    pk__in=list(overdue_qs.values_list("pk", flat=True)) + [self.instance.loan_id]
                )
            self.fields["loan"] = FineAdmin.LoanChoiceField(
                queryset=overdue_qs,
                required=True,
                label="Huazimi",
            )
            self.fields["member"].required = False
            self.fields["member"].widget = forms.HiddenInput()

        def clean(self):
            cleaned = super().clean()
            loan = cleaned.get("loan")
            if loan is not None:
                cleaned["member"] = loan.member
            return cleaned

    form = FineAdminForm
    list_display = ("id", "member", "amount", "status_display", "remaining_amount_display", "last_activity_display", "created_at")
    list_filter = ("status",)
    search_fields = ("member__member_no", "member__user__username", "loan__copy__barcode")
    readonly_fields = ("created_at_display", "updated_at_display", "audit_timeline_display")
    fieldsets = (
        (
            "Detajet kryesore",
            {
                "fields": ("loan", "member", "amount", "status", "reason"),
            },
        ),
        (
            "Falja e gjobës",
            {
                "fields": ("waived_by", "waived_reason"),
            },
        ),
        (
            "Gjurmë dhe auditim",
            {
                "fields": ("created_at_display", "updated_at_display", "audit_timeline_display"),
            },
        ),
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

    @admin.display(description="Statusi")
    def status_display(self, obj: Fine):
        if obj.status == FineStatus.WAIVED:
            return format_html(
                "<span style='padding:3px 10px;border-radius:999px;font-weight:800;background:rgba(100,116,139,.12);color:#334155;'>E falur</span>"
            )
        remaining = _remaining_for_fine(obj)
        paid_total = _paid_total_for_fine(obj)
        if remaining <= 0:
            return format_html(
                "<span style='padding:3px 10px;border-radius:999px;font-weight:800;background:rgba(16,185,129,.14);color:#065f46;'>E paguar</span>"
            )
        if paid_total > 0:
            return format_html(
                "<span style='padding:3px 10px;border-radius:999px;font-weight:800;background:rgba(245,158,11,.16);color:#92400e;'>Pagesë e pjesshme</span>"
            )
        return format_html(
            "<span style='padding:3px 10px;border-radius:999px;font-weight:800;background:rgba(239,68,68,.14);color:#991b1b;'>E papaguar</span>"
        )

    @admin.display(description="Mbetja pa paguar")
    def remaining_amount_display(self, obj: Fine):
        if obj.status == FineStatus.WAIVED:
            return "—"
        return f"{_remaining_for_fine(obj):.2f} €"

    @admin.display(description="Krijuar më")
    def created_at_display(self, obj: Fine):
        if not getattr(obj, "created_at", None):
            return "—"
        return timezone.localtime(obj.created_at).strftime("%d/%m/%Y %H:%M")

    @admin.display(description="Përditësuar më")
    def updated_at_display(self, obj: Fine):
        if not getattr(obj, "updated_at", None):
            return "—"
        return timezone.localtime(obj.updated_at).strftime("%d/%m/%Y %H:%M")

    @admin.display(description="Kronologjia e auditimit")
    def audit_timeline_display(self, obj: Fine):
        return _build_audit_timeline_html(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            object_id=str(obj.pk),
        )

    def save_model(self, request, obj, form, change):
        if getattr(obj, "loan_id", None):
            obj.member = obj.loan.member
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

        def loan_preview(request, loan_id: int):
            loan = (
                Loan.objects.select_related("member")
                .filter(id=loan_id, status=LoanStatus.ACTIVE, due_at__lt=timezone.now(), fine__isnull=True)
                .first()
            )
            if not loan:
                return JsonResponse({"ok": False, "error": "Huazimi nuk u gjet ose nuk është në vonesë."}, status=404)
            member = loan.member
            return JsonResponse(
                {
                    "ok": True,
                    "member_id": member.id,
                    "member_name": (member.full_name or member.member_no or "").strip(),
                    "member_nid": member.national_id or "",
                    "member_photo_url": member.photo.url if getattr(member, "photo", None) else "",
                }
            )

        custom = [
            path("loan-preview/<int:loan_id>/", self.admin_site.admin_view(loan_preview), name="fines_fine_loan_preview"),
            path("eksporto-excel/", self.admin_site.admin_view(export_excel), name="fines_fine_export_excel"),
            path("eksporto-pdf/", self.admin_site.admin_view(export_pdf), name="fines_fine_export_pdf"),
        ]
        return custom + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["loan_preview_base"] = "/admin/fines/fine/loan-preview/"
        return super().changeform_view(request, object_id, form_url, extra_context)

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
    change_list_template = "admin/fines/payment/change_list.html"
    change_form_template = "admin/fines/payment/change_form.html"

    class FineChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            book_title = getattr(getattr(getattr(obj.loan, "copy", None), "book", None), "title", f"Gjoba #{obj.id}")
            remaining = _remaining_for_fine(obj)
            return f"{book_title} — {obj.member.member_no} — mbetje {remaining:.2f} €"

    class PaymentAdminForm(forms.ModelForm):
        class Meta:
            model = Payment
            fields = "__all__"
            labels = {
                "fine": "Gjoba",
                "amount": "Shuma e pagesës",
                "method": "Mënyra e pagesës",
                "reference": "Referenca",
                "recorded_by": "Regjistruar nga",
            }
            help_texts = {
                "amount": "Vendos shumën e paguar. Mund të jetë e plotë ose e pjesshme.",
                "reference": "Opsionale: numër fature, përshkrim pagese, etj.",
            }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            outstanding_ids = []
            for fine in Fine.objects.select_related("member", "loan", "loan__copy", "loan__copy__book").exclude(
                status=FineStatus.WAIVED
            ):
                if _remaining_for_fine(fine) > 0:
                    outstanding_ids.append(fine.id)
            if self.instance and self.instance.pk and self.instance.fine_id:
                outstanding_ids.append(self.instance.fine_id)
            qs = Fine.objects.select_related("member", "loan", "loan__copy", "loan__copy__book").filter(pk__in=outstanding_ids)
            self.fields["fine"] = PaymentAdmin.FineChoiceField(queryset=qs, required=True, label="Gjoba")
            self.fields["recorded_by"].required = False
            self.fields["recorded_by"].widget = forms.HiddenInput()

            if not self.instance.pk and self.initial.get("fine"):
                fine = self.fields["fine"].queryset.filter(pk=self.initial.get("fine")).first()
                if fine:
                    self.initial.setdefault("amount", _remaining_for_fine(fine))

        def clean(self):
            cleaned = super().clean()
            fine = cleaned.get("fine")
            amount = cleaned.get("amount")
            if not fine or amount is None:
                return cleaned
            remaining = _remaining_for_fine(
                fine,
                exclude_payment_id=self.instance.pk if self.instance and self.instance.pk else None,
            )
            if amount <= 0:
                self.add_error("amount", "Shuma duhet të jetë më e madhe se 0.")
            if amount > remaining:
                self.add_error("amount", f"Shuma kalon mbetjen e papaguar ({remaining:.2f} €).")
            return cleaned

    form = PaymentAdminForm
    @admin.display(description="Nr. huazimi")
    def loan_number_display(self, obj: Payment):
        return f"Huazim #{obj.fine.loan_id}"

    @admin.display(description="Anëtari")
    def member_display(self, obj: Payment):
        member = obj.fine.member
        return f"{member.full_name or member.member_no} ({member.member_no})"

    @admin.display(description="Shuma e pagesës")
    def amount_display(self, obj: Payment):
        return f"{obj.amount:.2f} €"

    @admin.display(description="Mënyra e pagesës")
    def method_display(self, obj: Payment):
        return obj.get_method_display()

    @admin.display(description="Regjistruar nga")
    def recorded_by_display(self, obj: Payment):
        return obj.recorded_by.get_username() if obj.recorded_by_id else "—"

    @admin.display(description="Data")
    def created_at_display(self, obj: Payment):
        return timezone.localtime(obj.created_at).strftime("%d/%m/%Y %H:%M")

    class MethodFilter(admin.SimpleListFilter):
        title = "Mënyra"
        parameter_name = "method"

        def lookups(self, request, model_admin):
            return (
                ("CASH", "Para në dorë"),
                ("CARD", "Kartë"),
                ("OTHER", "Tjetër"),
            )

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(method=self.value())
            return queryset

    class FineStatusFilter(admin.SimpleListFilter):
        title = "Statusi i gjobës"
        parameter_name = "fine_status"

        def lookups(self, request, model_admin):
            return (
                ("UNPAID", "E papaguar"),
                ("PAID", "E paguar"),
                ("WAIVED", "E falur"),
            )

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(fine__status=self.value())
            return queryset

    list_display = (
        "id",
        "loan_number_display",
        "member_display",
        "amount_display",
        "method_display",
        "payment_status_display",
        "remaining_after_display",
        "recorded_by_display",
        "created_at_display",
    )
    list_filter = (MethodFilter, FineStatusFilter)
    search_fields = ("fine__member__member_no", "fine__member__full_name", "fine__loan__copy__barcode", "reference")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("fine", "fine__member", "fine__loan", "recorded_by")

    @admin.display(description="Statusi pas pagesës")
    def payment_status_display(self, obj: Payment):
        remaining = _remaining_for_fine(obj.fine)
        if obj.fine.status == FineStatus.WAIVED:
            return "E falur"
        return "E paguar" if remaining <= 0 else "Pagesë e pjesshme"

    @admin.display(description="Mbetja pas pagesës")
    def remaining_after_display(self, obj: Payment):
        return f"{_remaining_for_fine(obj.fine):.2f} €"

    def _sync_fine_status(self, fine: Fine):
        if fine.status == FineStatus.WAIVED:
            return
        remaining = _remaining_for_fine(fine)
        target_status = FineStatus.PAID if remaining <= 0 else FineStatus.UNPAID
        if fine.status != target_status:
            fine.status = target_status
            fine.save(update_fields=["status", "updated_at"])

    def save_model(self, request, obj, form, change):
        if not getattr(obj, "recorded_by_id", None):
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)
        self._sync_fine_status(obj.fine)

    def delete_model(self, request, obj):
        fine = obj.fine
        super().delete_model(request, obj)
        self._sync_fine_status(fine)

    def delete_queryset(self, request, queryset):
        fine_ids = list(queryset.values_list("fine_id", flat=True).distinct())
        super().delete_queryset(request, queryset)
        for fine in Fine.objects.filter(pk__in=fine_ids):
            self._sync_fine_status(fine)

    def get_urls(self):
        urls = super().get_urls()

        def fine_preview(request, fine_id: int):
            fine = Fine.objects.select_related("member").filter(pk=fine_id).first()
            if not fine:
                return JsonResponse({"ok": False, "error": "Gjoba nuk u gjet."}, status=404)
            member = fine.member
            paid_total = _paid_total_for_fine(fine)
            remaining = _remaining_for_fine(fine)
            return JsonResponse(
                {
                    "ok": True,
                    "member_name": (member.full_name or member.member_no or "").strip(),
                    "member_no": member.member_no or "",
                    "member_nid": member.national_id or "",
                    "member_phone": member.phone or "",
                    "member_address": member.address or "",
                    "member_photo_url": member.photo.url if getattr(member, "photo", None) else "",
                    "fine_amount": f"{(fine.amount or Decimal('0')):.2f}",
                    "paid_total": f"{paid_total:.2f}",
                    "remaining": f"{remaining:.2f}",
                }
            )

        custom = [
            path("fine-preview/<int:fine_id>/", self.admin_site.admin_view(fine_preview), name="fines_payment_fine_preview"),
        ]
        return custom + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["payment_fine_preview_base"] = "/admin/fines/payment/fine-preview/"
        return super().changeform_view(request, object_id, form_url, extra_context)
