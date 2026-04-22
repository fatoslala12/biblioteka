from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render

from accounts.models import UserRole


def permission_denied_redirect(request: HttpRequest, exception=None) -> HttpResponse:
    user = getattr(request, "user", None)
    path = request.get_full_path() or "/"

    if not user or not user.is_authenticated:
        return redirect(f"/hyr/?next={path}")

    messages.warning(request, "Nuk keni akses në këtë faqe.")

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return redirect("/admin/")
    if getattr(user, "role", None) in (UserRole.ADMIN, UserRole.STAFF):
        return redirect("/panel/")
    return redirect("/anetar/")


def csrf_failure_view(request: HttpRequest, reason: str = "") -> HttpResponse:
    return render(
        request,
        "403_csrf.html",
        {
            "reason": reason or "",
        },
        status=403,
    )
