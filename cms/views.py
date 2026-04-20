from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from urllib.parse import urlparse

from accounts.models import MemberProfile, UserRole
from catalog.models import Author, Book, Copy, CopyStatus, Genre, Publisher, Tag
from circulation.models import Hold, HoldStatus, Loan, LoanStatus
from circulation.models import ReservationRequest, ReservationRequestStatus
from cms.forms import ContactForm
from cms.models import Announcement, Event, Video


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
    """Preferon *_thumb.webp / *_thumb.jpg për ngarkim më të shpejtë (krijo me scripts/build_image_thumbs.py)."""
    captions = ["Salla e leximit", "Hapësira", "Katalogu", "Evente"]
    out = []
    for i, caption in enumerate(captions, start=1):
        stem = str(i)
        path = _first_existing_img_path(
            [
                f"img/home-gallery/{stem}_thumb.webp",
                f"img/home-gallery/{stem}_thumb.jpg",
                f"img/home-gallery/{stem}.webp",
                f"img/home-gallery/{stem}.jpg",
                f"img/home-gallery/{stem}.jpeg",
                f"img/home-gallery/{stem}.png",
            ],
            f"img/home-gallery/{stem}.jpg",
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
            "title": e.title,
            "date": e.published_at.strftime("%d/%m/%Y"),
            "time": (e.starts_at.strftime("%H:%M") if e.starts_at else e.published_at.strftime("%H:%M")),
            "excerpt": e.excerpt,
            "badge": e.badge or "Event",
            "image_url": (e.image.url if e.image else ""),
        }
        for e in home_events_qs
    ]
    home_videos_qs = Video.objects.filter(is_published=True, published_at__lte=now, show_on_home=True).order_by(
        "-published_at"
    )[:3]
    home_videos = [
        {
            "title": v.title,
            "date": v.published_at.strftime("%d/%m/%Y"),
            "time": v.published_at.strftime("%H:%M"),
            "excerpt": v.excerpt,
            "badge": v.badge or "Video",
            "url": v.video_url,
            "image_url": (v.image.url if getattr(v, "image", None) else ""),
        }
        for v in home_videos_qs
    ]

    featured = (
        Book.objects.filter(is_deleted=False)
        .annotate(
            available_copies=Count(
                "copies",
                filter=Q(copies__status=CopyStatus.AVAILABLE, copies__is_deleted=False),
                distinct=True,
            )
        )
        .order_by("-available_copies", "-created_at")[:6]
    )
    book_of_week = featured[0] if featured else None
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
            "home_videos": home_videos,
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
    qs = Video.objects.filter(is_published=True, published_at__lte=now).order_by("-published_at")
    items = []
    for v in qs:
        host = ""
        if v.video_url:
            try:
                host = (urlparse(v.video_url).netloc or "").replace("www.", "")
            except Exception:
                host = ""
        duration = f" • Kohëzgjatja: {v.duration}" if v.duration else ""
        items.append(
            {
                "title": v.title,
                "date": v.published_at.strftime("%d/%m/%Y"),
                "excerpt": (v.excerpt or "") + duration,
                "badge": v.badge or "Video",
                "url": v.video_url,
                "source_host": host,
            }
        )
    ctx = {
        "title": "Video",
        "subtitle": "Udhëzues dhe materiale informative (placeholder për modul video).",
        "items": items,
        "is_videos_page": True,
    }
    if _is_ajax(request):
        html = render_to_string("cms/_section_list_content.html", ctx, request=request)
        return JsonResponse({"html": html, "title": "Video — Smart Library"})
    return render(request, "cms/section_list.html", ctx)


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
