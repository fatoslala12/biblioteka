from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import MemberProfile, UserRole
from catalog.models import Author, Book, Copy, CopyStatus, Genre, Publisher, Tag
from circulation.models import Hold, HoldStatus, Loan, LoanStatus, Reservation, ReservationStatus
from circulation.models import ReservationRequest, ReservationRequestStatus
from cms.forms import ContactForm
from cms.models import Announcement, Event, WeeklyBook


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _static_img_dir() -> Path:
    return Path(settings.BASE_DIR) / "static" / "img"


def _first_existing_img_path(candidates: list[str], fallback: str) -> str:
    """Kthen rrugën relative `img/...` për static; përdor skedarin e parë që ekziston në disk."""
    img_dir = _static_img_dir()
    for rel in candidates:
        tail = rel[4:] if rel.startswith("img/") else rel
        if (img_dir / tail).is_file():
            return f"img/{tail}"
    fb = fallback[4:] if fallback.startswith("img/") else fallback
    return f"img/{fb}"


def _home_gallery_entries():
    """Preferon fotot e personalizuara të bibliotekës; bie te thumbs klasike si fallback."""
    gallery_sources = [
        (
            "Salla e leximit",
            [
                "img/home-gallery/biblioteka10.jpg",
                "img/home-gallery/biblioteka10.jpeg",
                "img/home-gallery/biblioteka10.png",
            ],
        ),
        (
            "Pamje panoramike",
            [
                "img/home-gallery/biblioteka9.jpg",
                "img/home-gallery/biblioteka9.jpeg",
                "img/home-gallery/biblioteka9.png",
            ],
        ),
        (
            "Raftet e librave",
            [
                "img/home-gallery/biblioteka6.jpg",
                "img/home-gallery/biblioteka6.jpeg",
                "img/home-gallery/biblioteka6.png",
            ],
        ),
        (
            "Zona e aktiviteteve",
            [
                "img/home-gallery/biblioteka5.jpg",
                "img/home-gallery/biblioteka5.jpeg",
                "img/home-gallery/biblioteka5.png",
            ],
        ),
        (
            "Këndi i studimit",
            [
                "img/home-gallery/biblioteka4.jpg",
                "img/home-gallery/biblioteka4.jpeg",
                "img/home-gallery/biblioteka4.png",
            ],
        ),
    ]
    out = []
    for idx, (caption, custom_candidates) in enumerate(gallery_sources, start=1):
        fallback_candidates = [
            f"img/home-gallery/{idx}_thumb.webp",
            f"img/home-gallery/{idx}_thumb.jpg",
            f"img/home-gallery/{idx}.webp",
            f"img/home-gallery/{idx}.jpg",
            f"img/home-gallery/{idx}.jpeg",
            f"img/home-gallery/{idx}.png",
        ]
        path = _first_existing_img_path(
            [*custom_candidates, *fallback_candidates],
            f"img/home-gallery/{idx}.jpg",
        )
        out.append({"path": path, "caption": caption})
    return out


def _hero_library_static_path() -> str:
    return _first_existing_img_path(
        [
            "img/kamez-library_thumb.webp",
            "img/kamez-library_thumb.jpg",
            "img/kamez-library.webp",
            "img/kamez-library.jpg",
            "img/kamez-library.png",
        ],
        "img/kamez-library.png",
    )


def healthz(request):
    response = HttpResponse("ok", content_type="text/plain; charset=utf-8")
    # Tiny cache window keeps the endpoint cheap for frequent probes.
    response["Cache-Control"] = "public, max-age=30, stale-while-revalidate=30"
    return response


