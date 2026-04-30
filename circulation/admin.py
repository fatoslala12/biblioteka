import json
from datetime import datetime, time, timedelta

from django import forms
from django.contrib import admin, messages
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.http import urlencode

from audit.models import AuditEntry, AuditSeverity
from audit.services import log_audit_event
from .exceptions import PolicyViolation
from .models import (
    Hold,
    Loan,
    LoanStatus,
    Reservation,
    ReservationStatus,
    ReservationRequest,
    ReservationRequestStatus,
)
from accounts.models import MemberProfile
from catalog.models import Author, Book, Copy, CopyStatus
from policies.models import LibraryPolicy
from .services import (
    auto_expire_overdue_reservations,
    approve_reservation_request,
    borrow_from_reservation,
    create_reservation_request,
    get_book_availability_for_range,
    quick_checkout_by_national_id,
    return_copy,
    reject_reservation_request,
    suggest_best_copy_for_quick_checkout,
)

# Ensure legacy Hold does not appear as a second "Rezervime"
try:
    admin.site.unregister(Hold)
except admin.sites.NotRegistered:
    pass


def _export_members_choices():
    """Lista (id, etiketa) për dropdown anëtarësh në modal eksporti."""
    out = []
    for mp in MemberProfile.objects.select_related("user").order_by("full_name", "member_no")[:400]:
        label = (mp.full_name or "").strip() or (mp.user.get_full_name() if mp.user_id else "") or mp.member_no or f"Anëtar #{mp.id}"
        if (mp.member_no or "").strip():
            label = f"{mp.member_no} — {label}"
        out.append((mp.id, label))
    return out


def _build_audit_timeline_html(*, app_label: str, model_name: str, object_id: str) -> str:
    entries = (
        AuditEntry.objects.select_related("actor")
        .filter(app_label=app_label, model_name=model_name, object_id=str(object_id))
        .order_by("-created_at")[:15]
    )
    if not entries:
        return "—"

    rows = []
    for e in entries:
        actor = e.actor.get_username() if e.actor_id else "Sistem"
        when = timezone.localtime(e.created_at).strftime("%d/%m/%Y %H:%M")
        changed_keys = ", ".join((e.changes or {}).keys()) if isinstance(e.changes, dict) else ""
        reason = (e.reason or "—").strip()
        rows.append(
            format_html(
                (
                    "<li style='padding:10px 12px;border:1px solid rgba(148,163,184,.25);"
                    "border-radius:12px;background:#fff;'>"
                    "<div style='display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;'>"
                    "<b>{}</b><small style='opacity:.78'>{}</small></div>"
                    "<div style='margin-top:4px;font-size:12px;opacity:.86'>Aktor: <b>{}</b></div>"
                    "<div style='margin-top:3px;font-size:12px;opacity:.86'>Arsye: {}</div>"
                    "<div style='margin-top:3px;font-size:12px;opacity:.86'>Ndryshime: {}</div>"
                    "</li>"
                ),
                e.action_type_sq,
                when,
                actor,
                reason,
                changed_keys or "—",
            )
        )

    timeline_items = format_html_join("", "{}", ((row,) for row in rows))
    return format_html(
        "<ul style='list-style:none;padding:0;margin:0;display:grid;gap:8px;'>{}</ul>",
        timeline_items,
    )


def _get_reservation_timing_policy() -> LibraryPolicy:
    policy, _ = LibraryPolicy.objects.get_or_create(name="default")
    return policy


class LoanAdminForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = "__all__"
        labels = {
            "member": "Anëtari",
            "copy": "Kopja",
            "status": "Statusi",
            "loaned_at": "Huazuar më",
            "due_at": "Afati i kthimit",
            "returned_at": "Kthyer më",
            "note": "Shënim",
            "renew_count": "Nr. zgjatjeve",
        }


