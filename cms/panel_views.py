from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import MemberProfile
from catalog.models import Book, Copy, CopyStatus
from circulation.models import Hold, HoldStatus, Loan, LoanStatus, ReservationRequest, ReservationRequestStatus
from cms.decorators import staff_required
from cms.forms import MemberProfileUpdateForm
from cms.panel_forms import BookPanelForm, CopyPanelForm
from fines.models import Fine, FineStatus
from notifications.models import UserNotification


def _base_ctx():
    return {
        "brand_name": "Smart Library",
    }


@staff_required
def dashboard(request: HttpRequest):
    books = Book.objects.filter(is_deleted=False).count()
    copies = Copy.objects.filter(is_deleted=False).count()
    available = Copy.objects.filter(is_deleted=False, status=CopyStatus.AVAILABLE).count()
    return render(
        request,
        "cms/panel/dashboard.html",
        {
            **_base_ctx(),
            "books": books,
            "copies": copies,
            "available": available,
        },
    )


@staff_required
def books_list(request: HttpRequest):
    q = (request.GET.get("q") or "").strip()
    qs = (
        Book.objects.filter(is_deleted=False)
        .select_related("publisher")
        .annotate(
            total_copies=Count("copies", filter=Q(copies__is_deleted=False), distinct=True),
            available_copies=Count(
                "copies",
                filter=Q(copies__is_deleted=False, copies__status=CopyStatus.AVAILABLE),
                distinct=True,
            ),
        )
        .order_by("title")
    )
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(isbn__icontains=q) | Q(authors__name__icontains=q)).distinct()

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "cms/panel/books_list.html",
        {
            **_base_ctx(),
            "q": q,
            "page_obj": page_obj,
        },
    )


@staff_required
def book_new(request: HttpRequest):
    if request.method == "POST":
        form = BookPanelForm(request.POST)
        if form.is_valid():
            book = form.save()
            return redirect("cms:panel_book_manage", pk=book.pk)
    else:
        form = BookPanelForm()
    return render(request, "cms/panel/book_form.html", {**_base_ctx(), "form": form, "mode": "new"})


@staff_required
def book_edit(request: HttpRequest, pk: int):
    book = get_object_or_404(Book, pk=pk, is_deleted=False)
    if request.method == "POST":
        form = BookPanelForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            return redirect("cms:panel_book_manage", pk=book.pk)
    else:
        form = BookPanelForm(instance=book)
    return render(
        request,
        "cms/panel/book_form.html",
        {**_base_ctx(), "form": form, "book": book, "mode": "edit"},
    )


@staff_required
def book_manage(request: HttpRequest, pk: int):
    book = get_object_or_404(Book, pk=pk, is_deleted=False)
    copies = book.copies.filter(is_deleted=False).order_by("-created_at")
    counts = {
        "total": copies.count(),
        "available": copies.filter(status=CopyStatus.AVAILABLE).count(),
        "on_loan": copies.filter(status=CopyStatus.ON_LOAN).count(),
        "on_hold": copies.filter(status=CopyStatus.ON_HOLD).count(),
    }
    return render(
        request,
        "cms/panel/book_manage.html",
        {
            **_base_ctx(),
            "book": book,
            "copies": copies,
            "counts": counts,
        },
    )


@staff_required
def copy_new(request: HttpRequest, book_pk: int):
    book = get_object_or_404(Book, pk=book_pk, is_deleted=False)
    if request.method == "POST":
        form = CopyPanelForm(request.POST)
        if form.is_valid():
            copy = form.save(commit=False)
            copy.book = book
            copy.save()
            return redirect("cms:panel_book_manage", pk=book.pk)
    else:
        form = CopyPanelForm()
    return render(
        request,
        "cms/panel/copy_form.html",
        {**_base_ctx(), "form": form, "book": book, "mode": "new"},
    )


@staff_required
def copy_edit(request: HttpRequest, pk: int):
    copy = get_object_or_404(Copy, pk=pk, is_deleted=False)
    if request.method == "POST":
        form = CopyPanelForm(request.POST, instance=copy)
        if form.is_valid():
            form.save()
            return redirect("cms:panel_book_manage", pk=copy.book_id)
    else:
        form = CopyPanelForm(instance=copy)
    return render(
        request,
        "cms/panel/copy_form.html",
        {**_base_ctx(), "form": form, "book": copy.book, "copy": copy, "mode": "edit"},
    )