def home(request):
    books_count = Book.objects.filter(is_deleted=False).count()
    copies_total = Copy.objects.filter(is_deleted=False).count()
    copies_available = Copy.objects.filter(is_deleted=False, status=CopyStatus.AVAILABLE).count()
    copies_on_loan = Copy.objects.filter(is_deleted=False, status=CopyStatus.ON_LOAN).count()
    copies_on_hold = Copy.objects.filter(is_deleted=False, status=CopyStatus.ON_HOLD).count()
    reservations_active = Reservation.objects.filter(status=ReservationStatus.APPROVED, loan__isnull=True).count()
    authors_count = Author.objects.count()
    publishers_count = Publisher.objects.count()
    genres_count = Genre.objects.count()
    tags_count = Tag.objects.count()
    members_count = MemberProfile.objects.count()

    now = timezone.now()
    active_loans = Loan.objects.filter(status=LoanStatus.ACTIVE).count()
    overdue_loans = Loan.objects.filter(status=LoanStatus.ACTIVE, due_at__lt=now).count()
    holds_waiting = Hold.objects.filter(status=HoldStatus.WAITING).count()
    holds_ready = Hold.objects.filter(status=HoldStatus.READY_FOR_PICKUP).count()

    announcements_qs = Announcement.objects.filter(is_published=True, published_at__lte=now).order_by("-published_at")[:4]
    announcements_data = [
        {
            "id": a.id,
            "detail_url": reverse("cms:announcement_detail", kwargs={"pk": a.id}),
            "title": a.title,
            "date": a.published_at.strftime("%d/%m/%Y"),
            "time": a.published_at.strftime("%H:%M"),
            "excerpt": a.excerpt,
            "badge": a.badge or "Info",
            "image_url": (a.image.url if a.image else ""),
        }
        for a in announcements_qs
    ]
    home_events_qs = Event.objects.filter(is_published=True, published_at__lte=now).order_by("-published_at")[:3]
    home_events = [
        {
            "id": e.id,
            "detail_url": reverse("cms:event_detail", kwargs={"pk": e.id}),
            "title": e.title,
            "date": e.published_at.strftime("%d/%m/%Y"),
            "time": (e.starts_at.strftime("%H:%M") if e.starts_at else e.published_at.strftime("%H:%M")),
            "excerpt": e.excerpt,
            "badge": e.badge or "Event",
            "image_url": (e.image.url if e.image else ""),
        }
        for e in home_events_qs
    ]
    featured_base_qs = (
        Book.objects.filter(is_deleted=False)
        .annotate(
            available_copies=Count(
                "copies",
                filter=Q(copies__status=CopyStatus.AVAILABLE, copies__is_deleted=False),
                distinct=True,
            )
        )
        .order_by("-available_copies", "-created_at")
    )
    featured = list(featured_base_qs.filter(is_recommended=True)[:6])
    if not featured:
        featured = list(featured_base_qs[:6])
    curated_book = (
        WeeklyBook.objects.filter(is_published=True, published_at__lte=now, show_on_home=True)
        .order_by("-published_at")
        .first()
    )
    fallback_book = featured[0] if featured else None
    if curated_book:
        detail_wb = reverse("cms:weekly_book_detail", kwargs={"pk": curated_book.id})
        book_of_week = {
            "title": curated_book.title,
            "author": curated_book.author,
            "excerpt": curated_book.excerpt,
            "date": curated_book.published_at.strftime("%d/%m/%Y"),
            "image_url": (curated_book.image.url if curated_book.image else ""),
            "detail_url": detail_wb,
            "url": (curated_book.cta_url or "").strip() or detail_wb,
            "cta_label": (curated_book.cta_label or "").strip() or "Shiko më shumë",
            "badge": "Libri i javës",
        }
    elif fallback_book:
        detail_fb = reverse("cms:book_detail", kwargs={"pk": fallback_book.id})
        book_of_week = {
            "title": fallback_book.title,
            "author": ", ".join(a.name for a in fallback_book.authors.all()) or "Titull i rekomanduar",
            "excerpt": "",
            "date": now.strftime("%d/%m/%Y"),
            "image_url": f"https://covers.openlibrary.org/b/isbn/{fallback_book.isbn}-M.jpg?default=false",
            "detail_url": detail_fb,
            "url": detail_fb,
            "cta_label": "Shiko më shumë",
            "badge": "Sugjerim",
        }
    else:
        book_of_week = None
    top_announcement = announcements_data[0] if announcements_data else None
    today_event = home_events[0] if home_events else None

    recent = Book.objects.filter(is_deleted=False).order_by("-created_at")[:6]

    top_publishers = (
        Publisher.objects.annotate(book_count=Count("books", filter=Q(books__is_deleted=False)))
        .filter(book_count__gt=0)
        .order_by("-book_count", "name")[:5]
    )
    home_gallery = _home_gallery_entries()
    hero_library_image = _hero_library_static_path()
    return render(
        request,
        "cms/home.html",
        {
            "home_gallery": home_gallery,
            "hero_library_image": hero_library_image,
            "top_publishers": top_publishers,
            "books_count": books_count,
            "copies_total": copies_total,
            "copies_available": copies_available,
            "copies_on_loan": copies_on_loan,
            "copies_on_hold": copies_on_hold,
            "reservations_active": reservations_active,
            "authors_count": authors_count,
            "publishers_count": publishers_count,
            "genres_count": genres_count,
            "tags_count": tags_count,
            "members_count": members_count,
            "active_loans": active_loans,
            "overdue_loans": overdue_loans,
            "holds_waiting": holds_waiting,
            "holds_ready": holds_ready,
            "featured": featured,
            "recent": recent,
            "announcements": announcements_data,
            "home_events": home_events,
            "book_of_week": book_of_week,
            "top_announcement": top_announcement,
            "today_event": today_event,
        },
    )