class HoldAdminForm(forms.ModelForm):
    class Meta:
        model = Hold
        fields = "__all__"
        labels = {
            "member": "Anëtari",
            "book": "Libri",
            "position": "Pozicioni në radhë",
            "status": "Statusi",
            "created_at": "Krijuar më",
            "ready_at": "Gati për marrje më",
            "expires_at": "Skadon më",
        }


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    change_list_template = "admin/circulation/loan/change_list.html"
    change_form_template = "admin/circulation/loan/change_form.html"
    list_display = (
        "loan_id_display",
        "member_display",
        "book_link",
        "source_staff_display",
        "status_display",
        "loaned_at_display",
        "due_at_display",
        "returned_at_display",
        "time_status_badge",
        "return_early_btn",
    )
    list_display_links = ("book_link",)
    list_filter = ()
    search_fields = ("id", "member__member_no", "copy__barcode", "copy__book__title")
    autocomplete_fields = ("member", "copy")
    list_select_related = (
        "member",
        "copy",
        "copy__book",
        "loaned_by",
        "returned_by",
        "from_reservation",
        "from_reservation__created_by",
        "from_reservation__borrowed_by",
        "from_reservation__source_request",
        "from_reservation__source_request__created_by",
        "from_reservation__source_request__decided_by",
    )
    form = LoanAdminForm

    actions = None

    def lookup_allowed(self, lookup, value, request):
        if lookup in {
            "copy__book__id__exact",
            "status__exact",
            "status__in",
            "from_reservation__isnull",
        }:
            return True
        return super().lookup_allowed(lookup, value, request)

    fieldsets = (
        ("Huazimi", {"fields": ("member", "copy", "status")}),
        ("Afatet", {"fields": ("loaned_at", "due_at", "returned_at")}),
        ("Auditim", {"fields": ("loaned_by", "returned_by")}),
        ("Zgjatjet", {"fields": ("renew_count",)}),
        ("Flow i huazimit", {"fields": ("loan_flow_display",)}),
        ("Timeline e auditimit", {"fields": ("audit_timeline_display",)}),
    )
    readonly_fields = ("loaned_at", "loan_flow_display", "loaned_by", "returned_by", "audit_timeline_display")

    def get_queryset(self, request):
        qs = super().get_queryset(request).annotate(
            source_order=Case(
                When(from_reservation__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            actor_username=Coalesce(
                "from_reservation__borrowed_by__username",
                "loaned_by__username",
                Value(""),
            ),
        )
        status_exact = (request.GET.get("status__exact") or "").upper()
        status_in = (request.GET.get("status__in") or "").upper()
        source_isnull = (request.GET.get("from_reservation__isnull") or "").strip()
        book_id_exact = (request.GET.get("copy__book__id__exact") or "").strip()
        if status_exact == "RETURNED":
            status_qs = qs.filter(status="RETURNED")
        elif status_exact == "ACTIVE":
            status_qs = qs.filter(status="ACTIVE")
        elif status_in:
            status_qs = qs
        else:
            status_qs = qs

        if book_id_exact.isdigit():
            status_qs = status_qs.filter(copy__book_id=int(book_id_exact))

        if source_isnull == "False":
            return status_qs.filter(from_reservation__isnull=False)
        if source_isnull == "True":
            return status_qs.filter(from_reservation__isnull=True)
        return status_qs

    @admin.display(description="Timeline")
    def audit_timeline_display(self, obj: Loan):
        return _build_audit_timeline_html(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            object_id=str(obj.pk),
        )

    @admin.display(description="ID", ordering="id")
    def loan_id_display(self, obj: Loan):
        return format_html(
            '<a href="/admin/circulation/loan/{}/change/" style="font-weight:800;">#{}</a>',
            obj.id,
            obj.id,
        )

    @admin.display(description="Libri", ordering="copy__book__title")
    def book_link(self, obj: Loan):
        book = getattr(obj.copy, "book", None)
        if not book:
            return "—"
        url = f"/admin/catalog/book/{book.id}/change/"
        return format_html('<a href="{}" style="font-weight:800;">{}</a>', url, book.title)

    @admin.display(description="Anëtari")
    def member_display(self, obj: Loan):
        m = obj.member
        name = (m.full_name or "").strip()
        nid = (m.national_id or "").strip()
        label = name or m.member_no
        url = f"/panel/members/{m.id}/"
        extra = f" • {nid}" if nid else ""
        if getattr(m, "photo", None):
            avatar = format_html(
                '<img src="{}" style="width:30px;height:30px;border-radius:999px;object-fit:cover;margin-right:8px;" />',
                m.photo.url,
            )
        else:
            initial = (label[:1] or "A").upper()
            avatar = format_html(
                '<span style="width:30px;height:30px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;'
                'margin-right:8px;background:rgba(49,145,137,.14);color:#1f5f5a;font-weight:800;font-size:12px;">{}</span>',
                initial,
            )
        return format_html(
            '<a href="{}" style="display:inline-flex;align-items:center;"><span>{}</span><span><b>{}</b><small style="display:block;opacity:.78;">{}</small></span></a>',
            url,
            avatar,
            label,
            extra[3:] if extra else m.member_no,
        )

    @admin.display(description="Kopja", ordering="copy__barcode")
    def copy_display(self, obj: Loan):
        return getattr(obj.copy, "barcode", None) or str(obj.copy)

    @admin.display(description="Statusi", ordering="status")
    def status_display(self, obj: Loan):
        try:
            return obj.get_status_display()
        except Exception:
            return obj.status

    @admin.display(description="Mënyra", ordering="actor_username")
    def source_staff_display(self, obj: Loan):
        reservation = getattr(obj, "from_reservation", None)
        if reservation:
            source_badge = '<span style="display:inline-flex;align-items:center;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800;background:rgba(14,165,233,.14);color:#0c4a6e;">Nga rezervimi</span>'
            staff_user = getattr(reservation, "borrowed_by", None) or getattr(obj, "loaned_by", None)
        else:
            source_badge = '<span style="display:inline-flex;align-items:center;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800;background:rgba(49,145,137,.14);color:#134e4a;">Direkt</span>'
            staff_user = getattr(obj, "loaned_by", None)

        if staff_user:
            staff_name = (staff_user.get_full_name() or "").strip() or staff_user.username
            staff_username = "@" + (staff_user.username or "")
        else:
            staff_name = ""
            staff_username = ""
        extra = ""
        if staff_name:
            extra = format_html(
                '<small style="color:#334155;font-weight:700;">{}</small><small style="color:#64748b;font-weight:700;">{}</small>',
                staff_name,
                staff_username,
            )
        return format_html('<div style="display:flex;flex-direction:column;gap:4px;line-height:1.15;">{}{}</div>', format_html(source_badge), extra)

    @admin.display(description="Huazuar më", ordering="loaned_at")
    def loaned_at_display(self, obj: Loan):
        return timezone.localtime(obj.loaned_at).strftime("%d/%m/%Y")

    @admin.display(description="Afati i kthimit", ordering="due_at")
    def due_at_display(self, obj: Loan):
        return timezone.localtime(obj.due_at).strftime("%d/%m/%Y")

    @admin.display(description="Kthyer më", ordering="returned_at")
    def returned_at_display(self, obj: Loan):
        if not obj.returned_at:
            return format_html('<a href="/admin/circulation/loan/{}/change/" title="Ndrysho huazimin">—</a>', obj.id)
        return timezone.localtime(obj.returned_at).strftime("%d/%m/%Y")

    @admin.display(description="Flow i huazimit")
    def loan_flow_display(self, obj: Loan):
        def dt(v):
            if not v:
                return "—"
            return timezone.localtime(v).strftime("%d/%m/%Y %H:%M")
        def actor(u):
            if not u:
                return "—"
            name = (u.get_full_name() or "").strip()
            return name or u.username

        reservation = getattr(obj, "from_reservation", None)
        request_obj = getattr(reservation, "source_request", None) if reservation else None

        events = []
        def add_event(*, when, title, meta, tag, dot, incident=False):
            events.append(
                {
                    "when": when,
                    "title": title,
                    "meta": meta,
                    "tag": tag,
                    "dot": dot,
                    "incident": incident,
                }
            )

        if request_obj:
            add_event(
                when=request_obj.created_at,
                title=f"Kërkesë rezervimi #{request_obj.id}",
                meta=f"Krijuar më {dt(request_obj.created_at)} • Regjistruar nga {actor(getattr(request_obj, 'created_by', None))}",
                tag="REQUEST_CREATED",
                dot="info",
            )
            if request_obj.decided_at or request_obj.decided_by_id:
                is_rejected = request_obj.status in (ReservationRequestStatus.REJECTED, ReservationRequestStatus.CANCELLED)
                add_event(
                    when=request_obj.decided_at or request_obj.created_at,
                    title=f"Vendim i kërkesës: {request_obj.get_status_display()}",
                    meta=f"Nga {actor(request_obj.decided_by if request_obj.decided_by_id else None)} • {dt(request_obj.decided_at)}",
                    tag="REQUEST_DECIDED",
                    dot="warning" if is_rejected else "primary",
                    incident=is_rejected,
                )

        if reservation:
            add_event(
                when=reservation.created_at,
                title=f"Rezervimi #{reservation.id} • {reservation.get_status_display()}",
                meta=(
                    f"Intervali: {reservation.pickup_date.strftime('%d/%m/%Y')} - {reservation.return_date.strftime('%d/%m/%Y')} "
                    f"• Krijuar nga {actor(getattr(reservation, 'created_by', None))}"
                ),
                tag="RESERVATION_CREATED",
                dot="cyan",
            )
        else:
            add_event(
                when=obj.loaned_at,
                title="Burimi: Direkt",
                meta="Ky huazim është krijuar direkt pa rezervim.",
                tag="SOURCE_DIRECT",
                dot="muted",
            )

        add_event(
            when=obj.loaned_at,
            title=f"Huazimi #{obj.id} • {obj.get_status_display()}",
            meta=f"Huazuar më {dt(obj.loaned_at)} • Afati {dt(obj.due_at)} • Nga {actor(getattr(obj, 'loaned_by', None))}",
            tag="LOAN_CREATED",
            dot="success",
        )
        if obj.returned_at:
            late = obj.returned_at > obj.due_at
            add_event(
                when=obj.returned_at,
                title="Dorëzimi i huazimit",
                meta=f"Kthyer më {dt(obj.returned_at)} • Pranuar nga {actor(getattr(obj, 'returned_by', None))}",
                tag="LOAN_RETURNED",
                dot="warning" if late else "success",
                incident=late,
            )
        else:
            overdue = obj.status == LoanStatus.ACTIVE and obj.due_at < timezone.now()
            add_event(
                when=timezone.now(),
                title="Dorëzimi",
                meta="Ende aktiv." if not overdue else "Huazimi është aktiv por me vonesë.",
                tag="LOAN_ACTIVE",
                dot="warning" if overdue else "muted",
                incident=overdue,
            )

        for entry in obj.audit_entries.select_related("actor").all().order_by("created_at"):
            changed_fields = ", ".join(list((entry.changes or {}).keys())[:3])
            changed_hint = f" • Fusha: {changed_fields}" if changed_fields else ""
            add_event(
                when=entry.created_at,
                title=f"{entry.action_type}",
                meta=(
                    f"{dt(entry.created_at)} • Nga {actor(entry.actor)} • Burimi: {entry.source_screen or '—'}"
                    f"{changed_hint}{' • Arsye: ' + entry.reason if entry.reason else ''}"
                ),
                tag=entry.severity,
                dot="warning" if entry.severity == AuditSeverity.INCIDENT else "primary",
                incident=entry.severity == AuditSeverity.INCIDENT,
            )

        events.sort(key=lambda x: x["when"] or timezone.now())

        cards = []
        for ev in events:
            cards.append(
                format_html(
                    '<li class="sl-flow-item" data-incident="{}"><span class="sl-flow-dot sl-flow-dot-{}"></span>'
                    '<div><div class="sl-flow-title"><span class="sl-flow-tag">{}</span> {}</div>'
                    '<div class="sl-flow-meta">{}</div></div></li>',
                    "1" if ev["incident"] else "0",
                    ev["dot"],
                    ev["tag"],
                    ev["title"],
                    ev["meta"],
                )
            )

        return format_html(
            '<div class="sl-loan-flow">'
            '<div class="sl-flow-toolbar">'
            '<button type="button" class="btn btn-xs btn-outline-secondary js-flow-filter" data-mode="all">Të gjitha ngjarjet</button> '
            '<button type="button" class="btn btn-xs btn-outline-warning js-flow-filter" data-mode="incident">Vetëm incidentet</button>'
            "</div>"
            '<ol class="sl-flow-list">{}</ol>'
            "<script>(function(){var root=document.currentScript&&document.currentScript.parentElement;if(!root)return;"
            "var btns=root.querySelectorAll('.js-flow-filter');var items=root.querySelectorAll('.sl-flow-item');"
            "btns.forEach(function(b){b.addEventListener('click',function(){var mode=b.getAttribute('data-mode');"
            "items.forEach(function(it){var inc=it.getAttribute('data-incident')==='1';it.style.display=(mode==='incident'&&!inc)?'none':'';});"
            "btns.forEach(function(x){x.classList.remove('active');});b.classList.add('active');});});})();</script>"
            "</div>",
            format_html("".join(str(item) for item in cards)),
        )

    @admin.display(description="Koha")
    def time_status_badge(self, obj: Loan):
        is_late = obj.status == "ACTIVE" and obj.due_at < timezone.now()
        returned_early = (
            obj.status == "RETURNED"
            and obj.returned_at is not None
            and obj.returned_at < obj.due_at
        )
        if is_late:
            return format_html(
                '<span title="Me vonesë" style="display:inline-flex;width:16px;height:16px;border-radius:999px;background:#e74c3c;"></span>'
            )
        if returned_early:
            return format_html(
                '<span title="Dorëzuar para afatit" style="display:inline-flex;width:16px;height:16px;border-radius:999px;background:#F39C12;"></span>'
            )
        return format_html(
            '<span title="Në rregull" style="display:inline-flex;width:16px;height:16px;border-radius:999px;background:#319189;"></span>'
        )

    @admin.display(description="Dorëzo")
    def return_early_btn(self, obj: Loan):
        if obj.status != "ACTIVE":
            return "—"
        url = f"/admin/circulation/loan/{obj.id}/kthe-heret/"
        return format_html(
            '<a class="btn btn-xs btn-primary" href="{}">Dorëzo</a>',
            url,
        )

    def _apply_export_filters_loan(self, request, qs):
        """Aplikon filtra nga GET (date_from, date_to, book_id, author_id, member_id)."""
        date_from = (request.GET.get("date_from") or "").strip()
        date_to = (request.GET.get("date_to") or "").strip()
        book_id = (request.GET.get("book_id") or "").strip()
        author_id = (request.GET.get("author_id") or "").strip()
        member_id = (request.GET.get("member_id") or "").strip()
        if date_from:
            qs = qs.filter(loaned_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(loaned_at__date__lte=date_to)
        if book_id:
            qs = qs.filter(copy__book_id=book_id)
        if author_id:
            qs = qs.filter(copy__book__authors__id=author_id).distinct()
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs

    def get_urls(self):
        urls = super().get_urls()
        from smart_library.reports import export_loans_excel, export_loans_pdf

        def export_excel(request):
            qs = self.get_queryset(request)
            qs = self._apply_export_filters_loan(request, qs)
            wb = export_loans_excel(qs)
            resp = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="raport_huazime.xlsx"'},
            )
            wb.save(resp)
            return resp

        def export_pdf(request):
            qs = self.get_queryset(request)
            qs = self._apply_export_filters_loan(request, qs)
            pdf_bytes = export_loans_pdf(qs)
            return HttpResponse(pdf_bytes, content_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="raport_huazime.pdf"'})

        custom = [
            path("shto-huazim/", self.admin_site.admin_view(self.quick_loan_view), name="circulation_loan_quick"),
            path("shto-huazim/api/", self.admin_site.admin_view(self.quick_loan_api), name="circulation_loan_quick_api"),
            path("shto-huazim/krijo/", self.admin_site.admin_view(self.quick_loan_create_api), name="circulation_loan_quick_create_api"),
            path("<int:loan_id>/kthe-heret/", self.admin_site.admin_view(self.return_early_view), name="circulation_loan_return_early"),
            path("eksporto-excel/", self.admin_site.admin_view(export_excel), name="circulation_loan_export_excel"),
            path("eksporto-pdf/", self.admin_site.admin_view(export_pdf), name="circulation_loan_export_pdf"),
        ]
        return custom + urls

    def return_early_view(self, request: HttpRequest, loan_id: int):
        loan = Loan.objects.select_related("copy").filter(id=loan_id).first()
        if not loan:
            messages.error(request, "Huazimi nuk u gjet.")
            return self._redirect_to_changelist()
        if loan.status != "ACTIVE":
            messages.warning(request, "Ky huazim nuk është aktiv.")
            return self._redirect_to_changelist()
        try:
            return_copy(
                copy_barcode=loan.copy.barcode,
                returned_by=request.user,
                source_screen="admin.loan.list.return_early",
                reason="Dorëzim i shpejtë nga lista e huazimeve.",
            )
            messages.success(request, "Huazimi u mbyll (u kthye).")
        except PolicyViolation as e:
            messages.error(request, str(e))
        return self._redirect_to_changelist()

    def _redirect_to_changelist(self):
        from django.shortcuts import redirect

        return redirect("/admin/circulation/loan/")

    def save_model(self, request, obj, form, change):
        before = None
        if not change and not obj.loaned_by_id:
            obj.loaned_by = request.user
        if change and obj.pk:
            prev = Loan.objects.filter(pk=obj.pk).only("status", "returned_by", "returned_at", "due_at", "note", "copy_id", "member_id").first()
            before = prev
            if prev and prev.status != LoanStatus.RETURNED and obj.status == LoanStatus.RETURNED:
                if not obj.returned_at:
                    obj.returned_at = timezone.now()
                if not obj.returned_by_id:
                    obj.returned_by = request.user
        super().save_model(request, obj, form, change)
        if not change:
            log_audit_event(
                target=obj,
                loan=obj,
                action_type="LOAN_CREATED_MANUAL",
                actor=request.user,
                source_screen="admin.loan.change_form",
                metadata={"loan_id": obj.id},
            )
            return

        if before:
            changed = {}
            tracked = ("status", "due_at", "returned_at", "returned_by_id", "copy_id", "member_id", "note")
            for field in tracked:
                old_v = getattr(before, field, None)
                new_v = getattr(obj, field, None)
                if old_v != new_v:
                    changed[field] = {
                        "old": old_v.isoformat() if hasattr(old_v, "isoformat") else old_v,
                        "new": new_v.isoformat() if hasattr(new_v, "isoformat") else new_v,
                    }
            if changed:
                severity = AuditSeverity.INCIDENT if "status" in changed and changed["status"]["new"] == LoanStatus.RETURNED else AuditSeverity.INFO
                log_audit_event(
                    target=obj,
                    loan=obj,
                    action_type="LOAN_UPDATED_MANUAL",
                    actor=request.user,
                    source_screen="admin.loan.change_form",
                    reason=(obj.note or "")[:255],
                    changes=changed,
                    severity=severity,
                )

    class QuickLoanForm(forms.Form):
        class BookChoiceField(forms.ModelChoiceField):
            def label_from_instance(self, obj):
                title = obj.title or "Pa titull"
                isbn = (obj.isbn or "").strip()
                if isbn:
                    return f"{title} (ISBN: {isbn})"
                return title

        national_id = forms.CharField(
            label="Nr. ID (numri personal)",
            max_length=32,
            widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "p.sh. J50408078S"}),
        )
        book = BookChoiceField(
            label="Libri",
            queryset=Book.objects.none(),
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        pickup_date = forms.DateField(
            label="Do ta marrë më",
            widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        )
        return_date = forms.DateField(
            label="Do ta dorëzojë më",
            widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        )
        note = forms.CharField(
            label="Shënim (opsionale)",
            required=False,
            max_length=255,
            widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "p.sh. me kartë anëtari / shënim sporteli"}),
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["book"].queryset = (
                Book.objects.filter(is_deleted=False)
                .annotate(
                    available_copies=Count(
                        "copies",
                        filter=Q(copies__is_deleted=False, copies__status=CopyStatus.AVAILABLE),
                    )
                )
                .filter(available_copies__gt=0)
                .order_by("title")
            )

    def quick_loan_view(self, request: HttpRequest):
        initial = {"pickup_date": timezone.now().date(), "return_date": (timezone.now() + timezone.timedelta(days=14)).date()}
        form = self.QuickLoanForm(request.POST or None, initial=initial)
        member_info = None
        availability = None

        if request.method == "POST" and form.is_valid():
            nid = form.cleaned_data["national_id"]
            book = form.cleaned_data["book"]
            pickup_date = form.cleaned_data["pickup_date"]
            return_date = form.cleaned_data["return_date"]
            note = form.cleaned_data.get("note") or ""

            member = MemberProfile.objects.filter(national_id=nid).select_related("user").first()
            if member:
                member_info = {
                    "member_no": member.member_no,
                    "full_name": member.full_name or (member.user.get_full_name() if member.user_id else ""),
                    "phone": member.phone,
                }

            try:
                availability = get_book_availability_for_range(book.id, pickup_date, return_date)
            except PolicyViolation as e:
                messages.error(request, str(e))

            action = (request.POST.get("action") or "").strip()
            if action == "confirm":
                try:
                    loan = quick_checkout_by_national_id(
                        national_id=nid,
                        book_id=book.id,
                        pickup_date=pickup_date,
                        return_date=return_date,
                        note=note,
                        loaned_by=request.user,
                        source_screen="admin.loan.quick_form",
                        reason="Krijuar nga forma e shpejtë e huazimit.",
                    )
                    messages.success(request, f"Huazimi u krye. ID: {loan.id}")
                    return self.response_post_save_add(request, loan)
                except PolicyViolation as e:
                    messages.error(request, str(e))

        context = dict(
            self.admin_site.each_context(request),
            title="Shto Huazim",
            form=form,
            member_info=member_info,
            availability=availability,
        )
        return TemplateResponse(request, "admin/circulation/quick_loan.html", context)

    def changelist_view(self, request, extra_context=None):
        initial = {
            "pickup_date": timezone.now().date(),
            "return_date": (timezone.now() + timezone.timedelta(days=14)).date(),
        }
        status_exact = (request.GET.get("status__exact") or "").upper()
        status_in = (request.GET.get("status__in") or "").upper()
        if status_exact in ("ACTIVE", "RETURNED"):
            current_scope = status_exact
        elif status_in:
            current_scope = "ALL"
        else:
            current_scope = "ALL"
        source_isnull = (request.GET.get("from_reservation__isnull") or "").strip()
        if source_isnull == "False":
            current_source = "RESERVATION"
        elif source_isnull == "True":
            current_source = "DIRECT"
        else:
            current_source = "ALL"
        keep_keys = ("q", "copy__book__id__exact", "o", "ot")
        base_params = {}
        for k in keep_keys:
            vals = request.GET.getlist(k)
            if vals:
                base_params[k] = vals
        def apply_status(qp, scope):
            qp.pop("status__exact", None)
            qp.pop("status__in", None)
            if scope == "ACTIVE":
                qp["status__exact"] = ["ACTIVE"]
            elif scope == "RETURNED":
                qp["status__exact"] = ["RETURNED"]
            else:
                qp["status__in"] = ["ACTIVE,RETURNED"]
        def apply_source(qp, source):
            qp.pop("from_reservation__isnull", None)
            if source == "RESERVATION":
                qp["from_reservation__isnull"] = ["False"]
            elif source == "DIRECT":
                qp["from_reservation__isnull"] = ["True"]
        status_urls = {}
        for s in ("ACTIVE", "ALL", "RETURNED"):
            qp = {k: list(v) for k, v in base_params.items()}
            apply_status(qp, s)
            apply_source(qp, current_source)
            status_urls[s.lower()] = "?" + urlencode(qp, doseq=True)
        source_urls = {}
        for s in ("ALL", "RESERVATION", "DIRECT"):
            qp = {k: list(v) for k, v in base_params.items()}
            apply_status(qp, current_scope)
            apply_source(qp, s)
            source_urls[s.lower()] = "?" + urlencode(qp, doseq=True)
        quick_form = self.QuickLoanForm(initial=initial)
        ctx = {
            "quick_loan_form": quick_form,
            "quick_loan_api_url": "/admin/circulation/loan/shto-huazim/api/",
            "quick_loan_create_url": "/admin/circulation/loan/shto-huazim/krijo/",
            "current_scope": current_scope,
            "current_source": current_source,
            "loan_status_urls": status_urls,
            "loan_source_urls": source_urls,
            "export_excel_url": "/admin/circulation/loan/eksporto-excel/" + ("?" + request.GET.urlencode() if request.GET else ""),
            "export_pdf_url": "/admin/circulation/loan/eksporto-pdf/" + ("?" + request.GET.urlencode() if request.GET else ""),
            "export_excel_base": "/admin/circulation/loan/eksporto-excel/",
            "export_pdf_base": "/admin/circulation/loan/eksporto-pdf/",
            "export_modal_report_label": "Huazime",
            "export_modal_has_book": True,
            "export_modal_has_author": True,
            "export_modal_has_member": True,
            "export_modal_has_dates": True,
            "export_books": list(Book.objects.filter(is_deleted=False).order_by("title")[:400].values_list("id", "title")),
            "export_authors": list(Author.objects.order_by("name")[:400].values_list("id", "name")),
            "export_members": _export_members_choices(),
        }
        if extra_context:
            ctx.update(extra_context)
        return super().changelist_view(request, extra_context=ctx)

    def quick_loan_api(self, request: HttpRequest):
        # Lightweight helper for JS (member lookup + availability).
        nid = (request.GET.get("national_id") or "").strip()
        book_id = (request.GET.get("book_id") or "").strip()
        pickup_date = (request.GET.get("pickup_date") or "").strip()
        return_date = (request.GET.get("return_date") or "").strip()

        member = None
        mp = None
        if nid:
            mp = MemberProfile.objects.filter(national_id=nid).select_related("user").first()
            if mp:
                member = {
                    "member_no": mp.member_no,
                    "full_name": mp.full_name or (mp.user.get_full_name() if mp.user_id else ""),
                    "phone": mp.phone,
                    "photo_url": (mp.photo.url if getattr(mp, "photo", None) else ""),
                }

        avail = None
        error = None
        book_info = None
        smart = {"can_checkout": True, "warnings": [], "best_copy": None}
        if book_id:
            b = Book.objects.filter(id=book_id).first()
            if b:
                best_copy = suggest_best_copy_for_quick_checkout(b.id)
                book_info = {
                    "title": b.title,
                    "isbn": (b.isbn or "").strip(),
                    "suggested_copy_barcode": (best_copy.get("barcode") if best_copy else ""),
                }
                smart["best_copy"] = best_copy

                if mp and Loan.objects.filter(member=mp, copy__book_id=b.id, status=LoanStatus.ACTIVE).exists():
                    smart["warnings"].append(
                        {
                            "level": "warning",
                            "code": "member_has_same_book",
                            "text": "Ky anëtar ka tashmë një huazim aktiv për këtë titull.",
                        }
                    )

        if book_id and pickup_date and return_date:
            try:
                avail = get_book_availability_for_range(int(book_id), pickup_date, return_date)
                if avail["total"] <= 0:
                    smart["can_checkout"] = False
                    smart["warnings"].append(
                        {
                            "level": "danger",
                            "code": "no_inventory",
                            "text": "Ky titull nuk ka kopje në inventar.",
                        }
                    )
                elif avail["free"] <= 0:
                    smart["can_checkout"] = False
                    smart["warnings"].append(
                        {
                            "level": "danger",
                            "code": "date_conflict",
                            "text": "Konflikt date: të gjitha kopjet janë të zëna në intervalin e zgjedhur.",
                        }
                    )
                elif avail["free"] == 1:
                    smart["warnings"].append(
                        {
                            "level": "warning",
                            "code": "limited_capacity",
                            "text": "Vetëm 1 kopje e lirë në këtë interval. Rekomandohet konfirmim i shpejtë.",
                        }
                    )
            except Exception as e:
                error = str(e)
                smart["can_checkout"] = False
                smart["warnings"].append(
                    {
                        "level": "danger",
                        "code": "invalid_dates",
                        "text": str(e),
                    }
                )

        return JsonResponse(
            {
                "member": member,
                "availability": avail,
                "book": book_info,
                "smart": smart,
                "error": error,
            }
        )

    def quick_loan_create_api(self, request: HttpRequest):
        if request.method != "POST":
            return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        nid = (payload.get("national_id") or "").strip()
        book_id = int(payload.get("book_id") or 0)
        pickup_date = (payload.get("pickup_date") or "").strip()
        return_date = (payload.get("return_date") or "").strip()
        note = (payload.get("note") or "").strip()

        if not nid or not book_id or not pickup_date or not return_date:
            return JsonResponse({"ok": False, "error": "Plotëso të gjitha fushat e detyrueshme."}, status=400)

        try:
            loan = quick_checkout_by_national_id(
                national_id=nid,
                book_id=book_id,
                pickup_date=pickup_date,
                return_date=return_date,
                note=note,
                loaned_by=request.user,
                source_screen="admin.loan.quick_modal",
                reason="Krijuar nga modalja 'Shto huazim'.",
            )
            return JsonResponse(
                {
                    "ok": True,
                    "loan_id": loan.id,
                    "copy_barcode": loan.copy.barcode,
                    "book_title": loan.copy.book.title,
                    "book_isbn": (loan.copy.book.isbn or "").strip(),
                    "redirect": "/admin/circulation/loan/",
                }
            )
        except PolicyViolation as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)
        except Exception:
            return JsonResponse({"ok": False, "error": "Nuk u krye huazimi."}, status=500)