def _member_portal_ctx(member_profile: MemberProfile):
    active_loans = (
        Loan.objects.select_related("copy", "copy__book")
        .filter(member=member_profile, status=LoanStatus.ACTIVE)
        .order_by("due_at")
    )
    history = (
        Loan.objects.select_related("copy", "copy__book")
        .filter(member=member_profile, status=LoanStatus.RETURNED)
        .order_by("-returned_at")[:20]
    )
    requests_qs = (
        ReservationRequest.objects.select_related("book")
        .filter(member=member_profile)
        .order_by("-created_at")[:20]
    )
    ready_for_pickup = (
        Hold.objects.select_related("book")
        .filter(member=member_profile, status=HoldStatus.READY_FOR_PICKUP)
        .order_by("expires_at")[:20]
    )
    fines = Fine.objects.filter(member=member_profile).order_by("-created_at")[:20]
    unpaid_total = sum([f.amount for f in fines if f.status == FineStatus.UNPAID], start=0)

    total_loans_count = Loan.objects.filter(member=member_profile).count()
    active_loans_count = active_loans.count()
    pending_requests_count = ReservationRequest.objects.filter(
        member=member_profile, status=ReservationRequestStatus.PENDING
    ).count()
    ready_for_pickup_count = ready_for_pickup.count()

    now = timezone.now().date()
    start = (now.replace(day=1) - timedelta(days=31 * 5)).replace(day=1)

    def add_month(d: date, n: int) -> date:
        y = d.year + (d.month - 1 + n) // 12
        m = (d.month - 1 + n) % 12 + 1
        return date(y, m, 1)

    months = [add_month(start, i) for i in range(6)]
    raw = (
        Loan.objects.filter(member=member_profile, loaned_at__date__gte=start)
        .annotate(month=TruncMonth("loaned_at"))
        .values("month")
        .annotate(c=Count("id"))
        .order_by("month")
    )
    raw_map = {r["month"].date(): r["c"] for r in raw if r.get("month")}
    loan_chart_labels = [f"{m.year}-{m.month:02d}" for m in months]
    loan_chart_data = [int(raw_map.get(m, 0)) for m in months]

    today = date.today()
    active_rows = []
    for loan in active_loans:
        days_kept = (today - loan.loaned_at.date()).days
        days_left = (loan.due_at.date() - today).days
        active_rows.append(
            {
                "loan": loan,
                "days_kept": days_kept,
                "days_left": days_left,
                "overdue": days_left < 0,
            }
        )

    overdue_loans_count = sum([1 for r in active_rows if r["overdue"]])
    return {
        "member": member_profile,
        "active_rows": active_rows,
        "history": history,
        "requests": requests_qs,
        "ready_for_pickup": ready_for_pickup,
        "fines": fines,
        "unpaid_total": unpaid_total,
        "total_loans_count": total_loans_count,
        "active_loans_count": active_loans_count,
        "overdue_loans_count": overdue_loans_count,
        "pending_requests_count": pending_requests_count,
        "ready_for_pickup_count": ready_for_pickup_count,
        "loan_chart_labels": loan_chart_labels,
        "loan_chart_data": loan_chart_data,
    }


@staff_required
def member_profile_portal(request: HttpRequest, pk: int):
    member_profile = get_object_or_404(MemberProfile, pk=pk)
    if request.method == "POST":
        form = MemberProfileUpdateForm(request.POST, request.FILES, instance=member_profile)
        if form.is_valid():
            member = form.save()
            full_name = (member.full_name or "").strip()
            parts = [p for p in full_name.split() if p]
            if parts and getattr(member, "user_id", None):
                member.user.first_name = parts[0]
                if len(parts) >= 2:
                    member.user.last_name = parts[-1]
                member.user.save(update_fields=["first_name", "last_name"])
            messages.success(request, "Profili i anëtarit u përditësua me sukses.")
            return redirect("cms:panel_member_profile", pk=member_profile.pk)
        messages.error(request, "Kontrollo fushat e profilit dhe provo sërish.")
    else:
        form = MemberProfileUpdateForm(instance=member_profile)

    ctx = _member_portal_ctx(member_profile)
    ctx.update(
        {
            "profile_form": form,
            "staff_view_mode": True,
            "profile_update_url": request.path,
        }
    )
    return render(request, "cms/member/portal.html", ctx)


@staff_required
def staff_notifications(request: HttpRequest):
    rid = (request.GET.get("read") or "").strip()
    if rid.isdigit():
        UserNotification.objects.filter(user=request.user, id=int(rid), read_at__isnull=True).update(
            read_at=timezone.now()
        )

    if request.method == "POST" and request.POST.get("action") == "mark_all_read":
        UserNotification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        messages.success(request, "Të gjitha njoftimet u shënuan si të lexuara.")
        return redirect("/panel/njoftime/")

    paginator = Paginator(UserNotification.objects.filter(user=request.user).order_by("-created_at"), 24)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "cms/panel/notifications.html",
        {
            **_base_ctx(),
            "page_obj": page_obj,
        },
    )

