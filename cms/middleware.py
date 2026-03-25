from django.contrib import messages
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