class HoldAdmin(admin.ModelAdmin):
    list_display = ("id", "book", "member", "status", "position", "created_at", "ready_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("book__title", "member__member_no", "member__user__username")
    autocomplete_fields = ("book", "member")
    list_select_related = ("book", "member")
    form = HoldAdminForm

    fieldsets = (
        ("Rezervimi", {"fields": ("member", "book", "status", "position")}),
        ("Afatet", {"fields": ("created_at", "ready_at", "expires_at")}),
    )
    readonly_fields = ("created_at",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    change_list_template = "admin/circulation/reservation/change_list.html"
    list_display = (
        "member_display",
        "book_display",
        "pickup_date_display",
        "return_date_display",
        "expiry_badge",
        "status",
        "loan_action",
    )
    list_filter = ("status",)
    search_fields = ("book__title", "member__member_no", "member__user__username")
    autocomplete_fields = ("book", "member")
    list_select_related = ("book", "member", "loan", "created_by", "borrowed_by")
    readonly_fields = ("created_at", "updated_at", "source_request", "loan", "created_by", "borrowed_by", "audit_timeline_display")

    fieldsets = (
        ("Rezervimi", {"fields": ("member", "book", "pickup_date", "return_date", "status")}),
        ("Lidhje", {"fields": ("source_request", "loan")}),
        ("Auditim", {"fields": ("created_by", "borrowed_by")}),
        ("Timeline e auditimit", {"fields": ("audit_timeline_display",)}),
        ("Meta", {"fields": ("created_at", "updated_at")}),
    )

    actions = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        scope = (request.GET.get("status__exact") or "ALL").upper()
        if scope == "ALL":
            return qs
        if scope in ("APPROVED", "BORROWED", "EXPIRED", "CANCELLED"):
            return qs.filter(status=scope)
        return qs

    @admin.display(description="Anëtari")
    def member_display(self, obj: Reservation):
        m = obj.member
        label = (m.full_name or "").strip() or m.member_no
        url = f"/panel/members/{m.id}/"
        if getattr(m, "photo", None):
            avatar = format_html(
                '<img src="{}" style="width:30px;height:30px;border-radius:999px;object-fit:cover;margin-right:8px;" />',
                m.photo.url,
            )
        else:
            avatar = format_html(
                '<span style="width:30px;height:30px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;'
                'margin-right:8px;background:rgba(49,145,137,.14);color:#1f5f5a;font-weight:800;font-size:12px;">{}</span>',
                (label[:1] or "A").upper(),
            )
        return format_html(
            '<a href="{}" style="display:inline-flex;align-items:center;"><span>{}</span><span><b>{}</b><small style="display:block;opacity:.78;">{}</small></span></a>',
            url,
            avatar,
            label,
            m.member_no,
        )

    @admin.display(description="Libri", ordering="book__title")
    def book_display(self, obj: Reservation):
        return format_html('<a href="/admin/catalog/book/{}/change/" style="font-weight:800;">{}</a>', obj.book_id, obj.book.title)

    @admin.display(description="Marrja", ordering="pickup_date")
    def pickup_date_display(self, obj: Reservation):
        return obj.pickup_date.strftime("%d/%m/%Y")

    @admin.display(description="Kthimi", ordering="return_date")
    def return_date_display(self, obj: Reservation):
        return obj.return_date.strftime("%d/%m/%Y")

    @admin.display(description="Afati")
    def expiry_badge(self, obj: Reservation):
        if obj.status != ReservationStatus.APPROVED:
            return "—"
        policy = _get_reservation_timing_policy()
        grace_days = int(policy.reservation_grace_days or 0)
        warning_hours = int(policy.reservation_warning_hours or 0)

        expiry_date = obj.pickup_date + timedelta(days=grace_days)
        expiry_dt = timezone.make_aware(datetime.combine(expiry_date, time(23, 59, 59)))
        now = timezone.now()
        seconds_left = int((expiry_dt - now).total_seconds())

        if seconds_left <= 0:
            return format_html(
                '<span style="display:inline-flex;align-items:center;border-radius:999px;padding:3px 10px;'
                'font-size:11px;font-weight:900;background:rgba(239,68,68,.14);color:#991b1b;">Skaduar</span>'
            )
        if warning_hours > 0 and seconds_left <= warning_hours * 3600:
            return format_html(
                '<span style="display:inline-flex;align-items:center;border-radius:999px;padding:3px 10px;'
                'font-size:11px;font-weight:900;background:rgba(245,158,11,.16);color:#92400e;">Afër skadimit</span>'
            )
        return format_html(
            '<span style="display:inline-flex;align-items:center;border-radius:999px;padding:3px 10px;'
            'font-size:11px;font-weight:900;background:rgba(22,163,74,.14);color:#14532d;">Në afat</span>'
        )

    @admin.display(description="Timeline")
    def audit_timeline_display(self, obj: Reservation):
        return _build_audit_timeline_html(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            object_id=str(obj.pk),
        )

    def save_model(self, request, obj, form, change):
        before = None
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        # If staff changes status to BORROWED, convert to a Loan automatically.
        if change and obj.pk:
            prev = Reservation.objects.get(pk=obj.pk)
            before = prev
            if prev.status == ReservationStatus.APPROVED and obj.status == ReservationStatus.BORROWED:
                try:
                    borrow_from_reservation(
                        reservation_id=obj.id,
                        decided_by=request.user,
                        source_screen="admin.reservation.change_form",
                        reason="Statusi u kalua manualisht në 'U huazua'.",
                    )
                    self.message_user(request, "Rezervimi u kalua në Huazim me sukses.")
                except PolicyViolation as e:
                    # Keep it approved if borrow fails
                    obj.status = prev.status
                    self.message_user(request, f"Nuk u huazua: {str(e)}", level="ERROR")
                return

        super().save_model(request, obj, form, change)
        if not change:
            log_audit_event(
                target=obj,
                action_type="RESERVATION_CREATED_MANUAL",
                actor=request.user,
                source_screen="admin.reservation.change_form",
                metadata={"reservation_id": obj.id},
            )
            return
        if before:
            changed = {}
            for field in ("status", "pickup_date", "return_date", "book_id", "member_id"):
                old_v = getattr(before, field, None)
                new_v = getattr(obj, field, None)
                if old_v != new_v:
                    changed[field] = {
                        "old": old_v.isoformat() if hasattr(old_v, "isoformat") else old_v,
                        "new": new_v.isoformat() if hasattr(new_v, "isoformat") else new_v,
                    }
            if changed:
                log_audit_event(
                    target=obj,
                    loan=obj.loan if obj.loan_id else None,
                    action_type="RESERVATION_UPDATED_MANUAL",
                    actor=request.user,
                    source_screen="admin.reservation.change_form",
                    changes=changed,
                )
    class QuickReservationForm(forms.Form):
        class BookChoiceField(forms.ModelChoiceField):
            def label_from_instance(self, obj):
                title = obj.title or "Pa titull"
                isbn = (obj.isbn or "").strip()
                return f"{title} (ISBN: {isbn})" if isbn else title

        national_id = forms.CharField(max_length=32, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "p.sh. J50408078S"}))
        book = BookChoiceField(queryset=Book.objects.filter(is_deleted=False).order_by("title"), widget=forms.Select(attrs={"class": "form-control"}))
        pickup_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
        return_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    def _apply_export_filters_reservation(self, request, qs):
        date_from = (request.GET.get("date_from") or "").strip()
        date_to = (request.GET.get("date_to") or "").strip()
        book_id = (request.GET.get("book_id") or "").strip()
        author_id = (request.GET.get("author_id") or "").strip()
        member_id = (request.GET.get("member_id") or "").strip()
        if date_from:
            qs = qs.filter(pickup_date__gte=date_from)
        if date_to:
            qs = qs.filter(pickup_date__lte=date_to)
        if book_id:
            qs = qs.filter(book_id=book_id)
        if author_id:
            qs = qs.filter(book__authors__id=author_id).distinct()
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs

    def get_urls(self):
        urls = super().get_urls()
        from smart_library.reports import export_reservations_excel, export_reservations_pdf

        def export_excel(request):
            qs = self.get_queryset(request)
            qs = self._apply_export_filters_reservation(request, qs)
            wb = export_reservations_excel(qs)
            resp = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="raport_rezervime.xlsx"'},
            )
            wb.save(resp)
            return resp

        def export_pdf(request):
            qs = self.get_queryset(request)
            qs = self._apply_export_filters_reservation(request, qs)
            pdf_bytes = export_reservations_pdf(qs)
            return HttpResponse(pdf_bytes, content_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="raport_rezervime.pdf"'})

        custom = [
            path("shto-rezervim/api/", self.admin_site.admin_view(self.quick_reservation_api), name="circulation_reservation_quick_api"),
            path("shto-rezervim/krijo/", self.admin_site.admin_view(self.quick_reservation_create_api), name="circulation_reservation_quick_create_api"),
            path("<int:reservation_id>/huazo/", self.admin_site.admin_view(self.borrow_now_view), name="circulation_reservation_borrow_now"),
            path("eksporto-excel/", self.admin_site.admin_view(export_excel), name="circulation_reservation_export_excel"),
            path("eksporto-pdf/", self.admin_site.admin_view(export_pdf), name="circulation_reservation_export_pdf"),
        ]
        return custom + urls

    @admin.display(description="Huazimi")
    def loan_action(self, obj: Reservation):
        if obj.loan_id:
            return format_html('<a class="btn btn-xs btn-outline-secondary" href="/admin/circulation/loan/{}/change/">Hap huazimin</a>', obj.loan_id)
        if obj.status == ReservationStatus.APPROVED:
            today = timezone.localdate()
            can_use_today = Copy.objects.filter(
                book_id=obj.book_id,
                status=CopyStatus.AVAILABLE,
                is_deleted=False,
            ).exists()
            if obj.pickup_date and obj.pickup_date != today:
                return format_html(
                    '<a class="btn btn-xs btn-primary js-borrow-reservation" href="/admin/circulation/reservation/{}/huazo/" '
                    'data-requires-confirm="1" data-pickup-date="{}" data-use-today-ok="{}" '
                    'data-use-today-msg="Libri është i huazuar dhe nuk ka kopje të lira për sot.">Huazo</a>',
                    obj.id,
                    obj.pickup_date.strftime("%d/%m/%Y"),
                    "1" if can_use_today else "0",
                )
            return format_html(
                '<a class="btn btn-xs btn-primary js-borrow-reservation" href="/admin/circulation/reservation/{}/huazo/" data-requires-confirm="0">Huazo</a>',
                obj.id,
            )
        return "—"

    def borrow_now_view(self, request: HttpRequest, reservation_id: int):
        reservation = Reservation.objects.filter(id=reservation_id).first()
        if not reservation:
            messages.error(request, "Rezervimi nuk u gjet.")
            return redirect("/admin/circulation/reservation/")

        try:
            if request.GET.get("use_today") == "1":
                reservation.pickup_date = timezone.localdate()
                reservation.save(update_fields=["pickup_date", "updated_at"])
            loan = borrow_from_reservation(
                reservation_id=reservation_id,
                decided_by=request.user,
                source_screen="admin.reservation.list.borrow_now",
                reason="Veprimi 'Huazo' nga lista e rezervimeve.",
            )
            messages.success(request, "Rezervimi u kalua në huazim me sukses.")
            return redirect(f"/admin/circulation/loan/?id__exact={loan.id}")
        except PolicyViolation as e:
            messages.error(request, f"Nuk u huazua: {str(e)}")
            return redirect("/admin/circulation/reservation/")

    def changelist_view(self, request, extra_context=None):
        policy = _get_reservation_timing_policy()
        expired_count = auto_expire_overdue_reservations(
            actor=request.user,
            source_screen="admin.reservation.list.auto_expire",
            reason="Skadim automatik nga sistemi sepse data e marrjes kaloi pa huazim.",
        )
        if expired_count:
            self.message_user(
                request,
                f"{expired_count} rezervime u skaduan automatikisht (auto-release).",
                level=messages.INFO,
            )
        initial = {
            "pickup_date": timezone.now().date(),
            "return_date": (timezone.now() + timezone.timedelta(days=7)).date(),
        }
        current_scope = (request.GET.get("status__exact") or "ALL").upper()
        if current_scope not in ("APPROVED", "BORROWED", "EXPIRED", "CANCELLED", "ALL"):
            current_scope = "ALL"
        ctx = {
            "quick_res_form": self.QuickReservationForm(initial=initial),
            "quick_res_api_url": "/admin/circulation/reservation/shto-rezervim/api/",
            "quick_res_create_url": "/admin/circulation/reservation/shto-rezervim/krijo/",
            "current_scope": current_scope,
            "reservation_grace_days": int(policy.reservation_grace_days or 0),
            "reservation_warning_hours": int(policy.reservation_warning_hours or 0),
            "export_excel_url": "/admin/circulation/reservation/eksporto-excel/" + ("?" + request.GET.urlencode() if request.GET else ""),
            "export_pdf_url": "/admin/circulation/reservation/eksporto-pdf/" + ("?" + request.GET.urlencode() if request.GET else ""),
            "export_excel_base": "/admin/circulation/reservation/eksporto-excel/",
            "export_pdf_base": "/admin/circulation/reservation/eksporto-pdf/",
            "export_modal_report_label": "Rezervime",
            "export_modal_has_book": True,
            "export_modal_has_author": True,
            "export_modal_has_member": True,
            "export_modal_has_dates": True,
            "export_books": list(Book.objects.filter(is_deleted=False).order_by("title")[:400].values_list("id", "title")),
            "export_authors": list(Author.objects.order_by("name")[:400].values_list("id", "name")),
            "export_members": _export_members_choices(),
        }
        if extra_context:
            ctx.update(extra_context)
        return super().changelist_view(request, extra_context=ctx)

    def quick_reservation_api(self, request: HttpRequest):
        nid = (request.GET.get("national_id") or "").strip()
        book_id = (request.GET.get("book_id") or "").strip()
        pickup_date = (request.GET.get("pickup_date") or "").strip()
        return_date = (request.GET.get("return_date") or "").strip()
        member = None
        if nid:
            mp = MemberProfile.objects.filter(national_id=nid).select_related("user").first()
            if mp:
                member = {
                    "member_no": mp.member_no,
                    "full_name": mp.full_name or (mp.user.get_full_name() if mp.user_id else ""),
                    "photo_url": (mp.photo.url if getattr(mp, "photo", None) else ""),
                }
        book_info = None
        if book_id:
            b = Book.objects.filter(id=book_id).first()
            if b:
                book_info = {"title": b.title, "isbn": (b.isbn or "").strip()}
        avail = None
        error = None
        if book_id and pickup_date and return_date:
            try:
                avail = get_book_availability_for_range(int(book_id), pickup_date, return_date)
            except Exception as e:
                error = str(e)
        return JsonResponse({"member": member, "book": book_info, "availability": avail, "error": error})

    def quick_reservation_create_api(self, request: HttpRequest):
        if request.method != "POST":
            return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}
        nid = (payload.get("national_id") or "").strip()
        book_id = int(payload.get("book_id") or 0)
        pickup_date = (payload.get("pickup_date") or "").strip()
        return_date = (payload.get("return_date") or "").strip()
        if not nid or not book_id or not pickup_date or not return_date:
            return JsonResponse({"ok": False, "error": "Plotëso të gjitha fushat."}, status=400)
        member = MemberProfile.objects.filter(national_id=nid).first()
        if not member:
            return JsonResponse({"ok": False, "error": "Nuk u gjet anëtar me këtë Nr. ID."}, status=400)
        try:
            avail = get_book_availability_for_range(book_id, pickup_date, return_date)
            if avail["total"] > 0 and avail["occupied"] >= avail["total"]:
                return JsonResponse({"ok": False, "error": "Titulli është i zënë në këto data."}, status=400)
            res = Reservation.objects.create(
                member=member,
                book_id=book_id,
                pickup_date=pickup_date,
                return_date=return_date,
                status=ReservationStatus.APPROVED,
                created_by=request.user,
            )
            return JsonResponse({"ok": True, "reservation_id": res.id, "redirect": "/admin/circulation/reservation/"})
        except Exception:
            return JsonResponse({"ok": False, "error": "Nuk u krijua rezervimi."}, status=500)


