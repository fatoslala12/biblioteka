from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse

from cms.ops_services import (
    clean_old_backups,
    clear_expired_sessions,
    create_full_backup,
    delete_backup,
    optimize_database,
    prune_old_admin_logs,
    system_settings_context,
    _safe_backup_name,
)


def _staff_ops_guard(user) -> bool:
    return bool(
        user
        and user.is_active
        and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    )


@staff_member_required
def system_settings_view(request):
    if not _staff_ops_guard(request.user):
        messages.error(request, "Nuk keni të drejta për këtë faqe.")
        return redirect("admin:index")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "create_backup":
            result = create_full_backup(request.POST.get("description", ""))
            if result.get("ok"):
                messages.success(
                    request,
                    f"Backup u krijua: {result['filename']} ({result.get('size_human', '')})",
                )
            else:
                messages.error(request, result.get("error") or "Backup-i dështoi.")
        elif action == "clean_backups":
            result = clean_old_backups()
            if result.get("count"):
                messages.success(request, f"U fshinë {result['count']} backup-e të vjetra.")
            else:
                messages.info(request, "Nuk ka backup-e të vjetra për fshirje.")
        elif action == "delete_backup":
            filename = request.POST.get("filename", "")
            result = delete_backup(filename)
            if result.get("ok"):
                messages.success(request, f"U fshi backup-i {filename}.")
            else:
                messages.error(request, result.get("error") or "Fshirja dështoi.")
        elif action == "clear_sessions":
            result = clear_expired_sessions()
            messages.success(request, f"U pastruan {result.get('removed', 0)} sesione të skaduara.")
        elif action == "prune_admin_logs":
            result = prune_old_admin_logs()
            messages.success(
                request,
                f"U fshinë {result.get('removed', 0)} regjistra admin më të vjetër se {result.get('retention_days')} ditë.",
            )
        elif action == "optimize_db":
            result = optimize_database()
            if result.get("ok"):
                messages.success(request, result.get("message") or "Databaza u optimizua.")
            else:
                messages.error(request, result.get("error") or "Optimizimi dështoi.")
        return redirect("admin:system_settings")

    ctx = {
        **admin.site.each_context(request),
        "title": "Settings",
        "opts": {"app_label": "cms", "model_name": "settings", "verbose_name_plural": "Settings"},
        "settings_data": system_settings_context(),
    }
    return render(request, "admin/system_settings.html", ctx)


@staff_member_required
def system_settings_backup_download(request, filename: str):
    if not _staff_ops_guard(request.user):
        raise Http404
    path = _safe_backup_name(filename)
    if not path:
        raise Http404
    response = HttpResponse(path.read_bytes(), content_type="application/gzip")
    response["Content-Disposition"] = f'attachment; filename="{path.name}"'
    return response


def register_admin_ops_urls():
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom = [
            path("settings/", admin.site.admin_view(system_settings_view), name="system_settings"),
            path(
                "settings/backup/<str:filename>/download/",
                admin.site.admin_view(system_settings_backup_download),
                name="system_settings_backup_download",
            ),
        ]
        return custom + original_get_urls()

    admin.site.get_urls = get_urls
