from django.contrib import messages
from django.conf import settings
from django.shortcuts import render
from django.shortcuts import redirect


class AdminAccessGuardMiddleware:
    """
    If a non-staff authenticated user tries to access /admin/,
    redirect to member portal with a clear message instead of
    showing admin login/error flows.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if path.startswith("/admin/"):
            user = getattr(request, "user", None)
            if user and user.is_authenticated:
                is_staff_like = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
                if not is_staff_like:
                    messages.warning(request, "Nuk keni të drejta për të hyrë në panelin e admin-it.")
                    return redirect("/anetar/")
        return self.get_response(request)


class MaintenanceModeMiddleware:
    """
    Show a friendly maintenance page when MAINTENANCE_MODE is enabled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "MAINTENANCE_MODE", False):
            return self.get_response(request)

        path = request.path or ""
        if (
            path.startswith("/static/")
            or path.startswith("/media/")
            or path.startswith("/healthz/")
        ):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False):
            return self.get_response(request)

        return render(request, "503.html", status=503)
