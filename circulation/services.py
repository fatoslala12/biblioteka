from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import Count, Max, Sum
from django.utils import timezone

from audit.models import AuditSeverity
from audit.services import log_audit_event
from accounts.models import MemberProfile, MemberStatus
from catalog.models import Copy, CopyStatus
from circulation.exceptions import NotAvailable, PolicyViolation
from circulation.models import (
    Hold,
    HoldStatus,
    Loan,
    LoanStatus,
    Reservation,
    ReservationStatus,
    ReservationRequest,
    ReservationRequestStatus,
)
from fines.models import Fine, FineStatus
from policies.models import LibraryPolicy, LoanRule


def _try_log(**kwargs):
    try:
        log_audit_event(**kwargs)
    except Exception:
        # Audit must never block core circulation actions.
        return


def _as_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        s = d.strip()
        try:
            # Expect ISO format from HTML date input: YYYY-MM-DD
            return datetime.fromisoformat(s).date()
        except Exception:
            raise PolicyViolation("Datë e pavlefshme. Përdor formatin YYYY-MM-DD.")
    raise PolicyViolation("Datë e pavlefshme.")


def _book_capacity_for_range(book_id: int, start: date, end: date) -> tuple[int, int]:
    total = Copy.objects.filter(book_id=book_id, is_deleted=False).count()

    # Active loans occupying copies during [start, end] (approx by loaned_at..due_at).
    loan_count = Loan.objects.filter(
        copy__book_id=book_id,
        status=LoanStatus.ACTIVE,
        loaned_at__date__lte=end,
        due_at__date__gte=start,
    ).count()

    reservation_count = Reservation.objects.filter(
        book_id=book_id,
        status=ReservationStatus.APPROVED,
        pickup_date__lte=end,
        return_date__gte=start,
    ).count()

    return total, (loan_count + reservation_count)


def get_book_availability_for_range(book_id: int, pickup_date: date, return_date: date) -> dict:
    pickup_date = _as_date(pickup_date)
    return_date = _as_date(return_date)
    if pickup_date > return_date:
        raise PolicyViolation("Datat janë të pavlefshme.")

    total, occupied = _book_capacity_for_range(book_id, pickup_date, return_date)
    free = max(0, total - occupied)
    return {"total": total, "occupied": occupied, "free": free}


def suggest_best_copy_for_quick_checkout(book_id: int):
    copy = (
        Copy.objects.filter(book_id=book_id, status=CopyStatus.AVAILABLE, is_deleted=False)
        .annotate(total_loans=Count("loans"))
        .order_by("total_loans", "id")
        .first()
    )
    if not copy:
        return None
    return {
        "copy_id": copy.id,
        "barcode": copy.barcode,
        "total_loans": int(getattr(copy, "total_loans", 0) or 0),
        "reason": "Kopja me konsum më të ulët (më pak huazime historike).",
    }


@dataclass(frozen=True)
class PolicySnapshot:
    fine_per_day: Decimal
    fine_cap: Decimal
    hold_window_hours: int
    max_renewals: int
    fine_block_threshold: Decimal
    loan_period_days: int
    max_active_loans: int


def _get_policy_snapshot(member: MemberProfile, copy: Copy) -> PolicySnapshot:
    policy, _ = LibraryPolicy.objects.get_or_create(name="default")
    rule = (
        LoanRule.objects.filter(
            policy=policy, member_type=member.member_type, book_type=copy.book.book_type
        )
        .order_by("id")
        .first()
    )
    return PolicySnapshot(
        fine_per_day=policy.fine_per_day,
        fine_cap=policy.fine_cap,
        hold_window_hours=policy.hold_window_hours,
        max_renewals=policy.max_renewals,
        fine_block_threshold=policy.fine_block_threshold,
        loan_period_days=(rule.loan_period_days if rule else policy.default_loan_period_days),
        max_active_loans=(rule.max_active_loans if rule else policy.default_max_active_loans),
    )


def _unpaid_fines_total(member: MemberProfile) -> Decimal:
    agg = Fine.objects.filter(member=member, status=FineStatus.UNPAID).aggregate(total=Sum("amount"))
    return (agg["total"] or Decimal("0.00")).quantize(Decimal("0.01"))


