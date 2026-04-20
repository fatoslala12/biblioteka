"""
URL configuration for smart_library project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.static import serve

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf import settings
from django.conf.urls.static import static

from notifications.views import staff_notification_badge_json

handler403 = "cms.security_views.permission_denied_redirect"
handler404 = "cms.views.page_not_found_view"
handler500 = "cms.views.server_error_view"

urlpatterns = [
    path(
        "admin/login/",
        lambda request: redirect(f"/hyr/?next={request.GET.get('next', '/admin/')}"),
    ),
    path("admin/logout/", lambda request: redirect("/")),
    path("_staff-notif-badge/", staff_notification_badge_json, name="staff_notification_badge_json"),
    path('admin/', admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/", include("smart_library.api_urls")),
    path("", include("cms.urls")),
]

# Serve uploaded media files in both dev and single-container production.
# `django.conf.urls.static.static()` returns [] when DEBUG=False, so we add
# an explicit route to keep admin-uploaded files reachable in production.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.MEDIA_URL:
    media_prefix = settings.MEDIA_URL.lstrip("/")
    urlpatterns += [
        re_path(rf"^{media_prefix}(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
