from django.urls import path

from . import views
from . import auth_views
from . import panel_views

app_name = "cms"

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("books/<int:pk>/", views.book_detail, name="book_detail"),
    path("njoftime/", views.announcements, name="announcements"),
    path("evente/", views.events, name="events"),
    path("video/", views.videos, name="videos"),
    path("rreth-nesh/", views.about, name="about"),
    path("rregullore/", views.rules, name="rules"),
    path("orar/", views.hours, name="hours"),
    path("kontakt/", views.contact, name="contact"),

    # Auth / Member portal
    path("hyr/", auth_views.sign_in, name="sign_in"),
    path("regjistrohu/", auth_views.sign_up, name="sign_up"),
    path("dil/", auth_views.sign_out, name="sign_out"),
    path("anetar/", auth_views.member_portal, name="member_portal"),
    path("anetar/rezervo/<int:book_id>/", auth_views.member_place_hold, name="member_place_hold"),
    path("anetar/profil/", auth_views.member_update_profile, name="member_update_profile"),
    path("anetar/fjalekalim/", auth_views.member_change_password, name="member_change_password"),
    path("anetar/kerkesa/<int:request_id>/anulo/", auth_views.member_cancel_request, name="member_cancel_request"),

    # Staff portal (beautiful UI for inventory)
    path("panel/", panel_views.dashboard, name="panel_dashboard"),
    path("panel/books/", panel_views.books_list, name="panel_books_list"),
    path("panel/books/new/", panel_views.book_new, name="panel_book_new"),
    path("panel/books/<int:pk>/", panel_views.book_manage, name="panel_book_manage"),
    path("panel/books/<int:pk>/edit/", panel_views.book_edit, name="panel_book_edit"),
    path("panel/books/<int:book_pk>/copies/new/", panel_views.copy_new, name="panel_copy_new"),
    path("panel/copies/<int:pk>/edit/", panel_views.copy_edit, name="panel_copy_edit"),
    path("panel/members/<int:pk>/", panel_views.member_profile_portal, name="panel_member_profile"),
]