def _ensure_member_can_borrow(member: MemberProfile, policy: PolicySnapshot) -> None:
    if member.status in (MemberStatus.SUSPENDED, MemberStatus.BLOCKED):
        raise PolicyViolation("Member is not allowed to borrow (blocked/suspended).")

    unpaid_total = _unpaid_fines_total(member)
    if unpaid_total > policy.fine_block_threshold:
        raise PolicyViolation("Member has unpaid fines above threshold.")

    active_loans = Loan.objects.filter(member=member, status=LoanStatus.ACTIVE).count()
    if active_loans >= policy.max_active_loans:
        raise PolicyViolation("Member has reached the maximum number of active loans.")


def _expire_ready_holds(book_id: int) -> None:
    now = timezone.now()
    Hold.objects.filter(
        book_id=book_id,
        status=HoldStatus.READY_FOR_PICKUP,
        expires_at__isnull=False,
        expires_at__lt=now,
    ).update(status=HoldStatus.EXPIRED)


def _assign_next_hold_to_copy(copy: Copy) -> Hold | None:
    """
    Assign the next waiting hold (FIFO) to this copy, if any.
    """
    _expire_ready_holds(copy.book_id)
    next_hold = (
        Hold.objects.select_for_update()
        .filter(book_id=copy.book_id, status=HoldStatus.WAITING)
        .order_by("position")
        .first()
    )
    if not next_hold:
        copy.status = CopyStatus.AVAILABLE
        copy.hold_for = None
        copy.hold_expires_at = None
        copy.save(update_fields=["status", "hold_for", "hold_expires_at", "updated_at"])
        return None

    policy, _ = LibraryPolicy.objects.get_or_create(name="default")
    now = timezone.now()
    expires = now + timedelta(hours=policy.hold_window_hours)

    next_hold.status = HoldStatus.READY_FOR_PICKUP
    next_hold.ready_at = now
    next_hold.expires_at = expires
    next_hold.save(update_fields=["status", "ready_at", "expires_at"])

    copy.status = CopyStatus.ON_HOLD
    copy.hold_for = next_hold.member
    copy.hold_expires_at = expires
    copy.save(update_fields=["status", "hold_for", "hold_expires_at", "updated_at"])

    return next_hold


@transaction.atomic
def checkout_copy(
    *,
    member_no: str,
    copy_barcode: str,
    loaned_by=None,
    source_screen: str = "api.circulation.checkout",
    reason: str = "",
) -> Loan:
    member = MemberProfile.objects.select_for_update().select_related("user").get(member_no=member_no)
    copy = Copy.objects.select_for_update().select_related("book").get(barcode=copy_barcode, is_deleted=False)

    policy = _get_policy_snapshot(member, copy)
    _ensure_member_can_borrow(member, policy)

    now = timezone.now()

    if copy.status == CopyStatus.AVAILABLE:
        pass
    elif copy.status == CopyStatus.ON_HOLD:
        if copy.hold_for_id != member.id:
            raise NotAvailable("Copy is on hold for another member.")
        if copy.hold_expires_at and copy.hold_expires_at < now:
            # hold expired, make it available and proceed
            copy.status = CopyStatus.AVAILABLE
            copy.hold_for = None
            copy.hold_expires_at = None
            copy.save(update_fields=["status", "hold_for", "hold_expires_at", "updated_at"])
        else:
            # fulfil the hold for this member (if any)
            Hold.objects.filter(
                book_id=copy.book_id,
                member=member,
                status=HoldStatus.READY_FOR_PICKUP,
            ).update(status=HoldStatus.FULFILLED)
    else:
        raise NotAvailable(f"Copy is not available (status={copy.status}).")

    due_at = now + timedelta(days=policy.loan_period_days)

    loan = Loan.objects.create(
        member=member,
        copy=copy,
        due_at=due_at,
        status=LoanStatus.ACTIVE,
        loaned_by=loaned_by,
    )
    copy.status = CopyStatus.ON_LOAN
    copy.hold_for = None
    copy.hold_expires_at = None
    copy.save(update_fields=["status", "hold_for", "hold_expires_at", "updated_at"])
    _try_log(
        target=loan,
        loan=loan,
        action_type="LOAN_CREATED_DIRECT",
        actor=loaned_by,
        source_screen=source_screen,
        reason=reason,
        metadata={
            "member_no": member.member_no,
            "copy_barcode": copy.barcode,
            "book_id": copy.book_id,
        },
    )
    return loan


