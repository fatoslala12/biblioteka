from datetime import date, timedelta

from django.db.models import Count, Prefetch, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.http import HttpRequest
from django.shortcuts import redirect, render

from django_ratelimit.decorators import ratelimit

from audit.models import AuditSeverity
from audit.services import get_client_ip, log_audit_event
from accounts.models import MemberProfile, MemberStatus, MemberType, UserRole
from catalog.models import Book
from circulation.exceptions import PolicyViolation
from circulation.models import Hold, HoldStatus, Loan, LoanStatus
from circulation.models import ReservationRequest, ReservationRequestStatus
from circulation.services import create_reservation_request
from cms.forms import MemberPasswordChangeForm, MemberProfileUpdateForm, MemberSignUpForm
from fines.models import Fine, FineStatus, Payment

User = get_user_model()


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def _audit_member_event(
    *,
    user,
    action_type: str,
    source_screen: str,
    reason: str = "",
    changes: dict | None = None,
    metadata: dict | None = None,
    severity: str = AuditSeverity.INFO,
):
    try:
        log_audit_event(
            target=user,
            actor=user,
            action_type=action_type,
            source_screen=source_screen,
            reason=reason,
            changes=changes or {},
            metadata=metadata or {},
            severity=severity,
        )
    except Exception:
        return


def _login_default_destination(user) -> str:
    # Superuser/staff → admin first (they can still open /panel/)
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return "/admin/"
    if getattr(user, "role", None) in (UserRole.ADMIN, UserRole.STAFF):
        return "/panel/"
    return "/anetar/"


def _member_signup_errors_to_messages(request: HttpRequest, form: MemberSignUpForm) -> None:
    for field, errs in form.errors.items():
        if field == "__all__":
            for err in errs:
                messages.error(request, str(err))
            continue
        fld = form.fields.get(field)
        prefix = f"{fld.label}: " if fld and fld.label else ""
        for err in errs:
            messages.error(request, f"{prefix}{err}")


def _safe_next_for_user(request: HttpRequest, user, next_url: str | None) -> str | None:
    if not next_url:
        return None
    next_url = (next_url or "").strip()
    if not next_url:
        return None
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return None

    # Members must not be redirected into staff/admin areas.
    if getattr(user, "role", None) == UserRole.MEMBER and (
        next_url.startswith("/admin") or next_url.startswith("/panel")
    ):
        return None
    return next_url


def sign_in(request: HttpRequest):
    next_url = (request.GET.get("next") or request.POST.get("next") or "").strip()

    if request.user.is_authenticated:
        safe_next = _safe_next_for_user(request, request.user, next_url)
        return redirect(safe_next or _login_default_destination(request.user))

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is None and "@" in username:
            match = User.objects.filter(email__iexact=username).only("username").first()
            if match:
                user = authenticate(request, username=match.username, password=password)
        if user is None:
            messages.error(request, "Përdoruesi ose fjalëkalimi është i pasaktë.")
        else:
            if getattr(user, "is_locked", False):
                messages.error(request, "Llogaria është e bllokuar. Kontakto administratorin.")
            else:
                login(request, user)
                safe_next = _safe_next_for_user(request, user, next_url)
                return redirect(safe_next or _login_default_destination(user))

    return render(request, "cms/auth/sign_in.html", {"next": next_url})


@ratelimit(key="ip", rate="5/m", method="POST")
@ratelimit(key="ip", rate="25/h", method="POST")
def sign_up(request: HttpRequest):
    if request.user.is_authenticated:
        return redirect(_login_default_destination(request.user))

    if request.method == "POST" and getattr(request, "limited", False):
        messages.error(
            request,
            "Shumë përpjekje regjistrimi nga kjo adresë. Prisni pak dhe provoni përsëri.",
        )
        return render(
            request,
            "cms/auth/sign_up.html",
            {"form": MemberSignUpForm()},
            status=429,
        )

    if request.method == "POST":
        form = MemberSignUpForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            email = data["email"]
            password = data["password1"]
            full_name = data["full_name"].strip()
            fn, ln = _split_full_name(full_name)
            username = email
            try:
                with transaction.atomic():
                    member_no = MemberProfile._next_member_no()
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=(fn or "")[:150],
                        last_name=(ln or "")[:150],
                        role=UserRole.MEMBER,
                        is_staff=False,
                        is_superuser=False,
                    )
                    MemberProfile.objects.create(
                        user=user,
                        member_no=member_no,
                        full_name=full_name,
                        phone=data["phone"].strip(),
                        date_of_birth=data["date_of_birth"],
                        national_id=data["national_id"].strip(),
                        place_of_birth=data["place_of_birth"].strip(),
                        address=data["address"].strip(),
                        status=MemberStatus.ACTIVE,
                        member_type=MemberType.STANDARD,
                    )
            except Exception:
                messages.error(
                    request,
                    "Regjistrimi dështoi (p.sh. përdorues ekzistues). Provoni përsëri ose kontaktoni bibliotekën.",
                )
                return render(request, "cms/auth/sign_up.html", {"form": form})

            try:
                log_audit_event(
                    target=user,
                    actor=user,
                    action_type="MEMBER_SELF_REGISTERED",
                    source_screen="auth.sign_up",
                    reason="",
                    changes={"member_no": member_no},
                    metadata={"email": email},
                    severity=AuditSeverity.INFO,
                    ip_address=get_client_ip(request),
                    user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:512],
                )
            except Exception:
                pass

            login(request, user)
            messages.success(
                request,
                f"Mirë se erdhe! Nr. anëtari: {member_no}. Hyni më vonë me email-in tuaj si përdorues.",
            )
            return redirect("/anetar/")
        _member_signup_errors_to_messages(request, form)
    else:
        form = MemberSignUpForm()

    return render(request, "cms/auth/sign_up.html", {"form": form})