def catalog(request):
    q = (request.GET.get("q") or "").strip()
    genre_id = (request.GET.get("genre") or "").strip()
    language = (request.GET.get("language") or "").strip()
    year = (request.GET.get("year") or "").strip()
    available_only = (request.GET.get("available") or "").strip() == "1"

    qs = (
        Book.objects.filter(is_deleted=False)
        .select_related("publisher")
        .prefetch_related("authors", "genres", "tags")
        .annotate(
            total_copies=Count("copies", filter=Q(copies__is_deleted=False), distinct=True),
            available_copies=Count(
                "copies",
                filter=Q(copies__status=CopyStatus.AVAILABLE, copies__is_deleted=False),
                distinct=True,
            ),
        )
        .order_by("title")
    )

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(isbn__icontains=q)
            | Q(authors__name__icontains=q)
            | Q(publisher__name__icontains=q)
            | Q(tags__name__icontains=q)
        ).distinct()

    if genre_id.isdigit():
        qs = qs.filter(genres__id=int(genre_id)).distinct()

    if language:
        qs = qs.filter(language__icontains=language)

    if year.isdigit():
        qs = qs.filter(publication_year=int(year))

    if available_only:
        qs = qs.filter(available_copies__gt=0)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    genres = Genre.objects.order_by("name")

    ctx = {
        "q": q,
        "genre_id": genre_id,
        "language": language,
        "year": year,
        "available_only": available_only,
        "genres": genres,
        "page_obj": page_obj,
    }
    if _is_ajax(request):
        html = render_to_string("cms/_catalog_results.html", ctx, request=request)
        return JsonResponse({"html": html, "count": page_obj.paginator.count, "title": "Katalog — Smart Library"})
    return render(request, "cms/catalog.html", ctx)


def book_detail(request, pk: int):
    book = get_object_or_404(
        Book.objects.filter(is_deleted=False)
        .select_related("publisher")
        .prefetch_related("authors", "genres", "tags", "copies"),
        pk=pk,
    )
    copies = book.copies.filter(is_deleted=False)
    counts = {
        "total": copies.count(),
        "available": copies.filter(status=CopyStatus.AVAILABLE).count(),
        "on_loan": copies.filter(status=CopyStatus.ON_LOAN).count(),
        "on_hold": copies.filter(status=CopyStatus.ON_HOLD).count(),
        "lost": copies.filter(status=CopyStatus.LOST).count(),
        "damaged": copies.filter(status=CopyStatus.DAMAGED).count(),
    }

    pending_request = False
    approved_request = False
    if getattr(request, "user", None) and request.user.is_authenticated and getattr(request.user, "role", None) == UserRole.MEMBER:
        member_profile = getattr(request.user, "member_profile", None)
        if member_profile is not None:
            pending_request = ReservationRequest.objects.filter(
                member=member_profile, book=book, status=ReservationRequestStatus.PENDING
            ).exists()
            approved_request = ReservationRequest.objects.filter(
                member=member_profile, book=book, status=ReservationRequestStatus.APPROVED
            ).exists()
    return render(
        request,
        "cms/book_detail.html",
        {
            "book": book,
            "counts": counts,
            "pending_request": pending_request,
            "approved_request": approved_request,
        },
    )


