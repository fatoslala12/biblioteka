from __future__ import annotations

import logging
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserRole
from notifications.models import NotificationKind, UserNotification

logger = logging.getLogger(__name__)
User = get_user_model()


def _safe(fn):
    try:
        fn()
    except Exception:
        logger.exception("In-app notification failed")


def staff_recipient_users() -> list[User]:
    qs = (
        User.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(is_staff=True) | Q(role__in=(UserRole.ADMIN, UserRole.STAFF)))
        .distinct()
    )
    return list(qs)


def create_for_users(
    users: Iterable[User],
    *,
    kind: str,
    title: str,
    body: str = "",
    link_url: str = "",
) -> None:
    rows = [
        UserNotification(user=u, kind=kind, title=title[:220], body=body or "", link_url=(link_url or "")[:500])
        for u in users
        if u and u.pk
    ]
    if rows:
        UserNotification.objects.bulk_create(rows, batch_size=100)


def notify_staff_new_reservation_request(req) -> None:
    """Kërkesë e re rezervimi — njofto stafin."""
    member_label = (req.member.full_name or "").strip() or req.member.member_no
    title = f"Kërkesë e re: {req.book.title}"
    body = (
        f"{member_label} · marrje {req.pickup_date.strftime('%d/%m/%Y') if req.pickup_date else '—'} · "
        f"kthim {req.return_date.strftime('%d/%m/%Y') if req.return_date else '—'}"
    )
    link = f"/admin/circulation/reservationrequest/{req.id}/change/"

    def _go():
        create_for_users(
            staff_recipient_users(),
            kind=NotificationKind.RESERVATION_NEW_STAFF,
            title=title,
            body=body,
            link_url=link,
        )

    _safe(_go)


def notify_staff_member_cancelled_request(req) -> None:
    member_label = (req.member.full_name or "").strip() or req.member.member_no
    title = f"Kërkesë e anuluar: {req.book.title}"
    body = f"{member_label} anuloi kërkesën #{req.id}."
    link = f"/admin/circulation/reservationrequest/{req.id}/change/"

    def _go():
        create_for_users(
            staff_recipient_users(),
            kind=NotificationKind.RESERVATION_CANCELLED_STAFF,
            title=title,
            body=body,
            link_url=link,
        )

    _safe(_go)


def notify_staff_new_member_signup(*, member_profile) -> None:
    member_no = (getattr(member_profile, "member_no", "") or "").strip() or "—"
    full_name = (getattr(member_profile, "full_name", "") or "").strip() or "Anëtar i ri"
    user = getattr(member_profile, "user", None)
    username = getattr(user, "username", "") if user else ""
    title = f"Anëtar i ri: {full_name}"
    body = f"U shtua anëtari {full_name} ({member_no}){f' · {username}' if username else ''}."
    link = f"/admin/accounts/memberprofile/{member_profile.id}/change/"

    def _go():
        create_for_users(
            staff_recipient_users(),
            kind=NotificationKind.MEMBER_NEW_STAFF,
            title=title,
            body=body,
            link_url=link,
        )

    _safe(_go)


def notify_member_user(user, *, kind: str, title: str, body: str = "", link_url: str = "") -> None:
    if not user or not user.pk:
        return

    def _go():
        UserNotification.objects.create(
            user=user,
            kind=kind,
            title=title[:220],
            body=body or "",
            link_url=(link_url or "")[:500],
        )

    _safe(_go)


def notify_member_reservation_submitted(req) -> None:
    u = getattr(req.member, "user", None)
    if not u:
        return
    title = "Kërkesa për rezervim u dërgua"
    body = (
        f"Stafi do ta shqyrtojë kërkesën për “{req.book.title}”. "
        f"Datat: marrje {req.pickup_date.strftime('%d/%m/%Y') if req.pickup_date else '—'}, "
        f"dorëzim {req.return_date.strftime('%d/%m/%Y') if req.return_date else '—'}."
    )
    notify_member_user(
        u,
        kind=NotificationKind.RESERVATION_SUBMITTED_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-reservations",
    )