def sign_out(request: HttpRequest):
    logout(request)
    return redirect("/")


def member_portal(request: HttpRequest):
    user = request.user
    if not user.is_authenticated:
        return redirect(f"/hyr/?next=/anetar/")

    member_profile = getattr(user, "member_profile", None)
    if user.role != UserRole.MEMBER or member_profile is None:
        return redirect(_login_default_destination(user))

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
    fines = (
        Fine.objects.filter(member=member_profile)
        .prefetch_related(Prefetch("payments", queryset=Payment.objects.order_by("-created_at"), to_attr="portal_payments"))
        .order_by("-created_at")[:20]
    )
    latest_payments = (
        Payment.objects.select_related("fine", "fine__loan", "fine__loan__copy", "fine__loan__copy__book")
        .filter(fine__member=member_profile)
        .order_by("-created_at")[:8]
    )
    for fine in fines:
        paid = sum([p.amount for p in getattr(fine, "portal_payments", [])], start=0)
        remaining = max(0, (fine.amount or 0) - paid)
        fine.portal_paid_total = paid
        fine.portal_remaining = remaining
        fine.portal_status_label = "Pagesë e pjesshme" if (fine.status == FineStatus.UNPAID and paid > 0 and remaining > 0) else (
            "E paguar" if remaining <= 0 else fine.get_status_display()
        )
    unpaid_total = sum([getattr(f, "portal_remaining", 0) for f in fines if f.status == FineStatus.UNPAID], start=0)
    paid_total = Payment.objects.filter(fine__member=member_profile).aggregate(total=Sum("amount")).get("total") or 0
    unpaid_fines_count = sum([1 for f in fines if f.status == FineStatus.UNPAID and getattr(f, "portal_remaining", 0) > 0])
    paid_fines_count = sum([1 for f in fines if f.status == FineStatus.PAID])

    # Member dashboard metrics
    total_loans_count = Loan.objects.filter(member=member_profile).count()
    active_loans_count = active_loans.count()
    pending_requests_count = ReservationRequest.objects.filter(
        member=member_profile, status=ReservationRequestStatus.PENDING
    ).count()
    ready_for_pickup_count = ready_for_pickup.count()

    # Loans per month (last 6 months, including current month)
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

    # derived metrics after we have active_rows
    overdue_loans_count = sum([1 for r in active_rows if r["overdue"]])

    return render(
        request,
        "cms/member/portal.html",
        {
            "member": member_profile,
            "profile_form": MemberProfileUpdateForm(instance=member_profile),
            "password_form": MemberPasswordChangeForm(user=user),
            "active_rows": active_rows,
            "history": history,
            "requests": requests_qs,
            "ready_for_pickup": ready_for_pickup,
            "fines": fines,
            "latest_payments": latest_payments,
            "unpaid_total": unpaid_total,
            "paid_total": paid_total,
            "unpaid_fines_count": unpaid_fines_count,
            "paid_fines_count": paid_fines_count,
            "total_loans_count": total_loans_count,
            "active_loans_count": active_loans_count,
            "overdue_loans_count": overdue_loans_count,
            "pending_requests_count": pending_requests_count,
            "ready_for_pickup_count": ready_for_pickup_count,
            "loan_chart_labels": loan_chart_labels,
            "loan_chart_data": loan_chart_data,
        },
    )


@require_POST
def member_place_hold(request: HttpRequest, book_id: int):
    user = request.user
    if not user.is_authenticated:
        return redirect(f"/hyr/?next=/books/{book_id}/")

    member_profile = getattr(user, "member_profile", None)
    if getattr(user, "role", None) != UserRole.MEMBER or member_profile is None:
        messages.error(request, "Ky veprim lejohet vetëm për anëtarët.")
        return redirect(_login_default_destination(user))

    book = get_object_or_404(Book.objects.filter(is_deleted=False), pk=book_id)
    try:
        pickup_date = (request.POST.get("pickup_date") or "").strip()
        return_date = (request.POST.get("return_date") or "").strip()
        create_reservation_request(
            member_no=member_profile.member_no,
            book_id=book.id,
            pickup_date=pickup_date,
            return_date=return_date,
            created_by=user if user.is_authenticated else None,
            source_screen="member.book_detail.reserve",
        )
        messages.success(
            request,
            "Kërkesa për rezervim u dërgua. Stafi do e shqyrtojë dhe do ta pranojë ose refuzojë.",
        )
    except PolicyViolation as e:
        messages.error(request, f"Nuk u realizua: {str(e)}")

    return redirect(f"/books/{book.id}/")


