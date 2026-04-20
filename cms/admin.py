from django.contrib import admin
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.template.loader import render_to_string

from audit.services import get_client_ip, log_audit_event

from .models import Announcement, ContactMessage, Event, Video, WeeklyBook


class ReadStatusFilter(admin.SimpleListFilter):
    title = "Status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return (
            ("unread", "Pa lexuar"),
            ("read", "Lexuar"),
        )

    def queryset(self, request, queryset):
        v = self.value()
        if v == "unread":
            return queryset.filter(is_read=False)
        if v == "read":
            return queryset.filter(is_read=True)
        return queryset


class RepliedStatusFilter(admin.SimpleListFilter):
    title = "Përgjigje"
    parameter_name = "replied"

    def lookups(self, request, model_admin):
        return (
            ("yes", "U përgjigj"),
            ("no", "Pa përgjigje"),
        )

    def queryset(self, request, queryset):
        v = self.value()
        if v == "yes":
            return queryset.filter(is_replied=True)
        if v == "no":
            return queryset.filter(is_replied=False)
        return queryset


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    change_form_template = "admin/cms/contactmessage/change_form.html"
    change_list_template = "admin/cms/contactmessage/change_list.html"
    list_display = ("subject_display", "name", "email", "created_at", "replied_badge")
    list_filter = (ReadStatusFilter, RepliedStatusFilter, ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = (
        "name",
        "email",
        "subject",
        "message",
        "created_at",
        "is_replied",
        "replied_at",
        "reply_subject",
        "reply_body",
        "replied_by",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_editable = ()
    fieldsets = ((None, {"fields": ("subject", "name", "email", "created_at", "is_read")}),)

    @admin.display(description="Subjekti", ordering="subject")
    def subject_display(self, obj: ContactMessage):
        subject = obj.subject or "—"
        if not obj.is_replied:
            return format_html(
                '<span style="font-weight:950;color:#0f172a;">{}</span>'
                '<span class="sl-new-badge" style="margin-left:8px;display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;'
                "background:rgba(13,148,136,.14);border:1px solid rgba(13,148,136,.28);color:#0f766e;font-weight:900;font-size:11px;"
                '">NEW</span>',
                subject,
            )
        return subject

    @admin.display(description="Përgjigjur")
    def replied_badge(self, obj: ContactMessage):
        if obj.is_replied:
            return format_html(
                '<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;color:#fff;background:#0f766e;font-weight:800;font-size:12px;">Po</span>'
            )
        return format_html(
            '<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;color:#fff;background:#64748b;font-weight:800;font-size:12px;">Jo</span>'
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:message_id>/reply/",
                self.admin_site.admin_view(self.reply_api),
                name="cms_contactmessage_reply",
            ),
        ]
        return custom + urls

    def reply_api(self, request, message_id: int):
        if request.method != "POST":
            return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)

        obj = ContactMessage.objects.filter(id=message_id).first()
        if not obj:
            return JsonResponse({"ok": False, "error": "Mesazhi nuk u gjet."}, status=404)

        body = (request.POST.get("body") or "").strip()
        if not body:
            return JsonResponse({"ok": False, "error": "Shkruaj përgjigjen."}, status=400)

        to_email = (obj.email or "").strip()
        if not to_email:
            return JsonResponse({"ok": False, "error": "Mesazhi nuk ka email."}, status=400)
        try:
            validate_email(to_email)
        except ValidationError:
            return JsonResponse(
                {"ok": False, "error": "Email-i i marrësit është i pavlefshëm (invalid).", "error_type": "INVALID_TO"},
                status=400,
            )

        subject = f"Re: {obj.subject}".strip()

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
        if not from_email:
            return JsonResponse(
                {"ok": False, "error": "Email nuk është konfiguruar. Vendos EMAIL_HOST_USER/EMAIL_HOST_PASSWORD në .env."},
                status=500,
            )

        try:
            replied_at = timezone.now()
            text_body = (
                f"Përgjigje nga Smart Library • Biblioteka Kamëz\\n\\n"
                f"Subjekti: {subject}\\n"
                f"---\\n"
                f"Përgjigja:\\n{body}\\n\\n"
                f"---\\nMesazhi yt origjinal:\\n{obj.message}\\n"
            )
            html_body = render_to_string(
                "cms/emails/contact_reply_user.html",
                {
                    "library_name": "Smart Library • Biblioteka Kamëz",
                    "subject": subject,
                    "to_email": to_email,
                    "from_email": from_email,
                    "sender_name": (obj.name or "").strip() or "Përdorues",
                    "sender_email": to_email,
                    "original_message": obj.message,
                    "reply_body": body,
                    "replied_at": replied_at,
                },
            )
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[to_email],
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)
        except Exception as e:
            return JsonResponse(
                {"ok": False, "error": f"Nuk u dërgua email-i: {e}.", "error_type": "SMTP_ERROR"}, status=500
            )

        obj.is_replied = True
        obj.replied_at = replied_at
        obj.replied_by = getattr(request, "user", None)
        obj.reply_subject = subject
        obj.reply_body = body
        obj.save(update_fields=["is_replied", "replied_at", "replied_by", "reply_subject", "reply_body"])

        try:
            LogEntry.objects.log_action(
                user_id=getattr(request.user, "pk", None),
                content_type_id=ContentType.objects.get_for_model(ContactMessage).pk,
                object_id=obj.pk,
                object_repr=str(obj),
                action_flag=CHANGE,
                change_message="U dërgua një përgjigje me email (Reply).",
            )
        except Exception:
            pass

        try:
            ip = get_client_ip(request) or None
            ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
            log_audit_event(
                target=obj,
                action_type="CONTACT_MESSAGE_REPLIED",
                actor=getattr(request, "user", None),
                source_screen="admin.contactmessage.reply",
                metadata={"to_email": to_email, "subject": subject},
                ip_address=ip,
                user_agent=ua,
            )
        except Exception:
            pass

        messages.success(request, "Përgjigja u dërgua me sukses.")
        return JsonResponse({"ok": True, "detail": "Email u dërgua me sukses.", "to": to_email})


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "published_at", "badge", "show_on_home", "is_published", "image_preview")
    list_filter = ("is_published", "show_on_home", "published_at")
    search_fields = ("title", "excerpt", "content")
    ordering = ("-published_at",)
    date_hierarchy = "published_at"

    @admin.display(description="Foto")
    def image_preview(self, obj: Announcement):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" style="width:48px;height:34px;border-radius:8px;object-fit:cover;border:1px solid rgba(15,23,42,.12);" />', obj.image.url)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "published_at", "starts_at", "location", "badge", "is_published", "image_preview")
    list_filter = ("is_published", "published_at", "starts_at")
    search_fields = ("title", "excerpt", "content", "location")
    ordering = ("-published_at",)
    date_hierarchy = "published_at"

    @admin.display(description="Foto")
    def image_preview(self, obj: Event):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" style="width:48px;height:34px;border-radius:8px;object-fit:cover;border:1px solid rgba(15,23,42,.12);" />', obj.image.url)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "published_at",
        "badge",
        "duration",
        "show_on_home",
        "is_published",
        "image_preview",
        "open_video",
    )
    list_filter = ("is_published", "show_on_home", "published_at")
    search_fields = ("title", "excerpt", "content", "video_url")
    ordering = ("-published_at",)
    date_hierarchy = "published_at"
    fields = (
        "title",
        "excerpt",
        "content",
        "published_at",
        "is_published",
        "video_url",
        "image",
        "badge",
        "duration",
        "show_on_home",
    )

    @admin.display(description="Foto")
    def image_preview(self, obj: Video):
        if not getattr(obj, "image", None):
            return "—"
        return format_html(
            '<img src="{}" style="width:48px;height:34px;border-radius:8px;object-fit:cover;border:1px solid rgba(15,23,42,.12);" />',
            obj.image.url,
        )

    @admin.display(description="Hap")
    def open_video(self, obj: Video):
        return format_html('<a class="btn btn-xs btn-outline-secondary" href="{}" target="_blank">Hap videon</a>', obj.video_url)


@admin.register(WeeklyBook)
class WeeklyBookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "published_at", "show_on_home", "is_published", "image_preview")
    list_filter = ("is_published", "show_on_home", "published_at")
    search_fields = ("title", "author", "excerpt", "content")
    ordering = ("-published_at",)
    date_hierarchy = "published_at"
    fields = (
        "title",
        "author",
        "excerpt",
        "content",
        "image",
        "cta_url",
        "cta_label",
        "published_at",
        "show_on_home",
        "is_published",
    )

    @admin.display(description="Kopertina")
    def image_preview(self, obj: WeeklyBook):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="width:48px;height:64px;border-radius:8px;object-fit:cover;border:1px solid rgba(15,23,42,.12);" />',
            obj.image.url,
        )
