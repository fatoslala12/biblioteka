import json

from django.contrib import admin
from django.db.models import Q
from django.utils import timezone
from django.utils.html import format_html

from .models import AuditEntry


class IncidentFilter(admin.SimpleListFilter):
    title = "Pamja"
    parameter_name = "incident_only"

    def lookups(self, request, model_admin):
        return (
            ("all", "Të gjitha"),
            ("incident", "Vetëm incidente"),
            ("info", "Vetëm informuese"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "incident":
            return queryset.filter(severity="INCIDENT")
        if value == "info":
            return queryset.filter(severity="INFO")
        return queryset


class AuditDomainFilter(admin.SimpleListFilter):
    title = "Kategoria"
    parameter_name = "domain"

    def lookups(self, request, model_admin):
        return (
            ("auth", "Logime"),
            ("member", "Veprime anëtari"),
            ("loan", "Huazime"),
            ("reservation", "Rezervime"),
            ("request", "Kërkesa rezervimi"),
            ("messages", "Mesazhet"),
            ("other", "Të tjera"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "auth":
            return queryset.filter(action_type__startswith="AUTH_")
        if value == "member":
            return queryset.filter(Q(action_type__startswith="MEMBER_") | Q(source_screen__startswith="member."))
        if value == "loan":
            return queryset.filter(action_type__startswith="LOAN_")
        if value == "reservation":
            return queryset.filter(action_type__startswith="RESERVATION_").exclude(action_type__startswith="RESERVATION_REQUEST_")
        if value == "request":
            return queryset.filter(action_type__startswith="RESERVATION_REQUEST_")
        if value == "messages":
            return queryset.filter(
                Q(action_type="CONTACT_MESSAGE_REPLIED") | Q(app_label="cms", model_name="contactmessage")
            )
        if value == "other":
            return queryset.exclude(action_type__startswith="LOAN_").exclude(
                action_type__startswith="RESERVATION_"
            ).exclude(action_type__startswith="AUTH_").exclude(action_type="CONTACT_MESSAGE_REPLIED")
        return queryset


class LoginEventFilter(admin.SimpleListFilter):
    title = "Filtri logimi"
    parameter_name = "login_event"

    def lookups(self, request, model_admin):
        return (
            ("all", "Të gjitha logimet"),
            ("success", "Hyrje të suksesshme"),
            ("failed", "Hyrje të dështuara"),
            ("logout", "Dalje"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "success":
            return queryset.filter(action_type="AUTH_LOGIN_SUCCESS")
        if value == "failed":
            return queryset.filter(action_type="AUTH_LOGIN_FAILED")
        if value == "logout":
            return queryset.filter(action_type="AUTH_LOGOUT")
        if value == "all":
            return queryset.filter(action_type__startswith="AUTH_")
        return queryset


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    change_form_template = "admin/change_form.html"
    list_display = (
        "created_at_display",
        "severity_badge",
        "action_type_display",
        "target_display",
        "loan",
        "actor_display",
        "ip_display",
        "browser_display",
        "source_screen_display",
    )
    list_filter = (IncidentFilter, AuditDomainFilter, LoginEventFilter, "action_type", "app_label", "model_name")
    search_fields = ("object_id", "object_repr", "reason", "source_screen", "actor__username")
    readonly_fields = (
        "created_at",
        "actor_display",
        "action_type_display",
        "severity_badge",
        "target_display",
        "loan",
        "ip_display",
        "browser_display",
        "source_screen_display",
        "reason_display",
        "changes_pretty",
        "metadata_pretty",
    )
    fields = (
        "created_at",
        "actor_display",
        "action_type_display",
        "severity_badge",
        "target_display",
        "loan",
        "ip_display",
        "browser_display",
        "source_screen_display",
        "reason_display",
        "changes_pretty",
        "metadata_pretty",
    )
    ordering = ("-created_at",)
    list_per_page = 30
    actions = None

    class Media:
        js = ("jazzmin/js/audit_admin.js",)

    def has_add_permission(self, request):
        return False

    @admin.display(description="Krijuar më", ordering="created_at")
    def created_at_display(self, obj: AuditEntry):
        if not obj.created_at:
            return "—"
        return timezone.localtime(obj.created_at).strftime("%d/%m/%Y %H:%M")

    @admin.display(description="Objekti", ordering="object_id")
    def target_display(self, obj: AuditEntry):
        model_labels = {
            ("circulation", "loan"): "Huazim",
            ("circulation", "reservation"): "Rezervim",
            ("circulation", "reservationrequest"): "Kërkesë rezervimi",
            ("accounts", "user"): "Përdorues",
            ("accounts", "memberprofile"): "Profil anëtari",
            ("cms", "contactmessage"): "Mesazh kontakt",
        }
        label = model_labels.get((obj.app_label, obj.model_name), f"{obj.app_label}.{obj.model_name}")
        return format_html(
            '<span class="sl-audit-target">{}</span><span class="sl-audit-target-sub">{}</span>',
            f"#{obj.object_id}",
            label,
        )

    @admin.display(description="Veprimi", ordering="action_type")
    def action_type_display(self, obj: AuditEntry):
        return format_html('<span class="sl-audit-action">{}</span>', obj.action_type_sq)

    @admin.display(description="Niveli", ordering="severity")
    def severity_badge(self, obj: AuditEntry):
        if obj.severity == "INCIDENT":
            return format_html('<span class="sl-audit-badge sl-audit-badge-incident">Incident</span>')
        return format_html('<span class="sl-audit-badge sl-audit-badge-info">Informues</span>')

    @admin.display(description="Përdoruesi", ordering="actor__username")
    def actor_display(self, obj: AuditEntry):
        if not obj.actor_id:
            return "Sistem"
        full = (obj.actor.get_full_name() or "").strip()
        label = full or obj.actor.username
        return format_html("<b>{}</b><br><small>@{}</small>", label, obj.actor.username)

    @admin.display(description="IP", ordering="ip_address")
    def ip_display(self, obj: AuditEntry):
        ip = obj.ip_address or (obj.metadata or {}).get("ip") or ""
        return ip or "—"

    @admin.display(description="Browser")
    def browser_display(self, obj: AuditEntry):
        return obj.browser_display

    @admin.display(description="Ekrani burim")
    def source_screen_display(self, obj: AuditEntry):
        return obj.screen_sq

    @admin.display(description="Arsye")
    def reason_display(self, obj: AuditEntry):
        return obj.reason or "—"

    @admin.display(description="Ndryshimet")
    def changes_pretty(self, obj: AuditEntry):
        if not obj.changes:
            return "—"
        text = json.dumps(obj.changes, ensure_ascii=False, indent=2)
        return format_html("<pre>{}</pre>", text)

    @admin.display(description="Metadata")
    def metadata_pretty(self, obj: AuditEntry):
        if not obj.metadata:
            return "—"
        text = json.dumps(obj.metadata, ensure_ascii=False, indent=2)
        return format_html("<pre>{}</pre>", text)
