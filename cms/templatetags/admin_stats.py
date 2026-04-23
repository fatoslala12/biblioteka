from calendar import month_abbr
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django import template
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone

from accounts.models import MemberProfile
from catalog.models import Author, Book, Copy, CopyStatus, Genre, Publisher
from circulation.models import Loan, LoanStatus, Reservation, ReservationRequest, ReservationRequestStatus
from fines.models import Fine, FineStatus

register = template.Library()


def _severity_rank(level: str) -> int:
    return {"NORMAL": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get((level or "").upper(), 0)


def _metric_severity(value: Decimal, threshold: Decimal) -> str:
    if threshold <= 0:
        return "NORMAL"
    if value >= threshold * Decimal("2.0"):
        return "CRITICAL"
    if value >= threshold:
        return "HIGH"
    if value >= threshold * Decimal("0.75"):
        return "MEDIUM"
    return "NORMAL"


def _sparkline(points: list[int], labels: list[str]) -> list[dict]:
    if not points:
        return []
    mx = max(points) or 1
    out = []
    for idx, p in enumerate(points):
        h = int(round(15 + (85 * (p / mx))))
        out.append(
            {
                "value": p,
                "height": max(12, min(100, h)),
                "label": labels[idx] if idx < len(labels) else "",
            }
        )
    return out


@register.simple_tag
def stat_books():
    return Book.objects.filter(is_deleted=False).count()


@register.simple_tag
def stat_copies():
    return Copy.objects.filter(is_deleted=False).count()


@register.simple_tag
def stat_available_copies():
    return Copy.objects.filter(is_deleted=False, status=CopyStatus.AVAILABLE).count()


@register.simple_tag
def stat_members():
    return MemberProfile.objects.count()


@register.simple_tag
def stat_active_loans():
    return Loan.objects.filter(status=LoanStatus.ACTIVE).count()


@register.simple_tag
def stat_overdue_loans():
    return Loan.objects.filter(status=LoanStatus.ACTIVE, due_at__lt=timezone.now()).count()

@register.simple_tag
def stat_genres():
    return Genre.objects.count()


@register.simple_tag
def stat_authors():
    return Author.objects.count()


@register.simple_tag
def stat_publishers():
    return (
        Publisher.objects.filter(books__is_deleted=False)
        .distinct()
        .count()
    )


@register.simple_tag
def stat_requests_pending():
    return ReservationRequest.objects.filter(status=ReservationRequestStatus.PENDING).count()


@register.simple_tag
def stat_requests_approved():
    return ReservationRequest.objects.filter(status=ReservationRequestStatus.APPROVED).count()


@register.simple_tag
def stat_requests_rejected():
    return ReservationRequest.objects.filter(status=ReservationRequestStatus.REJECTED).count()


@register.simple_tag
def stat_books_purchase_total_lek():
    total = Decimal("0.00")
    books = Book.objects.filter(is_deleted=False).annotate(
        active_copies=Count("copies", filter=Q(copies__is_deleted=False))
    )
    for book in books:
        if not book.price or not book.active_copies:
            continue
        total += (book.price * book.active_copies)
    return round(total, 2)


@register.simple_tag
def stat_avg_days_kept():
    # Average days between loaned_at and returned_at (returned loans only)
    qs = Loan.objects.filter(status=LoanStatus.RETURNED, returned_at__isnull=False)
    duration = ExpressionWrapper(F("returned_at") - F("loaned_at"), output_field=DurationField())
    agg = qs.aggregate(avg=Avg(duration))["avg"]
    if not agg:
        return 0
    try:
        days = agg.total_seconds() / 86400.0
        return round(days, 1)
    except Exception:
        return 0


@register.simple_tag
def stat_unpaid_fines():
    return Fine.objects.filter(status=FineStatus.UNPAID).count()


@register.simple_tag
def top_members_by_loans(limit=5):
    return (
        MemberProfile.objects.select_related("user")
        .annotate(total_loans=Count("loans"))
        .filter(total_loans__gt=0)
        .order_by("-total_loans", "full_name")[:limit]
    )


@register.simple_tag
def top_books_by_loans(limit=5):
    return (
        Book.objects.filter(is_deleted=False)
        .annotate(total_loans=Count("copies__loans"))
        .filter(total_loans__gt=0)
        .order_by("-total_loans", "title")[:limit]
    )


# ——— Dashboard analitikë ———

def _month_range(months=12):
    """Yields (date_first_of_month, label) for the last `months` months."""
    from datetime import date
    now = timezone.now().date()
    y, m = now.year, now.month
    for _ in range(months):
        yield date(y, m, 1), f"{month_abbr[m]} {y}"
        m -= 1
        if m < 1:
            m, y = 12, y - 1


@register.simple_tag
def dashboard_loans_by_month(months=12):
    """Lista {month: "Jan 2025", count: N} për grafik huazimesh sipas muajve."""
    from datetime import datetime
    month_list = list(_month_range(months))
    if not month_list:
        return []
    start = timezone.make_aware(datetime.combine(month_list[-1][0], datetime.min.time()))
    qs = (
        Loan.objects.filter(loaned_at__gte=start)
        .annotate(month=TruncMonth("loaned_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    by_month = {r["month"].strftime("%Y-%m"): r["count"] for r in qs}
    result = []
    for d, label in month_list:
        key = d.strftime("%Y-%m")
        result.append({"month": label, "count": by_month.get(key, 0)})
    result.reverse()
    return result


@register.simple_tag
def dashboard_reservations_by_month(months=12):
    """Lista {month: "Jan 2025", count: N} për grafik rezervimesh."""
    from datetime import datetime
    month_list = list(_month_range(months))
    if not month_list:
        return []
    start = timezone.make_aware(datetime.combine(month_list[-1][0], datetime.min.time()))
    qs = (
        Reservation.objects.filter(created_at__gte=start)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    by_month = {r["month"].strftime("%Y-%m"): r["count"] for r in qs}
    result = []
    for d, label in month_list:
        key = d.strftime("%Y-%m")
        result.append({"month": label, "count": by_month.get(key, 0)})
    result.reverse()
    return result


def _period_counts_loans():
    from datetime import timedelta
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=today_start.weekday())
    prev_week_start = week_start - timedelta(days=7)
    month_start = today_start.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    return {
        "today": Loan.objects.filter(loaned_at__gte=today_start).count(),
        "yesterday": Loan.objects.filter(loaned_at__gte=yesterday_start, loaned_at__lt=today_start).count(),
        "this_week": Loan.objects.filter(loaned_at__gte=week_start).count(),
        "prev_week": Loan.objects.filter(loaned_at__gte=prev_week_start, loaned_at__lt=week_start).count(),
        "this_month": Loan.objects.filter(loaned_at__gte=month_start).count(),
        "prev_month": Loan.objects.filter(loaned_at__gte=prev_month_start, loaned_at__lt=month_start).count(),
    }


@register.simple_tag
def dashboard_loans_today():
    return _period_counts_loans()["today"]


@register.simple_tag
def dashboard_loans_yesterday():
    return _period_counts_loans()["yesterday"]


@register.simple_tag
def dashboard_loans_this_week():
    return _period_counts_loans()["this_week"]


@register.simple_tag
def dashboard_loans_prev_week():
    return _period_counts_loans()["prev_week"]


@register.simple_tag
def dashboard_loans_this_month():
    return _period_counts_loans()["this_month"]


@register.simple_tag
def dashboard_loans_prev_month():
    return _period_counts_loans()["prev_month"]


@register.simple_tag
def dashboard_top_books(limit=15):
    return list(
        Book.objects.filter(is_deleted=False)
        .annotate(total_loans=Count("copies__loans"))
        .filter(total_loans__gt=0)
        .order_by("-total_loans", "title")[:limit]
        .values("id", "title", "total_loans")
    )


@register.simple_tag
def dashboard_top_authors(limit=10):
    return list(
        Author.objects.annotate(total_loans=Count("books__copies__loans"))
        .filter(total_loans__gt=0)
        .order_by("-total_loans", "name")[:limit]
        .values("id", "name", "total_loans")
    )


@register.simple_tag
def dashboard_top_members(limit=15):
    return list(
        MemberProfile.objects.select_related("user")
        .annotate(total_loans=Count("loans"))
        .filter(total_loans__gt=0)
        .order_by("-total_loans", "full_name")[:limit]
    )


@register.simple_tag
def dashboard_unpaid_fines_total():
    from django.db.models import Sum
    r = Fine.objects.filter(status=FineStatus.UNPAID).aggregate(s=Sum("amount"))
    return r["s"] or 0


@register.simple_tag
def dashboard_unpaid_fines_member_count():
    return Fine.objects.filter(status=FineStatus.UNPAID).values("member").distinct().count()


@register.simple_tag
def dashboard_copies_on_loan():
    return Copy.objects.filter(is_deleted=False, status=CopyStatus.ON_LOAN).count()


@register.simple_tag
def dashboard_loans_due_soon():
    """Huazime që skadojnë në 1–3 ditët e ardhshme."""
    from datetime import timedelta
    now = timezone.now()
    today = now.date()
    end = today + timedelta(days=3)
    return Loan.objects.filter(
        status=LoanStatus.ACTIVE,
        due_at__date__gte=today,
        due_at__date__lte=end,
    ).select_related("member", "member__user", "copy", "copy__book").order_by("due_at")[:20]


@register.simple_tag
def dashboard_reservations_pending_count():
    """Kërkesa rezervimesh në pritje (ReservationRequest PENDING)."""
    return ReservationRequest.objects.filter(status=ReservationRequestStatus.PENDING).count()


@register.simple_tag
def dashboard_executive_overview():
    now = timezone.now()
    overdue_loans = Loan.objects.filter(status=LoanStatus.ACTIVE, due_at__lt=now).count()
    overdue_reservations = Reservation.objects.filter(
        status="APPROVED",
        loan__isnull=True,
        pickup_date__lt=now.date(),
    ).count()
    pending_requests = ReservationRequest.objects.filter(status=ReservationRequestStatus.PENDING).count()
    unpaid_fines = Fine.objects.filter(status=FineStatus.UNPAID)
    unpaid_fines_total = unpaid_fines.aggregate(s=Sum("amount")).get("s") or Decimal("0.00")

    th_overdue_loans = int(getattr(settings, "OPS_ALERT_OVERDUE_LOANS_THRESHOLD", 10) or 10)
    th_overdue_reservations = int(getattr(settings, "OPS_ALERT_OVERDUE_RESERVATIONS_THRESHOLD", 5) or 5)
    th_pending_requests = int(getattr(settings, "OPS_ALERT_PENDING_REQUESTS_THRESHOLD", 20) or 20)
    try:
        th_unpaid_fines_total = Decimal(str(getattr(settings, "OPS_ALERT_UNPAID_FINES_TOTAL_THRESHOLD", "1000.00")))
    except Exception:
        th_unpaid_fines_total = Decimal("1000.00")

    metrics = [
        {
            "key": "overdue_loans",
            "label": "Huazime me afat të kaluar",
            "value": overdue_loans,
            "threshold": th_overdue_loans,
            "severity": _metric_severity(Decimal(str(overdue_loans)), Decimal(str(th_overdue_loans))),
            "url": "/admin/circulation/loan/?status__exact=ACTIVE",
        },
        {
            "key": "overdue_reservations",
            "label": "Rezervime për skadim",
            "value": overdue_reservations,
            "threshold": th_overdue_reservations,
            "severity": _metric_severity(Decimal(str(overdue_reservations)), Decimal(str(th_overdue_reservations))),
            "url": "/admin/circulation/reservation/?status__exact=APPROVED",
        },
        {
            "key": "pending_requests",
            "label": "Kërkesa në pritje",
            "value": pending_requests,
            "threshold": th_pending_requests,
            "severity": _metric_severity(Decimal(str(pending_requests)), Decimal(str(th_pending_requests))),
            "url": "/admin/circulation/reservationrequest/?status__exact=PENDING",
        },
        {
            "key": "unpaid_fines_total",
            "label": "Gjoba të papaguara (€)",
            "value": unpaid_fines_total,
            "threshold": th_unpaid_fines_total,
            "severity": _metric_severity(Decimal(str(unpaid_fines_total)), th_unpaid_fines_total),
            "url": "/admin/fines/fine/?status__exact=UNPAID",
        },
    ]

    now_date = now.date()
    for m in metrics:
        points = []
        labels = []
        for d in range(6, -1, -1):
            day = now_date - timedelta(days=d)
            labels.append(day.strftime("%d/%m"))
            if m["key"] == "overdue_loans":
                v = Loan.objects.filter(status=LoanStatus.ACTIVE, due_at__date__lte=day).count()
            elif m["key"] == "overdue_reservations":
                v = Reservation.objects.filter(status="APPROVED", loan__isnull=True, pickup_date__lt=day).count()
            elif m["key"] == "pending_requests":
                v = ReservationRequest.objects.filter(
                    status=ReservationRequestStatus.PENDING,
                    created_at__date__lte=day,
                ).count()
            else:
                agg = Fine.objects.filter(status=FineStatus.UNPAID, created_at__date__lte=day).aggregate(s=Sum("amount"))
                v = float(agg.get("s") or 0)
            points.append(int(v))
        m["trend_points"] = points
        m["sparkline"] = _sparkline(points, labels)
        m["trend_delta"] = points[-1] - points[0] if points else 0

    priority = "NORMAL"
    actions = []
    for m in metrics:
        if _severity_rank(m["severity"]) > _severity_rank(priority):
            priority = m["severity"]
        if m["severity"] == "NORMAL":
            continue
        actions.append(
            f"[{m['severity']}] {m['label']}: kontrollo menjëherë këtë listë."
        )
    return {"priority": priority, "metrics": metrics, "actions": actions}


@register.inclusion_tag("admin/partials/in_app_notifications_card.html", takes_context=True)
def in_app_notifications_card(context):
    """In-app notifications preview on the admin index dashboard (/admin/)."""
    request = context.get("request")
    empty = {"show": False, "notifications": [], "unread_count": 0, "changelist_url": ""}
    if not request or not getattr(request.user, "is_authenticated", False):
        return empty
    if not getattr(request.user, "is_staff", False):
        return empty
    from notifications.models import UserNotification

    user = request.user
    notifications = list(UserNotification.objects.filter(user=user).order_by("-created_at")[:8])
    unread_count = UserNotification.objects.filter(user=user, read_at__isnull=True).count()
    return {
        "show": True,
        "notifications": notifications,
        "unread_count": unread_count,
        "changelist_url": reverse("admin:notifications_usernotification_changelist"),
    }

