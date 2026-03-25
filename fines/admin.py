from django.contrib import admin
from django.http import HttpResponse
from django.urls import path

from accounts.models import MemberProfile
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


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    change_list_template = "admin/fines/fine/change_list.html"
    list_display = ("id", "member", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("member__member_no", "member__user__username", "loan__copy__barcode")

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