@transaction.atomic
def return_copy(
    *,
    copy_barcode: str,
    returned_by=None,
    source_screen: str = "api.circulation.return",
    reason: str = "",
) -> Loan:
    copy = Copy.objects.select_for_update().select_related("book").get(barcode=copy_barcode, is_deleted=False)
    loan = (
        Loan.objects.select_for_update()
        .select_related("member")
        .filter(copy=copy, status=LoanStatus.ACTIVE)
        .order_by("-loaned_at")
        .first()
    )
    if not loan:
        raise PolicyViolation("No active loan found for this copy.")

    now = timezone.now()
    loan.status = LoanStatus.RETURNED
    loan.returned_at = now
    loan.returned_by = returned_by
    loan.save(update_fields=["status", "returned_at", "returned_by", "updated_at"])

    # Fine calculation
    policy, _ = LibraryPolicy.objects.get_or_create(name="default")
    days_late = max(0, (now.date() - loan.due_at.date()).days)
    fine_amount = min(Decimal(days_late) * policy.fine_per_day, policy.fine_cap)

    if fine_amount > 0:
        Fine.objects.update_or_create(
            loan=loan,
            defaults={
                "member": loan.member,
                "amount": fine_amount,
                "status": FineStatus.UNPAID,
                "reason": "Overdue",
            },
        )

    _assign_next_hold_to_copy(copy)
    _try_log(
        target=loan,
        loan=loan,
        action_type="LOAN_RETURNED",
        actor=returned_by,
        source_screen=source_screen,
        reason=reason,
        severity=AuditSeverity.INCIDENT if days_late > 0 else AuditSeverity.INFO,
        metadata={
            "days_late": int(days_late),
            "fine_amount": str(fine_amount),
            "copy_barcode": copy.barcode,
        },
    )
    return loan


@transaction.atomic
def renew_loan(
    *,
    loan_id: int,
    renewed_by=None,
    source_screen: str = "api.circulation.renew",
    reason: str = "",
) -> Loan:
    loan = (
        Loan.objects.select_for_update()
        .select_related("member", "copy", "copy__book")
        .get(id=loan_id)
    )
    if loan.status != LoanStatus.ACTIVE:
        raise PolicyViolation("Only active loans can be renewed.")

    member = loan.member
    policy_snapshot = _get_policy_snapshot(member, loan.copy)
    _ensure_member_can_borrow(member, policy_snapshot)

    _expire_ready_holds(loan.copy.book_id)
    active_holds_exist = Hold.objects.filter(
        book_id=loan.copy.book_id,
        status__in=[HoldStatus.WAITING, HoldStatus.READY_FOR_PICKUP],
    ).exists()
    if active_holds_exist:
        raise PolicyViolation("Renewal not allowed because there are active holds for this book.")

    if loan.renew_count >= policy_snapshot.max_renewals:
        raise PolicyViolation("Maximum renewals reached.")

    old_due_at = loan.due_at
    loan.renew_count += 1
    loan.due_at = loan.due_at + timedelta(days=policy_snapshot.loan_period_days)
    loan.save(update_fields=["renew_count", "due_at", "updated_at"])
    _try_log(
        target=loan,
        loan=loan,
        action_type="LOAN_RENEWED",
        actor=renewed_by,
        source_screen=source_screen,
        reason=reason,
        metadata={
            "renew_count": int(loan.renew_count),
            "old_due_at": old_due_at.isoformat(),
            "new_due_at": loan.due_at.isoformat(),
        },
    )
    return loan


