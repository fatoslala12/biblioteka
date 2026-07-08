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
        "note": "Paraqituni në bibliotekë me kartën e identitetit brenda afatit të marrjes.",
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
        "note": "Shko në bibliotekë me kartën e identitetit për ta tërhequr librin para skadimit.",
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
    "loan_active": {
        "subject": "Huazimi filloi",
        "title": "📖 Huazimi juaj u regjistrua",
        "intro": "Libri i mëposhtëm është huazuar në emrin tuaj. Ju lutemi respektoni afatin e kthimit.",
        "badge_text": "📗 Në huazim",
        "badge_bg": "#e0e7ff",
        "badge_color": "#3730a3",
        "cta_text": "Shiko huazimet e mia",
        "note": "Mund të renewoni/ktheni librin duke u paraqitur në bibliotekë.",
    },
    "loan_returned": {
        "subject": "Libri u kthye",
        "title": "✅ Kthimi u regjistrua",
        "intro": "Faleminderit! Libri i mëposhtëm u regjistrua si i kthyer.",
        "badge_text": "✔ I kthyer",
        "badge_bg": "#dcfce7",
        "badge_color": "#166534",
        "cta_text": "Hap portalin",
        "note": "Mund të rezervoni ose huazoni një titull tjetër nga katalogu.",
    },
    "loan_renewed": {
        "subject": "Afati i huazimit u zgjat",
        "title": "🔄 Afati juaj u rinovua",
        "intro": "Afati i kthimit për librin e mëposhtëm u zgjat. Kontrolloni datën e re.",
        "badge_text": "⏳ Afati i ri",
        "badge_bg": "#fef3c7",
        "badge_color": "#92400e",
        "cta_text": "Shiko huazimet",
        "note": "Numri i rinovimeve është i kufizuar sipas rregullave të bibliotekës.",
    },
    "loan_due_tomorrow": {
        "subject": "Kujtesë: nesër është afati i kthimit",
        "title": "⏰ Afati i kthimit është nesër",
        "intro": "Ju kujtojmë që libri i mëposhtëm duhet të kthehet nesër në bibliotekë.",
        "badge_text": "📌 Kujtesë",
        "badge_bg": "#ffedd5",
        "badge_color": "#9a3412",
        "cta_text": "Shiko huazimet",
        "note": "Kthimi me vonesë mund të sjellë gjobë.",
    },
    "fine_created": {
        "subject": "Gjobë e re në llogarinë tuaj",
        "title": "💶 U regjistrua një gjobë",
        "intro": "Në profilin tuaj është regjistruar një gjobë. Ju lutemi shlyeni atë në bibliotekë.",
        "badge_text": "🧾 Gjobë",
        "badge_bg": "#fee2e2",
        "badge_color": "#991b1b",
        "cta_text": "Shiko gjobat",
        "note": "Huazimet/rezervimet mund të bllokohen derisa gjoba të paguhet.",
    },
    "reservation_expired": {
        "subject": "Rezervimi skadoi",
        "title": "⌛ Rezervimi juaj skadoi",
        "intro": "Rezervimi për titullin e mëposhtëm u mbyll automatikisht sepse libri nuk u mor në datën e caktuar.",
        "badge_text": "Skaduar",
        "badge_bg": "#f1f5f9",
        "badge_color": "#475569",
        "cta_text": "Rezervo sërish",
        "note": "Mund të dërgoni një kërkesë të re nga katalogu nëse titulli është ende i interesuar.",
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
    """Dërgon një email me dizajn për ngjarjet e rezervimit / huazimit / gjobës.

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

        # Loan events use return_date as due date label in the shared template.
        show_pickup = bool(pickup_date) and event in ("approved", "rejected")
        show_return = bool(return_date) and event in (
            "approved",
            "rejected",
            "loan_active",
            "loan_renewed",
            "loan_due_tomorrow",
        )
        show_expiry = bool(expires_at) and event == "ready"

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
            "return_date": _fmt_date(return_date) if not hasattr(return_date, "hour") else _fmt_datetime(return_date),
            "expires_at": _fmt_datetime(expires_at) if expires_at else "",
            "has_pickup": show_pickup,
            "has_return": show_return,
            "has_expiry": show_expiry,
            "decision_reason": (decision_reason or "").strip(),
            "cta_text": cfg["cta_text"],
            "cta_url": _absolute_url(cta_url),
        }
        # Prefer datetime formatting for loan due dates.
        if event in ("loan_active", "loan_renewed", "loan_due_tomorrow") and return_date:
            ctx["return_date"] = _fmt_datetime(return_date) if hasattr(return_date, "hour") else _fmt_date(return_date)

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
        if show_pickup:
            text_lines.append(f"Data e marrjes: {ctx['pickup_date']}")
        if show_return:
            label = "Afati i kthimit" if event.startswith("loan_") else "Data e dorëzimit"
            text_lines.append(f"{label}: {ctx['return_date']}")
        if show_expiry and ctx["expires_at"]:
            text_lines.append(f"Afati për tërheqje: {ctx['expires_at']}")
        if ctx["decision_reason"]:
            text_lines.append(f"Detaje: {ctx['decision_reason']}")
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
        logger.exception("Dërgimi i email-it dështoi (event=%s)", event)
        return False