def notify_member_reservation_approved(req, reservation_id: int) -> None:
    u = getattr(req.member, "user", None)
    if not u:
        return
    title = "Rezervimi u pranua"
    body = (
        f"“{req.book.title}” është i rezervuar për ju. "
        f"Merrni librin më {req.pickup_date.strftime('%d/%m/%Y') if req.pickup_date else '—'}; "
        f"dorëzimi deri më {req.return_date.strftime('%d/%m/%Y') if req.return_date else '—'}."
    )
    notify_member_user(
        u,
        kind=NotificationKind.RESERVATION_APPROVED_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-reservations",
    )


def notify_member_reservation_rejected(req) -> None:
    u = getattr(req.member, "user", None)
    if not u:
        return
    title = "Kërkesa nuk u pranua"
    reason = (req.decision_reason or "").strip() or "Pa arsye të detajuar."
    body = f"“{req.book.title}”: {reason}"
    notify_member_user(
        u,
        kind=NotificationKind.RESERVATION_REJECTED_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-reservations",
    )


def notify_member_hold_ready(member, *, book_title: str, expires_at) -> None:
    u = getattr(member, "user", None)
    if not u:
        return
    exp = timezone.localtime(expires_at).strftime("%d/%m/%Y %H:%M") if expires_at else "—"
    title = "Libri është gati për marrje"
    body = f"“{book_title}” mund të merret në bibliotekë. Afati për marrje: {exp}."
    notify_member_user(
        u,
        kind=NotificationKind.HOLD_READY_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-active-loans",
    )


def notify_member_loan_active(member, *, book_title: str, due_at) -> None:
    u = getattr(member, "user", None)
    if not u:
        return
    due = timezone.localtime(due_at).strftime("%d/%m/%Y %H:%M") if due_at else "—"
    title = "Huazimi filloi"
    body = f"“{book_title}” është në huazim. Afati i kthimit: {due}."
    notify_member_user(
        u,
        kind=NotificationKind.LOAN_ACTIVE_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-active-loans",
    )


def notify_member_loan_returned(member, *, book_title: str) -> None:
    u = getattr(member, "user", None)
    if not u:
        return
    title = "Libri u kthye me sukses"
    body = f"“{book_title}” është regjistruar si i kthyer. Faleminderit!"
    notify_member_user(
        u,
        kind=NotificationKind.LOAN_RETURNED_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/",
    )


def notify_member_loan_renewed(member, *, book_title: str, new_due_at) -> None:
    u = getattr(member, "user", None)
    if not u:
        return
    due = timezone.localtime(new_due_at).strftime("%d/%m/%Y %H:%M") if new_due_at else "—"
    title = "Afati i huazimit u zgjat"
    body = f"“{book_title}”: afati i ri i kthimit është {due}."
    notify_member_user(
        u,
        kind=NotificationKind.LOAN_RENEWED_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-active-loans",
    )


def notify_member_loan_due_tomorrow(member, *, book_title: str, due_at) -> None:
    u = getattr(member, "user", None)
    if not u:
        return
    due = timezone.localtime(due_at).strftime("%d/%m/%Y %H:%M") if due_at else "—"
    title = "Kujtesë: nesër është afati i kthimit"
    body = f"“{book_title}” duhet të kthehet më {due}. Faleminderit që respektoni afatin."
    notify_member_user(
        u,
        kind=NotificationKind.LOAN_DUE_TOMORROW_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-active-loans",
    )


def notify_member_reservation_pickup_tomorrow(member, *, book_title: str, pickup_date) -> None:
    u = getattr(member, "user", None)
    if not u:
        return
    pd = pickup_date.strftime("%d/%m/%Y") if pickup_date else "—"
    title = "Kujtesë: nesër merrni librin"
    body = f"Keni rezervimin “{book_title}” — nesër ({pd}) është dita e marrjes në bibliotekë."
    notify_member_user(
        u,
        kind=NotificationKind.RESERVATION_PICKUP_TOMORROW_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-reservations",
    )


def notify_member_reservation_expired(member, *, book_title: str) -> None:
    u = getattr(member, "user", None)
    if not u:
        return
    title = "Rezervimi skadoi"
    body = f"Rezervimi për “{book_title}” u mbyll automatikisht sepse libri nuk u mor në datën e caktuar."
    notify_member_user(
        u,
        kind=NotificationKind.RESERVATION_EXPIRED_MEMBER,
        title=title,
        body=body,
        link_url="/anetar/#member-reservations",
    )