@transaction.atomic
def place_hold(*, member_no: str, book_id: int) -> Hold:
    member = MemberProfile.objects.select_for_update().get(member_no=member_no)
    if member.status in (MemberStatus.SUSPENDED, MemberStatus.BLOCKED):
        raise PolicyViolation("Member is not allowed to place holds (blocked/suspended).")

    existing = Hold.objects.filter(
        member=member,
        book_id=book_id,
        status__in=[HoldStatus.WAITING, HoldStatus.READY_FOR_PICKUP],
    ).exists()
    if existing:
        raise PolicyViolation("Member already has an active hold for this book.")

    max_pos = Hold.objects.filter(book_id=book_id).aggregate(m=Max("position"))["m"] or 0
    hold = Hold.objects.create(member=member, book_id=book_id, position=max_pos + 1, status=HoldStatus.WAITING)

    # If this is the only active hold and there is an available copy, assign immediately.
    active_queue_len = Hold.objects.filter(
        book_id=book_id, status__in=[HoldStatus.WAITING, HoldStatus.READY_FOR_PICKUP]
    ).count()
    if active_queue_len == 1:
        copy = (
            Copy.objects.select_for_update()
            .filter(book_id=book_id, status=CopyStatus.AVAILABLE, is_deleted=False)
            .order_by("id")
            .first()
        )
        if copy:
            policy, _ = LibraryPolicy.objects.get_or_create(name="default")
            now = timezone.now()
            expires = now + timedelta(hours=policy.hold_window_hours)

            hold.status = HoldStatus.READY_FOR_PICKUP
            hold.ready_at = now
            hold.expires_at = expires
            hold.save(update_fields=["status", "ready_at", "expires_at"])

            copy.status = CopyStatus.ON_HOLD
            copy.hold_for = member
            copy.hold_expires_at = expires
            copy.save(update_fields=["status", "hold_for", "hold_expires_at", "updated_at"])

    return hold


@transaction.atomic
def create_reservation_request(
    *,
    member_no: str,
    book_id: int,
    pickup_date: date,
    return_date: date,
    note: str = "",
    created_by=None,
    source_screen: str = "",
) -> ReservationRequest:
    member = MemberProfile.objects.select_for_update().get(member_no=member_no)
    if member.status in (MemberStatus.SUSPENDED, MemberStatus.BLOCKED):
        raise PolicyViolation("Anëtari nuk lejohet të bëjë kërkesa (i bllokuar/pezulluar).")

    pickup_date = _as_date(pickup_date)
    return_date = _as_date(return_date)
    if pickup_date > return_date:
        raise PolicyViolation("Datat janë të pavlefshme: data e marrjes nuk mund të jetë pas dorëzimit.")
    if pickup_date < timezone.now().date():
        raise PolicyViolation("Nuk mund të rezervosh për data të kaluara.")

    if ReservationRequest.objects.filter(
        member=member, book_id=book_id, status=ReservationRequestStatus.PENDING
    ).exists():
        raise PolicyViolation("Ke tashmë një kërkesë në pritje për këtë titull.")

    total, occupied = _book_capacity_for_range(book_id, pickup_date, return_date)
    if total > 0 and occupied >= total:
        raise PolicyViolation("Ky titull është i zënë në këto data (i rezervuar/huazuar).")

    try:
        req = ReservationRequest.objects.create(
            member=member,
            book_id=book_id,
            status=ReservationRequestStatus.PENDING,
            note=(note or "").strip(),
            pickup_date=pickup_date,
            return_date=return_date,
            created_by=created_by,
        )
        _try_log(
            target=req,
            action_type="RESERVATION_REQUEST_CREATED",
            actor=created_by,
            source_screen=source_screen or "system.reservation_request.create",
            metadata={
                "member_no": member.member_no,
                "book_id": int(book_id),
                "pickup_date": pickup_date.isoformat(),
                "return_date": return_date.isoformat(),
            },
        )
        return req
    except IntegrityError:
        # Safety for concurrent requests (unique pending constraint).
        raise PolicyViolation("Ke tashmë një kërkesë në pritje për këtë titull.")