@require_POST
def member_update_profile(request: HttpRequest):
    user = request.user
    if not user.is_authenticated:
        return redirect("/hyr/?next=/anetar/")

    member_profile = getattr(user, "member_profile", None)
    if getattr(user, "role", None) != UserRole.MEMBER or member_profile is None:
        messages.error(request, "Ky veprim lejohet vetëm për anëtarët.")
        return redirect(_login_default_destination(user))

    old_data = {
        "full_name": member_profile.full_name or "",
        "phone": member_profile.phone or "",
        "address": member_profile.address or "",
    }
    form = MemberProfileUpdateForm(request.POST, request.FILES, instance=member_profile)
    if form.is_valid():
        member = form.save()
        # Keep the auth user names reasonably in sync with profile.
        full_name = (member.full_name or "").strip()
        parts = [p for p in full_name.split() if p]
        if parts and getattr(member, "user_id", None):
            member.user.first_name = parts[0]
            if len(parts) >= 2:
                member.user.last_name = parts[-1]
            member.user.save(update_fields=["first_name", "last_name"])
        changes = {}
        for key in ("full_name", "phone", "address"):
            old_v = old_data.get(key, "")
            new_v = getattr(member, key, "") or ""
            if old_v != new_v:
                changes[key] = {"old": old_v, "new": new_v}
        if changes:
            _audit_member_event(
                user=user,
                action_type="MEMBER_PROFILE_UPDATED",
                source_screen="member.profile.update",
                changes=changes,
            )
        messages.success(request, "Profili u përditësua me sukses.")
    else:
        _audit_member_event(
            user=user,
            action_type="MEMBER_PROFILE_UPDATE_FAILED",
            source_screen="member.profile.update",
            reason="Forma e profilit dështoi validimin.",
            severity=AuditSeverity.INCIDENT,
            metadata={"errors": form.errors.get_json_data()},
        )
        messages.error(request, "Kontrollo fushat e profilit dhe provo sërish.")
    return redirect("/anetar/")


@require_POST
def member_change_password(request: HttpRequest):
    user = request.user
    if not user.is_authenticated:
        return redirect("/hyr/?next=/anetar/")

    member_profile = getattr(user, "member_profile", None)
    if getattr(user, "role", None) != UserRole.MEMBER or member_profile is None:
        messages.error(request, "Ky veprim lejohet vetëm për anëtarët.")
        return redirect(_login_default_destination(user))

    form = MemberPasswordChangeForm(request.POST, user=user)
    if form.is_valid():
        new_pw = form.cleaned_data["new_password1"]
        user.set_password(new_pw)
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)
        _audit_member_event(
            user=user,
            action_type="MEMBER_PASSWORD_CHANGED",
            source_screen="member.password.change",
        )
        messages.success(request, "Fjalëkalimi u ndryshua me sukses.")
    else:
        _audit_member_event(
            user=user,
            action_type="MEMBER_PASSWORD_CHANGE_FAILED",
            source_screen="member.password.change",
            reason="Forma e ndryshimit të fjalëkalimit dështoi validimin.",
            severity=AuditSeverity.INCIDENT,
            metadata={"errors": form.errors.get_json_data()},
        )
        messages.error(request, "Nuk u ndryshua fjalëkalimi. Kontrollo fushat dhe provo sërish.")
    return redirect("/anetar/")


@require_POST
def member_cancel_request(request: HttpRequest, request_id: int):
    user = request.user
    if not user.is_authenticated:
        return redirect("/hyr/?next=/anetar/")

    member_profile = getattr(user, "member_profile", None)
    if getattr(user, "role", None) != UserRole.MEMBER or member_profile is None:
        messages.error(request, "Ky veprim lejohet vetëm për anëtarët.")
        return redirect(_login_default_destination(user))

    req = get_object_or_404(ReservationRequest, id=request_id, member=member_profile)
    if req.status != ReservationRequestStatus.PENDING:
        messages.error(request, "Vetëm kërkesat “Në pritje” mund të anulohen.")
        return redirect("/anetar/")

    req.status = ReservationRequestStatus.CANCELLED
    req.decided_at = timezone.now()
    req.decided_by = None
    req.decision_reason = "Anuluar nga anëtari."
    req.save(update_fields=["status", "decided_at", "decided_by", "decision_reason"])
    _audit_member_event(
        user=user,
        action_type="MEMBER_RESERVATION_REQUEST_CANCELLED",
        source_screen="member.request.cancel",
        reason=f"Anuluar kërkesa #{req.id}.",
        metadata={"request_id": req.id, "book_id": req.book_id},
        severity=AuditSeverity.INCIDENT,
    )
    messages.success(request, "Kërkesa u anulua.")
    return redirect("/anetar/")

