import json

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django import forms
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.shortcuts import redirect

from .models import MemberProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    change_list_template = "admin/accounts/user/change_list.html"
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Smart Library", {"fields": ("role", "is_locked", "locked_at", "lock_reason")}),
    )
    list_display = ("user_display", "role", "active_badge", "lock_badge", "last_login_display", "active_toggle_btn", "reset_password_btn")
    list_filter = ()
    search_fields = ("username", "email", "first_name", "last_name")
    actions = None

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("member_profile")
        raw_scope = (request.GET.get("user_scope") or "").strip()
        # Only apply our quick-filter when user_scope is explicitly set.
        # Otherwise, let the default ChangeList filters/search behave normally.
        if not raw_scope:
            return qs
        scope = raw_scope.upper()
        if scope == "ALL":
            return qs
        if scope == "INACTIVE":
            return qs.filter(is_active=False)
        if scope == "ADMIN":
            # Prefer Django permissions flags for admins
            return qs.filter(is_superuser=True)
        if scope == "STAFF":
            return qs.filter(is_staff=True, is_superuser=False)
        if scope == "MEMBER":
            # Members are non-staff users
            return qs.filter(is_staff=False, is_superuser=False, role="MEMBER")
        # Default scope (ACTIVE)
        return qs.filter(is_active=True)

    @admin.display(description="Përdoruesi")
    def user_display(self, obj: User):
        full_name = (obj.get_full_name() or "").strip()
        label = full_name or obj.username
        meta = obj.email or obj.username
        # Use member photo if exists
        mp = getattr(obj, "member_profile", None)
        if mp is not None and getattr(mp, "photo", None):
            avatar = format_html(
                '<img src="{}" style="width:30px;height:30px;border-radius:999px;object-fit:cover;margin-right:8px;border:1px solid rgba(15,23,42,.12);" />',
                mp.photo.url,
            )
        else:
            avatar = format_html(
                '<span style="width:30px;height:30px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;'
                'margin-right:8px;background:rgba(49,145,137,.14);color:#1f5f5a;font-weight:800;font-size:12px;">{}</span>',
                (label[:1] or "U").upper(),
            )
        return format_html(
            '<span style="display:inline-flex;align-items:center;">{}<span><b>{}</b><small style="display:block;opacity:.78;">{}</small></span></span>',
            avatar,
            label,
            meta,
        )

    @admin.display(description="Aktiv")
    def active_badge(self, obj: User):
        if obj.is_active:
            return format_html('<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;color:#fff;background:#319189;font-weight:800;font-size:12px;">Po</span>')
        return format_html('<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;color:#fff;background:#64748b;font-weight:800;font-size:12px;">Jo</span>')

    @admin.display(description="Bllokuar")
    def lock_badge(self, obj: User):
        if obj.is_locked:
            return format_html('<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;color:#fff;background:#e74c3c;font-weight:800;font-size:12px;">Po</span>')
        return format_html('<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;color:#fff;background:#319189;font-weight:800;font-size:12px;">Jo</span>')

    @admin.display(description="Hyrja e fundit")
    def last_login_display(self, obj: User):
        if not obj.last_login:
            return "—"
        return timezone.localtime(obj.last_login).strftime("%d/%m/%Y")

    @admin.display(description="Status")
    def active_toggle_btn(self, obj: User):
        label = "Aktivizo" if not obj.is_active else "Çaktivizo"
        cls = "btn-outline-secondary" if not obj.is_active else "btn-danger"
        return format_html('<a class="btn btn-xs {}" href="/admin/accounts/user/{}/toggle-active/">{}</a>', cls, obj.id, label)

    @admin.display(description="Fjalëkalimi")
    def reset_password_btn(self, obj: User):
        return format_html(
            '<button type="button" class="btn btn-xs btn-primary js-open-pass-modal" data-user-id="{}" data-username="{}">Fjalëkalimi</button>',
            obj.id,
            obj.username,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:user_id>/toggle-active/", self.admin_site.admin_view(self.toggle_active_view), name="accounts_user_toggle_active"),
            path("<int:user_id>/set-password/", self.admin_site.admin_view(self.set_password_api), name="accounts_user_set_password"),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        current_scope = (request.GET.get("user_scope") or "").strip().upper()
        if not current_scope:
            current_scope = "ACTIVE"
        if current_scope not in ("ACTIVE", "INACTIVE", "ADMIN", "STAFF", "MEMBER", "ALL"):
            current_scope = "ACTIVE"
        ctx = {"current_scope": current_scope}
        if extra_context:
            ctx.update(extra_context)
        return super().changelist_view(request, extra_context=ctx)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        messages.info(request, "Përdor butonat Mbyll/Hap dhe Reset për menaxhim.")
        return redirect("/admin/accounts/user/")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def toggle_active_view(self, request, user_id: int):
        obj = User.objects.filter(id=user_id).first()
        if not obj:
            messages.error(request, "Përdoruesi nuk u gjet.")
            return redirect("/admin/accounts/user/")
        if request.user.id == obj.id:
            messages.warning(request, "Nuk mund të çaktivizosh llogarinë tënde.")
            return redirect("/admin/accounts/user/")
        obj.is_active = not obj.is_active
        # Keep lock state consistent with active state.
        obj.is_locked = not obj.is_active
        obj.locked_at = timezone.now() if obj.is_locked else None
        obj.lock_reason = "Çaktivizuar nga admin." if obj.is_locked else ""
        obj.save(update_fields=["is_active", "is_locked", "locked_at", "lock_reason"])
        messages.success(request, f"Përdoruesi {'u çaktivizua' if not obj.is_active else 'u aktivizua'} me sukses.")
        return redirect("/admin/accounts/user/")

    def set_password_api(self, request, user_id: int):
        if request.method != "POST":
            return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
        obj = User.objects.filter(id=user_id).first()
        if not obj:
            return JsonResponse({"ok": False, "error": "Përdoruesi nuk u gjet."}, status=404)
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}
        raw = (payload.get("password") or "").strip()
        new_password = raw or "12345678"
        obj.set_password(new_password)
        obj.save(update_fields=["password"])
        return JsonResponse({"ok": True, "username": obj.username, "password": new_password})

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # If a MEMBER user is created/edited and has no member profile, create one automatically.
        if getattr(obj, "role", None) == "MEMBER" and not hasattr(obj, "member_profile"):
            from .models import MemberProfile

            full_name = (f"{obj.first_name} {obj.last_name}".strip() or obj.username).strip()
            # create a stable member number (simple local strategy)
            member_no = f"M{obj.id:03d}"
            MemberProfile.objects.create(user=obj, member_no=member_no, full_name=full_name)


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    change_list_template = "admin/accounts/memberprofile/change_list.html"
    list_display = (
        "member_display",
        "member_no",
        "member_type",
        "status_badge",
        "phone",
        "national_id",
        "created_at_display",
        "open_profile_btn",
    )
    list_filter = ()
    search_fields = ("member_no", "user__username", "full_name", "phone", "national_id")
    actions = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        scope = (request.GET.get("member_scope") or "ACTIVE").upper()
        if scope == "ALL":
            return qs
        if scope in ("ACTIVE", "SUSPENDED", "BLOCKED"):
            return qs.filter(status=scope)
        return qs.filter(status="ACTIVE")

    @admin.display(description="Anëtari")
    def member_display(self, obj: MemberProfile):
        label = (obj.full_name or "").strip() or obj.member_no
        if getattr(obj, "photo", None):
            avatar = format_html(
                '<img src="{}" style="width:32px;height:32px;border-radius:999px;object-fit:cover;margin-right:8px;" />',
                obj.photo.url,
            )
        else:
            avatar = format_html(
                '<span style="width:32px;height:32px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;'
                'margin-right:8px;background:rgba(49,145,137,.14);color:#1f5f5a;font-weight:800;font-size:12px;">{}</span>',
                (label[:1] or "A").upper(),
            )
        return format_html(
            '<a href="/panel/members/{}/" style="display:inline-flex;align-items:center;"><span>{}</span><span><b>{}</b><small style="display:block;opacity:.78;">{}</small></span></a>',
            obj.id,
            avatar,
            label,
            obj.member_no,
        )

    @admin.display(description="Statusi", ordering="status")
    def status_badge(self, obj: MemberProfile):
        color = {
            "ACTIVE": "#319189",
            "SUSPENDED": "#F39C12",
            "BLOCKED": "#e74c3c",
        }.get(obj.status, "#64748b")
        label = obj.get_status_display()
        return format_html(
            '<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;color:#fff;background:{};font-weight:800;font-size:12px;">{}</span>',
            color,
            label,
        )

    @admin.display(description="Krijuar më", ordering="created_at")
    def created_at_display(self, obj: MemberProfile):
        return obj.created_at.strftime("%d/%m/%Y")

    @admin.display(description="Veprim")
    def open_profile_btn(self, obj: MemberProfile):
        return format_html('<a class="btn btn-xs btn-primary" href="/panel/members/{}/">Hap profilin</a>', obj.id)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Default click on member profile opens the member-style portal view for staff.
        if request.GET.get("admin_edit") == "1":
            return super().change_view(request, object_id, form_url, extra_context)
        return redirect(f"/panel/members/{object_id}/")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("shto-anetar/krijo/", self.admin_site.admin_view(self.quick_create_member_api), name="accounts_memberprofile_quick_create_api"),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        current_scope = (request.GET.get("member_scope") or "ACTIVE").upper()
        if current_scope not in ("ACTIVE", "SUSPENDED", "BLOCKED", "ALL"):
            current_scope = "ACTIVE"
        ctx = {
            "current_scope": current_scope,
            "quick_member_create_url": "/admin/accounts/memberprofile/shto-anetar/krijo/",
        }
        if extra_context:
            ctx.update(extra_context)
        return super().changelist_view(request, extra_context=ctx)

    def quick_create_member_api(self, request):
        if request.method != "POST":
            return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)

        if request.POST:
            payload = request.POST
        else:
            try:
                payload = json.loads((request.body or b"{}").decode("utf-8"))
            except Exception:
                payload = {}

        full_name = (payload.get("full_name") or "").strip()
        national_id = (payload.get("national_id") or "").strip()
        phone = (payload.get("phone") or "").strip()
        address = (payload.get("address") or "").strip()
        place_of_birth = (payload.get("place_of_birth") or "").strip()
        date_of_birth = (payload.get("date_of_birth") or "").strip() or None
        member_type = (payload.get("member_type") or "STANDARD").strip().upper()
        status = (payload.get("status") or "ACTIVE").strip().upper()
        photo = request.FILES.get("photo")

        if not full_name:
            return JsonResponse({"ok": False, "error": "Emri dhe mbiemri është i detyrueshëm."}, status=400)
        if member_type not in ("STANDARD", "STUDENT", "VIP"):
            member_type = "STANDARD"
        if status not in ("ACTIVE", "SUSPENDED", "BLOCKED"):
            status = "ACTIVE"

        try:
            member = MemberProfile.objects.create(
                full_name=full_name,
                national_id=national_id,
                phone=phone,
                address=address,
                place_of_birth=place_of_birth,
                date_of_birth=date_of_birth,
                member_type=member_type,
                status=status,
                photo=photo,
            )
            return JsonResponse(
                {
                    "ok": True,
                    "member_id": member.id,
                    "member_no": member.member_no,
                    "redirect": "/admin/accounts/memberprofile/",
                }
            )
        except Exception as e:
            return JsonResponse({"ok": False, "error": f"Nuk u krijua anëtari. ({e})"}, status=500)


class MemberProfileAdminForm(forms.ModelForm):
    class Meta:
        model = MemberProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # make user optional; it will be auto-created when empty
        self.fields["user"].required = False
        self.fields["user"].help_text = "Nëse e lë bosh, krijohet automatikisht user MEMBER me password 12345678."


MemberProfileAdmin.form = MemberProfileAdminForm