@transaction.atomic
def approve_reservation_request(
    *,
    request_id: int,
    decided_by,
    source_screen: str = "",
    reason: str = "",
) -> ReservationRequest:
    req = (
        ReservationRequest.objects.select_for_update()
        .select_related("member", "book")
        .get(id=request_id)
    )
    if req.status != ReservationRequestStatus.PENDING:
        raise PolicyViolation("Vetëm kërkesat në pritje mund të pranohen.")

    try:
        if not req.pickup_date or not req.return_date:
            raise PolicyViolation("Kërkesa nuk ka data të plota.")

        # Re-check capacity for requested date range
        total, occupied = _book_capacity_for_range(req.book_id, req.pickup_date, req.return_date)
        if total > 0 and occupied >= total:
            raise PolicyViolation("Ky titull është i zënë në këto data (i rezervuar/huazuar).")

        # Create a reservation record for the requested range
        reservation = Reservation.objects.create(
            member=req.member,
            book=req.book,
            pickup_date=req.pickup_date,
            return_date=req.return_date,
            status=ReservationStatus.APPROVED,
            source_request=req,
            created_by=decided_by,
        )
        req.status = ReservationRequestStatus.APPROVED
        req.decided_at = timezone.now()
        req.decided_by = decided_by
        req.decision_reason = ""
        req.save(update_fields=["status", "decided_at", "decided_by", "decision_reason"])
        _try_log(
            target=req,
            action_type="RESERVATION_REQUEST_APPROVED",
            actor=decided_by,
            source_screen=source_screen or "system.reservation_request.approve",
            reason=reason,
            metadata={"reservation_id": reservation.id},
        )
        _try_log(
            target=reservation,
            action_type="RESERVATION_CREATED",
            actor=decided_by,
            source_screen=source_screen or "system.reservation.create",
            reason=reason,
            metadata={"request_id": req.id},
        )
        return req
    except PolicyViolation as e:
        # If hold cannot be created, mark as rejected with reason.
        req.status = ReservationRequestStatus.REJECTED
        req.decided_at = timezone.now()
        req.decided_by = decided_by
        req.decision_reason = str(e)
        req.save(update_fields=["status", "decided_at", "decided_by", "decision_reason"])
        _try_log(
            target=req,
            action_type="RESERVATION_REQUEST_REJECTED",
            actor=decided_by,
            source_screen=source_screen or "system.reservation_request.approve",
            reason=str(e),
            severity=AuditSeverity.INCIDENT,
        )
        return req


@transaction.atomic
def reject_reservation_request(
    *,
    request_id: int,
    decided_by,
    reason: str = "",
    source_screen: str = "",
) -> ReservationRequest:
    req = ReservationRequest.objects.select_for_update().get(id=request_id)
    if req.status != ReservationRequestStatus.PENDING:
        raise PolicyViolation("Vetëm kërkesat në pritje mund të refuzohen.")

    req.status = ReservationRequestStatus.REJECTED
    req.decided_at = timezone.now()
    req.decided_by = decided_by
    req.decision_reason = (reason or "").strip() or "Refuzuar nga stafi."
    req.save(update_fields=["status", "decided_at", "decided_by", "decision_reason"])
    _try_log(
        target=req,
        action_type="RESERVATION_REQUEST_REJECTED",
        actor=decided_by,
        source_screen=source_screen or "system.reservation_request.reject",
        reason=req.decision_reason,
        severity=AuditSeverity.INCIDENT,
    )
    return req


