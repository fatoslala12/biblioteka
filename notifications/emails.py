from __future__ import annotations

import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

LIBRARY_NAME = "Smart Library • Biblioteka Kamëz"


def _absolute_url(path: str) -> str:
    """Kthen një URL absolute duke përdorur PUBLIC_BASE_URL nëse është vendosur."""
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip()
    if not base:
        return path
    normalized = base if base.endswith("/") else f"{base}/"
    relative = path[1:] if path.startswith("/") else path
    return urljoin(normalized, relative)


def _resolve_email(user) -> str:
    return ((getattr(user, "email", "") or "")).strip()


def _authors_label(book) -> str:
    if not book:
        return ""
    try:
        names = [a.name for a in book.authors.all() if getattr(a, "name", "")]
    except Exception:
        names = []
    return ", ".join(names)


def _cover_url(book) -> str:
    if not book:
        return ""
    try:
        cover = getattr(book, "cover_image", None)
        if cover and getattr(cover, "url", ""):
            return _absolute_url(cover.url)
    except Exception:
        pass
    return ""


def _fmt_date(value) -> str:
    if not value:
        return "—"
    try:
        return value.strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _fmt_datetime(value) -> str:
    if not value:
        return "—"
    try:
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


# Konfigurimi i secilit event: subjekti, titulli, hyrja, emoji-t, ngjyra e badge-it.
_EVENT_CONFIG = {
    "approved": {
        "subject": "Rezervimi u pranua",
        "title": "🎉 Rezervimi juaj u pranua",
        "intro": (
            "Kërkesa juaj për rezervim u aprovua nga stafi i bibliotekës. "
            "Më poshtë gjeni detajet e rezervimit tuaj."
        ),
        "badge_text": "✅ Pranuar",
        "badge_bg": "#dcfce7",
        "badge_color": "#166534",
        "cta_text": "Shiko rezervimet e mia",
        "note": "Paraqituni në bibliotekë me kartën e anëtarit brenda afatit të marrjes.",
    },
    "ready": {
        "subject": "Libri është gati për tërheqje",
        "title": "📚 Libri juaj është gati për tërheqje",
        "intro": (
            "Titulli i mëposhtëm është gati për t'u tërhequr në bibliotekë. "
            "Ju lutemi paraqituni brenda afatit të shënuar."
        ),
        "badge_text": "📦 Gati për tërheqje",
        "badge_bg": "#ccfbf1",
        "badge_color": "#115e59",
        "cta_text": "Shiko detajet",
        "note": "Shko në bibliotekë me kartën e anëtarit për ta tërhequr librin para skadimit.",
    },
    "rejected": {
        "subject": "Kërkesa për rezervim nuk u pranua",
        "title": "ℹ️ Kërkesa juaj nuk u pranua",
        "intro": (
            "Na vjen keq, por kërkesa juaj për rezervim nuk mund të pranohej për momentin. "
            "Më poshtë gjeni detajet."
        ),
        "badge_text": "✖ Refuzuar",
        "badge_bg": "#fee2e2",
        "badge_color": "#991b1b",
        "cta_text": "Provo një titull tjetër",
        "note": "Mund të provoni sërish me data të tjera ose një titull tjetër të disponueshëm.",
    },
}


def send_reservation_email(
    user,
    *,
    event: str,
    book=None,
    book_title: str = "",
    pickup_date=None,
    return_date=None,
    expires_at=None,
    decision_reason: str = "",
    cta_url: str = "/anetar/#member-reservations",
) -> bool:
    """Dërgon një email me dizajn për ngjarjet e rezervimit (pranim / gati / refuzim).

    Nuk hedh asnjë përjashtim jashtë funksionit; dështimet regjistrohen në log.
    """
    try:
        cfg = _EVENT_CONFIG.get(event)
        if not cfg:
            return False
        email = _resolve_email(user)
        if not email:
            return False

        title_book = (getattr(book, "title", "") or book_title or "Libri").strip()
        member_name = (getattr(user, "get_full_name", lambda: "")() or "").strip()
        if not member_name:
            member_name = (getattr(user, "first_name", "") or getattr(user, "username", "") or "Anëtar").strip()

        ctx = {
            "library_name": LIBRARY_NAME,
            "subject": cfg["subject"],
            "title": cfg["title"],
            "intro": cfg["intro"],
            "note": cfg["note"],
            "badge_text": cfg["badge_text"],
            "badge_bg": cfg["badge_bg"],
            "badge_color": cfg["badge_color"],
            "member_name": member_name,
            "book_title": title_book,
            "authors": _authors_label(book),
            "cover_url": _cover_url(book),
            "publication_year": getattr(book, "publication_year", None),
            "pickup_date": _fmt_date(pickup_date),
            "return_date": _fmt_date(return_date),
            "expires_at": _fmt_datetime(expires_at) if expires_at else "",
            "has_pickup": bool(pickup_date),
            "has_return": bool(return_date),
            "has_expiry": bool(expires_at),
            "decision_reason": (decision_reason or "").strip(),
            "cta_text": cfg["cta_text"],
            "cta_url": _absolute_url(cta_url),
        }

        html_body = render_to_string("emails/reservation_notification.html", ctx)

        text_lines = [
            f"Përshëndetje {member_name},",
            "",
            cfg["intro"],
            "",
            f"Titulli: {title_book}",
        ]
        if ctx["authors"]:
            text_lines.append(f"Autori: {ctx['authors']}")
        if event in ("approved", "rejected"):
            text_lines.append(f"Data e marrjes: {ctx['pickup_date']}")
            text_lines.append(f"Data e dorëzimit: {ctx['return_date']}")
        if event == "ready" and ctx["expires_at"]:
            text_lines.append(f"Afati për tërheqje: {ctx['expires_at']}")
        if ctx["decision_reason"]:
            text_lines.append(f"Arsye: {ctx['decision_reason']}")
        text_lines += ["", cfg["note"], "", LIBRARY_NAME]
        text_body = "\n".join(text_lines)

        mail = EmailMultiAlternatives(
            subject=f"{cfg['subject']} — {title_book}",
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost"),
            to=[email],
        )
        mail.attach_alternative(html_body, "text/html")
        mail.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Dërgimi i email-it të rezervimit dështoi (event=%s)", event)
        return False