def about(request):
    return render(request, "cms/about.html")


def rules(request):
    return render(request, "cms/rules.html")


def hours(request):
    return render(request, "cms/hours.html")


def announcements(request):
    now = timezone.now()
    qs = Announcement.objects.filter(is_published=True, published_at__lte=now).order_by("-published_at")
    items = [
        {
            "title": a.title,
            "date": a.published_at.strftime("%d/%m/%Y"),
            "excerpt": a.excerpt,
            "badge": a.badge or "Info",
            "image_url": (a.image.url if a.image else ""),
        }
        for a in qs
    ]
    ctx = {
        "title": "Njoftime",
        "subtitle": "Përditësime, rregulla dhe informacione për bibliotekën.",
        "items": items,
        "is_announcements_page": True,
    }
    if _is_ajax(request):
        html = render_to_string("cms/_section_list_content.html", ctx, request=request)
        return JsonResponse({"html": html, "title": "Njoftime — Smart Library"})
    return render(request, "cms/section_list.html", ctx)


def events(request):
    now = timezone.now()
    qs = Event.objects.filter(is_published=True, published_at__lte=now).order_by("-published_at")
    items = []
    for e in qs:
        event_dt = e.starts_at or e.published_at
        items.append(
            {
                "title": e.title,
                "date": e.published_at.strftime("%d/%m/%Y"),
                "event_date": event_dt.strftime("%d/%m/%Y"),
                "location": e.location or "Biblioteka Kamëz",
                "excerpt": e.excerpt,
                "badge": e.badge or "Event",
                "image_url": (e.image.url if e.image else ""),
            }
        )
    ctx = {
        "title": "Evente",
        "subtitle": "Aktivitete të bibliotekës (workshop-e, klube leximi, prezantime).",
        "items": items,
        "is_events_page": True,
    }
    if _is_ajax(request):
        html = render_to_string("cms/_section_list_content.html", ctx, request=request)
        return JsonResponse({"html": html, "title": "Evente — Smart Library"})
    return render(request, "cms/section_list.html", ctx)


def videos(request):
    now = timezone.now()
    qs = WeeklyBook.objects.filter(is_published=True, published_at__lte=now).order_by("-published_at")
    items = []
    for b in qs:
        items.append(
            {
                "title": b.title,
                "date": b.published_at.strftime("%d/%m/%Y"),
                "excerpt": b.excerpt,
                "badge": "Libri i javës",
                "url": (b.cta_url or "").strip(),
                "image_url": (b.image.url if b.image else ""),
                "author": b.author,
                "cta_label": (b.cta_label or "").strip() or "Shiko më shumë",
            }
        )
    ctx = {
        "title": "Libri i javës",
        "subtitle": "Zgjedhjet javore me përshkrim, kopertinë dhe detaje nga paneli i admin.",
        "items": items,
        "is_books_page": True,
    }
    if _is_ajax(request):
        html = render_to_string("cms/_section_list_content.html", ctx, request=request)
        return JsonResponse({"html": html, "title": "Libri i javës — Smart Library"})
    return render(request, "cms/section_list.html", ctx)


def _published_cms_qs(model_cls):
    now = timezone.now()
    return model_cls.objects.filter(is_published=True, published_at__lte=now)


def announcement_detail(request, pk):
    obj = get_object_or_404(_published_cms_qs(Announcement), pk=pk)
    body = (obj.content or obj.excerpt or "").strip()
    return render(
        request,
        "cms/publishable_detail.html",
        {
            "page_title": obj.title,
            "badge": obj.badge or "Info",
            "subtitle": "",
            "meta_line": obj.published_at.strftime("%d/%m/%Y %H:%M"),
            "image_url": (obj.image.url if obj.image else ""),
            "body": body,
            "back_url": reverse("cms:announcements"),
            "back_label": "← Kthehu te njoftimet",
            "cta_url": "",
            "cta_label": "",
        },
    )


