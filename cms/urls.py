from django.urls import path
from django.views.generic import RedirectView

from . import views
from . import auth_views
from . import panel_views

app_name = "cms"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("books/<int:pk>/", views.book_detail, name="book_detail"),
    path("njoftime/<int:pk>/", views.announcement_detail, name="announcement_detail"),
    path("njoftime/", views.announcements, name="announcements"),
    path("evente/<int:pk>/", views.event_detail, name="event_detail"),
    path("evente/", views.events, name="events"),
    path("libri-i-javes/<int:pk>/", views.weekly_book_detail, name="weekly_book_detail"),
    path("libri-i-javes/", views.videos, name="weekly_books"),
    path("video/", RedirectView.as_view(url="/libri-i-javes/", permanent=False), name="videos_redirect"),
    path("rreth-nesh/", views.about, name="about"),
    path("rregullore/", views.rules, name="rules"),
    path("orar/", views.hours, name="hours"),
    path("kontakt/", views.contact, name="contact"),

    # Auth / Member portal
    path("hyr/", auth_views.sign_in, name="sign_in"),
    path("harrova-fjalekalimin/", auth_views.forgot_password, name="forgot_password"),
    path("rivendosje-derguar/", auth_views.password_reset_sent, name="password_reset_sent"),
    path("rivendosje/<uidb64>/<token>/", auth_views.password_reset_confirm, name="password_reset_confirm"),
    path("rivendosje-u-krye/", auth_views.password_reset_done, name="password_reset_done"),
    path("regjistrohu/", auth_views.sign_up, name="sign_up"),
    path("dil/", auth_views.sign_out, name="sign_out"),
    path("anetar/", auth_views.member_portal, name="member_portal"),
    path("anetar/rezervo/<int:book_id>/", auth_views.member_place_hold, name="member_place_hold"),
    path("anetar/profil/", auth_views.member_update_profile, name="member_update_profile"),
    path("anetar/fjalekalim/", auth_views.member_change_password, name="member_change_password"),
    path("anetar/kerkesa/<int:request_id>/anulo/", auth_views.member_cancel_request, name="member_cancel_request"),
    path("anetar/notifications/", auth_views.member_notifications, name="member_notifications"),
    path("anetar/njoftime/", views.redirect_anetar_inapp_notifications_legacy),

    # Staff portal (beautiful UI for inventory)
    path("panel/", panel_views.dashboard, name="panel_dashboard"),
    path("panel/notifications/", panel_views.staff_notifications, name="panel_notifications"),
    path("panel/njoftime/", views.redirect_panel_inapp_notifications_legacy),
    path("panel/books/", panel_views.books_list, name="panel_books_list"),
    path("panel/books/new/", panel_views.book_new, name="panel_book_new"),
    path("panel/books/<int:pk>/", panel_views.book_manage, name="panel_book_manage"),
    path("panel/books/<int:pk>/edit/", panel_views.book_edit, name="panel_book_edit"),
    path("panel/books/<int:book_pk>/copies/new/", panel_views.copy_new, name="panel_copy_new"),
    path("panel/copies/<int:pk>/edit/", panel_views.copy_edit, name="panel_copy_edit"),
    path("panel/members/<int:pk>/", panel_views.member_profile_portal, name="panel_member_profile"),
]