@transaction.atomic
def borrow_from_reservation(
    *,
    reservation_id: int,
    decided_by=None,
    source_screen: str = "",
    reason: str = "",
) -> Loan:
    """
    Convert an approved reservation into an actual loan (member picked up).
    Picks the first available copy of the book.
    """
    reservation = (
        Reservation.objects.select_for_update()
        .select_related("member", "book")
        .get(id=reservation_id)
    )
    if reservation.status != ReservationStatus.APPROVED:
        raise PolicyViolation("Vetëm rezervimet e pranuara mund të huazohen.")

    # pick an available copy
    copy = (
        Copy.objects.select_for_update()
        .select_related("book")
        .filter(book_id=reservation.book_id, status=CopyStatus.AVAILABLE, is_deleted=False)
        .order_by("id")
        .first()
    )
    if not copy:
        raise PolicyViolation("S’ka kopje të lirë për këtë titull në këtë moment.")

    member = reservation.member
    policy = _get_policy_snapshot(member, copy)
    _ensure_member_can_borrow(member, policy)

    # due_at uses reservation.return_date end of day
    due_at = timezone.make_aware(datetime.combine(reservation.return_date, time(23, 59, 0)))
    now = timezone.now()

    loan = Loan.objects.create(
        member=member,
        copy=copy,
        due_at=due_at,
        status=LoanStatus.ACTIVE,
        loaned_by=decided_by,
    )
    copy.status = CopyStatus.ON_LOAN
    copy.hold_for = None
    copy.hold_expires_at = None
    copy.save(update_fields=["status", "hold_for", "hold_expires_at", "updated_at"])

    reservation.status = ReservationStatus.BORROWED
    reservation.loan = loan
    reservation.borrowed_by = decided_by
    reservation.save(update_fields=["status", "loan", "borrowed_by", "updated_at"])
    _try_log(
        target=reservation,
        loan=loan,
        action_type="RESERVATION_BORROWED",
        actor=decided_by,
        source_screen=source_screen or "system.reservation.borrow",
        reason=reason,
        metadata={"loan_id": loan.id},
    )
    _try_log(
        target=loan,
        loan=loan,
        action_type="LOAN_CREATED_FROM_RESERVATION",
        actor=decided_by,
        source_screen=source_screen or "system.loan.create_from_reservation",
        reason=reason,
        metadata={"reservation_id": reservation.id, "request_id": reservation.source_request_id},
    )
    return loan


@transaction.atomic
def quick_checkout_by_national_id(
    *,
    national_id: str,
    book_id: int,
    pickup_date: date,
    return_date: date,
    note: str = "",
    loaned_by=None,
    source_screen: str = "",
    reason: str = "",
) -> Loan:
    nid = (national_id or "").strip()
    if not nid:
        raise PolicyViolation("Vendos Nr. ID të anëtarit.")

    members = MemberProfile.objects.select_for_update().filter(national_id=nid)
    if not members.exists():
        raise PolicyViolation("Nuk u gjet anëtar me këtë Nr. ID.")
    if members.count() > 1:
        raise PolicyViolation("Ka më shumë se 1 anëtar me këtë Nr. ID. Korrigjo të dhënat.")
    member = members.first()

    pickup_date = _as_date(pickup_date)
    return_date = _as_date(return_date)
    if pickup_date > return_date:
        raise PolicyViolation("Datat janë të pavlefshme: marrja nuk mund të jetë pas dorëzimit.")
    if pickup_date < timezone.now().date():
        raise PolicyViolation("Nuk mund të huazosh për data të kaluara.")

    availability = get_book_availability_for_range(book_id, pickup_date, return_date)
    if availability["total"] <= 0:
        raise PolicyViolation("Ky titull s’ka kopje në inventar.")
    # This checkout will occupy one copy for this range.
    if availability["occupied"] + 1 > availability["total"]:
        raise PolicyViolation("Ky titull është i zënë në këto data (i rezervuar/huazuar).")

    copy = (
        Copy.objects.select_for_update()
        .select_related("book")
        .filter(book_id=book_id, status=CopyStatus.AVAILABLE, is_deleted=False)
        .order_by("id")
        .first()
    )
    if not copy:
        raise PolicyViolation("S’ka kopje të lirë për këtë titull në këtë moment.")

    policy = _get_policy_snapshot(member, copy)
    _ensure_member_can_borrow(member, policy)

    due_at = timezone.make_aware(datetime.combine(return_date, time(23, 59, 0)))
    loan = Loan.objects.create(
        member=member,
        copy=copy,
        due_at=due_at,
        status=LoanStatus.ACTIVE,
        note=(note or "").strip(),
        loaned_by=loaned_by,
    )
    copy.status = CopyStatus.ON_LOAN
    copy.hold_for = None
    copy.hold_expires_at = None
    copy.save(update_fields=["status", "hold_for", "hold_expires_at", "updated_at"])
    _try_log(
        target=loan,
        loan=loan,
        action_type="LOAN_CREATED_QUICK",
        actor=loaned_by,
        source_screen=source_screen or "admin.loan.quick_modal",
        reason=reason or note,
        metadata={
            "member_no": member.member_no,
            "book_id": int(book_id),
            "copy_barcode": copy.barcode,
            "pickup_date": pickup_date.isoformat(),
            "return_date": return_date.isoformat(),
        },
    )
    return loan