def event_detail(request, pk):
    obj = get_object_or_404(_published_cms_qs(Event), pk=pk)
    body = (obj.content or obj.excerpt or "").strip()
    starts = obj.starts_at.strftime("%d/%m/%Y %H:%M") if obj.starts_at else ""
    ends = obj.ends_at.strftime("%d/%m/%Y %H:%M") if obj.ends_at else ""
    meta_bits = [obj.published_at.strftime("%d/%m/%Y")]
    if starts:
        meta_bits.append(f"Fillimi: {starts}")
    if ends:
        meta_bits.append(f"Mbarimi: {ends}")
    return render(
        request,
        "cms/publishable_detail.html",
        {
            "page_title": obj.title,
            "badge": obj.badge or "Event",
            "subtitle": obj.location or "",
            "meta_line": " · ".join(meta_bits),
            "image_url": (obj.image.url if obj.image else ""),
            "body": body,
            "back_url": reverse("cms:events"),
            "back_label": "← Kthehu te eventet",
            "cta_url": "",
            "cta_label": "",
        },
    )


def weekly_book_detail(request, pk):
    obj = get_object_or_404(_published_cms_qs(WeeklyBook), pk=pk)
    body = (obj.content or obj.excerpt or "").strip()
    cta_url = (obj.cta_url or "").strip()
    cta_label = (obj.cta_label or "").strip() or "Shiko më shumë"
    return render(
        request,
        "cms/publishable_detail.html",
        {
            "page_title": obj.title,
            "badge": "Libri i javës",
            "subtitle": (obj.author or "").strip(),
            "meta_line": obj.published_at.strftime("%d/%m/%Y"),
            "image_url": (obj.image.url if obj.image else ""),
            "body": body,
            "back_url": reverse("cms:weekly_books"),
            "back_label": "← Kthehu te librat e javës",
            "cta_url": cta_url,
            "cta_label": cta_label,
        },
    )


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            from cms.models import ContactMessage

            msg_obj = ContactMessage.objects.create(
                name=data["name"],
                email=data["email"],
                subject=data["subject"],
                message=data["message"],
            )
            # Modern HTML email for admin notification
            subject = f"[Smart Library • Biblioteka Kamëz] Mesazh i ri — {data['subject']}".strip()
            text_body = (
                "Mesazh i ri nga formulari i kontaktit (Smart Library / Biblioteka Kamëz)\n\n"
                f"Emri: {data['name']}\n"
                f"Email: {data['email']}\n"
                f"Subjekti: {data['subject']}\n\n"
                f"Mesazhi:\n{data['message']}\n"
            )
            html_body = render_to_string(
                "cms/emails/contact_message_admin.html",
                {
                    "name": data["name"],
                    "email": data["email"],
                    "subject": data["subject"],
                    "message": data["message"],
                    "created_at": msg_obj.created_at,
                    "admin_url": f"/admin/cms/contactmessage/{msg_obj.id}/change/",
                },
                request=request,
            )
            try:
                email_msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=None,
                    to=["fatoslala12@gmail.com"],
                    reply_to=[data["email"]],
                )
                email_msg.attach_alternative(html_body, "text/html")
                email_msg.send(fail_silently=False)
            except Exception:
                # If SMTP isn't configured or fails, still keep the contact message saved.
                pass
            messages.success(request, "Mesazhi u dërgua. Faleminderit!")
            return redirect("cms:contact")
    else:
        form = ContactForm()

    return render(request, "cms/contact.html", {"form": form})


def page_not_found_view(request, exception=None):
    return render(request, "404.html", status=404)


def server_error_view(request):
    return render(request, "500.html", status=500)


def redirect_anetar_inapp_notifications_legacy(request):
    suffix = ("?" + request.GET.urlencode()) if request.GET else ""
    return redirect(f"/anetar/notifications/{suffix}")


def redirect_panel_inapp_notifications_legacy(request):
    suffix = ("?" + request.GET.urlencode()) if request.GET else ""
    return redirect(f"/panel/notifications/{suffix}")
