from functools import wraps

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from accounts.models import UserRole


def _redirect_for_role(request: HttpRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return redirect(f"/hyr/?next={request.path}")
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return redirect("/admin/")
    if getattr(user, "role", None) in (UserRole.ADMIN, UserRole.STAFF):
        return redirect("/panel/")
    return redirect("/anetar/")


def staff_required(view_func):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return redirect(f"/hyr/?next={request.path}")
        if getattr(user, "is_locked", False):
            return _redirect_for_role(request)
        # Allow classic Django admin users too (superuser/is_staff),
        # otherwise fall back to our role-based access control.
        if not (getattr(user, "is_superuser", False) or getattr(user, "is_staff", False)):
            if getattr(user, "role", None) not in (UserRole.ADMIN, UserRole.STAFF):
                return _redirect_for_role(request)
        else:
            # Staff users still need to be active to access the panel.
            if not getattr(user, "is_active", True):
                return _redirect_for_role(request)
        return view_func(request, *args, **kwargs)

    return _wrapped