class ReservationRequestAdminForm(forms.ModelForm):
    class Meta:
        model = ReservationRequest
        fields = "__all__"
        labels = {
            "member": "Anëtari",
            "book": "Libri",
            "pickup_date": "Do ta marrë më",
            "return_date": "Do ta dorëzojë më",
            "status": "Statusi",
            "note": "Shënim (opsionale)",
            "created_at": "Krijuar më",
            "decided_at": "Vendosur më",
            "decided_by": "Vendosur nga",
            "decision_reason": "Arsye (për refuzim)",
        }

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        reason = (cleaned.get("decision_reason") or "").strip()
        if status == ReservationRequestStatus.REJECTED and not reason:
            self.add_error("decision_reason", "Vendos arsyen e refuzimit.")
        return cleaned


@admin.register(ReservationRequest)
class ReservationRequestAdmin(admin.ModelAdmin):
    change_list_template = "admin/circulation/reservationrequest/change_list.html"
    list_display = (
        "member_display",
        "book_display",
        "pickup_date_display",
        "return_date_display",
        "status",
        "created_at_display",
        "last_activity_display",
        "decision_actions",
    )
    list_filter = ("status",)
    search_fields = ("book__title", "member__member_no", "member__user__username")
    autocomplete_fields = ("book", "member")
    list_select_related = ("book", "member", "created_by", "decided_by")
    form = ReservationRequestAdminForm

    fieldsets = (
        ("Kërkesa për rezervim", {"fields": ("member", "book", "pickup_date", "return_date", "note", "status")}),
        ("Vendimi i stafit", {"fields": ("decided_by", "decided_at", "decision_reason")}),
        ("Auditim", {"fields": ("created_by",)}),
        ("Timeline e auditimit", {"fields": ("audit_timeline_display",)}),
    )
    readonly_fields = ("created_at", "decided_at", "decided_by", "created_by", "audit_timeline_display")

    actions = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        scope = (request.GET.get("status__exact") or "ALL").upper()
        if scope == "ALL":
            return qs
        if scope in ("PENDING", "APPROVED", "REJECTED", "CANCELLED"):
            return qs.filter(status=scope)
        return qs

    @admin.display(description="Anëtari")
    def member_display(self, obj: ReservationRequest):
        m = obj.member
        label = (m.full_name or "").strip() or m.member_no
        url = f"/panel/members/{m.id}/"
        if getattr(m, "photo", None):
            avatar = format_html(
                '<img src="{}" style="width:30px;height:30px;border-radius:999px;object-fit:cover;margin-right:8px;" />',
                m.photo.url,
            )
        else:
            avatar = format_html(
                '<span style="width:30px;height:30px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;'
                'margin-right:8px;background:rgba(49,145,137,.14);color:#1f5f5a;font-weight:800;font-size:12px;">{}</span>',
                (label[:1] or "A").upper(),
            )
        return format_html(
            '<a href="{}" style="display:inline-flex;align-items:center;"><span>{}</span><span><b>{}</b><small style="display:block;opacity:.78;">{}</small></span></a>',
            url,
            avatar,
            label,
            m.member_no,
        )

    @admin.display(description="Libri", ordering="book__title")
    def book_display(self, obj: ReservationRequest):
        return format_html('<a href="/admin/catalog/book/{}/change/" style="font-weight:800;">{}</a>', obj.book_id, obj.book.title)

    @admin.display(description="Do ta marrë më", ordering="pickup_date")
    def pickup_date_display(self, obj: ReservationRequest):
        return obj.pickup_date.strftime("%d/%m/%Y") if obj.pickup_date else "—"

    @admin.display(description="Do ta dorëzojë më", ordering="return_date")
    def return_date_display(self, obj: ReservationRequest):
        return obj.return_date.strftime("%d/%m/%Y") if obj.return_date else "—"

    @admin.display(description="Krijuar më", ordering="created_at")
    def created_at_display(self, obj: ReservationRequest):
        if not obj.created_at:
            return "—"
        local_dt = timezone.localtime(obj.created_at)
        return local_dt.strftime("%d/%m/%Y %H:%M")

    @admin.display(description="Aktiviteti i fundit")
    def last_activity_display(self, obj: ReservationRequest):
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
        at = timezone.localtime(entry.created_at).strftime("%d/%m/%Y %H:%M")
        return format_html(
            '<span style="display:inline-flex;flex-direction:column;gap:2px;">'
            "<b>{}</b>"
            '<small style="opacity:.78;">{}</small>'
            "</span>",
            entry.action_type_sq,
            at,
        )

    @admin.display(description="Timeline")
    def audit_timeline_display(self, obj: ReservationRequest):
        return _build_audit_timeline_html(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            object_id=str(obj.pk),
        )

    @admin.display(description="Vendimi")
    def decision_actions(self, obj: ReservationRequest):
        if obj.status == ReservationRequestStatus.PENDING:
            return format_html(
                '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
                '<a class="btn btn-xs btn-success" href="/admin/circulation/reservationrequest/{}/mirato/">Mirato</a>'
                '<a class="btn btn-xs btn-outline-danger" href="/admin/circulation/reservationrequest/{}/refuzo/">Refuzo</a>'
                '<a class="btn btn-xs btn-outline-secondary" href="/admin/circulation/reservationrequest/{}/change/">Hap</a>'
                "</div>",
                obj.id,
                obj.id,
                obj.id,
            )
        decided_at = timezone.localtime(obj.decided_at).strftime("%d/%m/%Y %H:%M") if obj.decided_at else "—"
        return format_html(
            '<div style="display:flex;align-items:center;gap:8px;">'
            '<span style="font-size:12px;opacity:.85;">{} • {}</span>'
            '<a class="btn btn-xs btn-outline-secondary" href="/admin/circulation/reservationrequest/{}/change/">Detaje</a>'
            "</div>",
            obj.get_status_display(),
            decided_at,
            obj.id,
        )

    def save_model(self, request, obj, form, change):
        before = None
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        # Ensure decisions are consistent and create Hold on approval.
        if change and obj.pk:
            prev = ReservationRequest.objects.get(pk=obj.pk)
            before = prev
            if prev.status == ReservationRequestStatus.PENDING and obj.status == ReservationRequestStatus.APPROVED:
                approve_reservation_request(
                    request_id=obj.id,
                    decided_by=request.user,
                    source_screen="admin.reservationrequest.change_form",
                    reason="Miratuar nga forma e kërkesës.",
                )
                return
            if prev.status == ReservationRequestStatus.PENDING and obj.status == ReservationRequestStatus.REJECTED:
                reject_reservation_request(
                    request_id=obj.id,
                    decided_by=request.user,
                    reason=(obj.decision_reason or "").strip(),
                    source_screen="admin.reservationrequest.change_form",
                )
                return

        super().save_model(request, obj, form, change)
        if not change:
            log_audit_event(
                target=obj,
                action_type="RESERVATION_REQUEST_CREATED_MANUAL",
                actor=request.user,
                source_screen="admin.reservationrequest.change_form",
                metadata={"request_id": obj.id},
            )
            return
        if before:
            changed = {}
            for field in ("status", "pickup_date", "return_date", "book_id", "member_id", "decision_reason"):
                old_v = getattr(before, field, None)
                new_v = getattr(obj, field, None)
                if old_v != new_v:
                    changed[field] = {
                        "old": old_v.isoformat() if hasattr(old_v, "isoformat") else old_v,
                        "new": new_v.isoformat() if hasattr(new_v, "isoformat") else new_v,
                    }
            if changed:
                log_audit_event(
                    target=obj,
                    action_type="RESERVATION_REQUEST_UPDATED_MANUAL",
                    actor=request.user,
                    source_screen="admin.reservationrequest.change_form",
                    changes=changed,
                    severity=AuditSeverity.INCIDENT if obj.status == ReservationRequestStatus.REJECTED else AuditSeverity.INFO,
                )

    class QuickReservationRequestForm(forms.Form):
        class BookChoiceField(forms.ModelChoiceField):
            def label_from_instance(self, obj):
                title = obj.title or "Pa titull"
                isbn = (obj.isbn or "").strip()
                return f"{title} (ISBN: {isbn})" if isbn else title

        national_id = forms.CharField(max_length=32, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "p.sh. J50408078S"}))
        book = BookChoiceField(queryset=Book.objects.filter(is_deleted=False).order_by("title"), widget=forms.Select(attrs={"class": "form-control"}))
        pickup_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
        return_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
        note = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Shënim opsional"}))

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("shto-kerkese/api/", self.admin_site.admin_view(self.quick_request_api), name="circulation_request_quick_api"),
            path("shto-kerkese/krijo/", self.admin_site.admin_view(self.quick_request_create_api), name="circulation_request_quick_create_api"),
            path("<int:request_id>/mirato/", self.admin_site.admin_view(self.approve_now_view), name="circulation_request_approve_now"),
            path("<int:request_id>/refuzo/", self.admin_site.admin_view(self.reject_now_view), name="circulation_request_reject_now"),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        initial = {
            "pickup_date": timezone.now().date(),
            "return_date": (timezone.now() + timezone.timedelta(days=7)).date(),
        }
        current_scope = (request.GET.get("status__exact") or "ALL").upper()
        if current_scope not in ("PENDING", "APPROVED", "REJECTED", "CANCELLED", "ALL"):
            current_scope = "ALL"
        ctx = {
            "quick_req_form": self.QuickReservationRequestForm(initial=initial),
            "quick_req_api_url": "/admin/circulation/reservationrequest/shto-kerkese/api/",
            "quick_req_create_url": "/admin/circulation/reservationrequest/shto-kerkese/krijo/",
            "current_scope": current_scope,
        }
        if extra_context:
            ctx.update(extra_context)
        return super().changelist_view(request, extra_context=ctx)

    def quick_request_api(self, request: HttpRequest):
        nid = (request.GET.get("national_id") or "").strip()
        book_id = (request.GET.get("book_id") or "").strip()
        pickup_date = (request.GET.get("pickup_date") or "").strip()
        return_date = (request.GET.get("return_date") or "").strip()
        member = None
        if nid:
            mp = MemberProfile.objects.filter(national_id=nid).select_related("user").first()
            if mp:
                member = {
                    "member_no": mp.member_no,
                    "full_name": mp.full_name or (mp.user.get_full_name() if mp.user_id else ""),
                    "photo_url": (mp.photo.url if getattr(mp, "photo", None) else ""),
                }
        book_info = None
        if book_id:
            b = Book.objects.filter(id=book_id).first()
            if b:
                book_info = {"title": b.title, "isbn": (b.isbn or "").strip()}
        avail = None
        error = None
        if book_id and pickup_date and return_date:
            try:
                avail = get_book_availability_for_range(int(book_id), pickup_date, return_date)
            except Exception as e:
                error = str(e)
        return JsonResponse({"member": member, "book": book_info, "availability": avail, "error": error})

    def quick_request_create_api(self, request: HttpRequest):
        if request.method != "POST":
            return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}
        nid = (payload.get("national_id") or "").strip()
        book_id = int(payload.get("book_id") or 0)
        pickup_date = (payload.get("pickup_date") or "").strip()
        return_date = (payload.get("return_date") or "").strip()
        note = (payload.get("note") or "").strip()
        if not nid or not book_id or not pickup_date or not return_date:
            return JsonResponse({"ok": False, "error": "Plotëso të gjitha fushat."}, status=400)
        member = MemberProfile.objects.filter(national_id=nid).first()
        if not member:
            return JsonResponse({"ok": False, "error": "Nuk u gjet anëtar me këtë Nr. ID."}, status=400)
        try:
            req = create_reservation_request(
                member_no=member.member_no,
                book_id=book_id,
                pickup_date=pickup_date,
                return_date=return_date,
                note=note,
                created_by=request.user,
                source_screen="admin.reservationrequest.quick_modal",
            )
            return JsonResponse({"ok": True, "request_id": req.id, "redirect": "/admin/circulation/reservationrequest/"})
        except PolicyViolation as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)
        except Exception:
            return JsonResponse({"ok": False, "error": "Nuk u krijua kërkesa."}, status=500)

    def approve_now_view(self, request: HttpRequest, request_id: int):
        obj = ReservationRequest.objects.filter(pk=request_id).first()
        if not obj:
            self.message_user(request, "Kërkesa nuk u gjet.", level=messages.ERROR)
            return redirect("/admin/circulation/reservationrequest/")
        if obj.status != ReservationRequestStatus.PENDING:
            self.message_user(request, "Kjo kërkesë ka marrë vendim më parë.", level=messages.WARNING)
            return redirect("/admin/circulation/reservationrequest/")
        try:
            approve_reservation_request(
                request_id=obj.id,
                decided_by=request.user,
                source_screen="admin.reservationrequest.list.approve_now",
                reason="Miratim i shpejtë nga lista.",
            )
            self.message_user(request, "Kërkesa u miratua me sukses.", level=messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"Nuk u miratua kërkesa: {exc}", level=messages.ERROR)
        return redirect("/admin/circulation/reservationrequest/")

    def reject_now_view(self, request: HttpRequest, request_id: int):
        obj = ReservationRequest.objects.filter(pk=request_id).first()
        if not obj:
            self.message_user(request, "Kërkesa nuk u gjet.", level=messages.ERROR)
            return redirect("/admin/circulation/reservationrequest/")
        if obj.status != ReservationRequestStatus.PENDING:
            self.message_user(request, "Kjo kërkesë ka marrë vendim më parë.", level=messages.WARNING)
            return redirect("/admin/circulation/reservationrequest/")
        try:
            reject_reservation_request(
                request_id=obj.id,
                decided_by=request.user,
                reason="Refuzuar nga stafi.",
                source_screen="admin.reservationrequest.list.reject_now",
            )
            self.message_user(request, "Kërkesa u refuzua.", level=messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"Nuk u refuzua kërkesa: {exc}", level=messages.ERROR)
        return redirect("/admin/circulation/reservationrequest/")
