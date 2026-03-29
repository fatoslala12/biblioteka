import json
from datetime import timedelta
from datetime import datetime, time
from urllib import request as urlrequest

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from audit.models import AuditEntry
from audit.models import AuditSeverity
from audit.services import log_audit_event
from circulation.models import Loan, LoanStatus, Reservation, ReservationStatus
from fines.models import Fine, FineStatus
from policies.models import LibraryPolicy


class Command(BaseCommand):
    help = "Dërgon njoftime automatike për anëtarët (afat kthimi, gjobë e re, rezervim që skadon)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--channels",
            choices=["both", "email", "sms"],
            default="both",
            help="Channel i dërgimit të njoftimeve.",
        )
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")

    def _already_notified(self, *, action_type: str, reason_token: str) -> bool:
        return AuditEntry.objects.filter(
            action_type=action_type,
            source_screen="system.notifications.member",
            reason=reason_token,
        ).exists()

    def _send_sms(self, *, phone: str, message: str) -> tuple[bool, str]:
        webhook = (getattr(settings, "SMS_WEBHOOK_URL", "") or "").strip()
        if not webhook:
            return False, "SMS webhook not configured."
        payload = {"to": phone, "message": message}
        headers = {"Content-Type": "application/json"}
        token = (getattr(settings, "SMS_WEBHOOK_TOKEN", "") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urlrequest.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=8) as resp:
                code = getattr(resp, "status", 200)
                if int(code) >= 400:
                    return False, f"SMS provider returned status {code}."
        except Exception as exc:
            return False, f"SMS send failed: {exc}"
        return True, ""

    def _notify_member(
        self,
        *,
        member,
        action_type: str,
        reason_token: str,
        subject: str,
        message: str,
        html_body: str = "",
        channels: str,
        dry_run: bool,
        metadata: dict,
    ) -> dict:
        email = ((getattr(member, "user", None) and (member.user.email or "")) or "").strip()
        phone = (member.phone or "").strip()
        delivered_email = False
        delivered_sms = False
        failures = []

        if channels in ("both", "email"):
            if email:
                if not dry_run:
                    mail = EmailMultiAlternatives(
                        subject=subject,
                        body=message,
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost"),
                        to=[email],
                    )
                    if html_body:
                        mail.attach_alternative(html_body, "text/html")
                    mail.send(fail_silently=False)
                delivered_email = True
            else:
                failures.append("missing email")

        if channels in ("both", "sms"):
            if phone:
                if not dry_run:
                    ok, err = self._send_sms(phone=phone, message=message)
                else:
                    ok, err = True, ""
                delivered_sms = bool(ok)
                if not ok and err:
                    failures.append(err)
            else:
                failures.append("missing phone")

        severity = AuditSeverity.INFO if (delivered_email or delivered_sms) else AuditSeverity.INCIDENT
        if not dry_run:
            log_audit_event(
                target=member,
                action_type=action_type,
                actor=None,
                source_screen="system.notifications.member",
                reason=reason_token,
                severity=severity,
                metadata={
                    **metadata,
                    "email": email,
                    "phone": phone,
                    "channels_requested": channels,
                    "delivered_email": delivered_email,
                    "delivered_sms": delivered_sms,
                    "failures": failures,
                },
            )
        return {
            "delivered_email": delivered_email,
            "delivered_sms": delivered_sms,
            "failures": failures,
        }

    def handle(self, *args, **options):
        channels = options.get("channels") or "both"
        dry_run = bool(options.get("dry_run"))
        now = timezone.now()
        today = timezone.localdate()
        due_days = int(getattr(settings, "NOTIFY_DUE_SOON_DAYS", 2) or 2)
        fine_lookback_days = int(getattr(settings, "NOTIFY_FINE_CREATED_LOOKBACK_DAYS", 3) or 3)
        reservation_warning_hours = int(getattr(settings, "NOTIFY_RESERVATION_EXPIRY_HOURS", 24) or 24)

        policy, _ = LibraryPolicy.objects.get_or_create(name="default")
        grace_days = int(policy.reservation_grace_days or 0)

        sent_count = 0
        skipped_count = 0

        # 1) Loan due soon
        due_limit = today + timedelta(days=max(0, due_days))
        due_loans = (
            Loan.objects.select_related("member", "member__user", "copy", "copy__book")
            .filter(status=LoanStatus.ACTIVE, due_at__date__gte=today, due_at__date__lte=due_limit)
            .order_by("due_at")
        )
        for loan in due_loans:
            token = f"loan:{loan.id}:due_soon:{today.isoformat()}"
            if self._already_notified(action_type="MEMBER_NOTIFICATION_DUE_SOON", reason_token=token):
                skipped_count += 1
                continue
            msg = (
                f"Përshëndetje {loan.member.full_name or loan.member.member_no},\n\n"
                f"Afati i kthimit për librin '{loan.copy.book.title}' po afrohet: "
                f"{timezone.localtime(loan.due_at).strftime('%d/%m/%Y %H:%M')}.\n"
                "Ju lutem dorëzojeni në kohë për të shmangur gjobat.\n\n"
                "Smart Library"
            )
            html_body = render_to_string(
                "emails/member_notification.html",
                {
                    "title": "Afati i kthimit po afrohet",
                    "subject": "Afati i kthimit po afrohet",
                    "member_name": loan.member.full_name or loan.member.member_no,
                    "body": (
                        f"Afati i kthimit për librin <b>{loan.copy.book.title}</b> po afrohet: "
                        f"{timezone.localtime(loan.due_at).strftime('%d/%m/%Y %H:%M')}."
                    ),
                    "cta_text": "Hap huazimet",
                    "cta_url": "/anetar/",
                    "library_name": "Smart Library • Biblioteka Kamëz",
                },
            )
            res = self._notify_member(
                member=loan.member,
                action_type="MEMBER_NOTIFICATION_DUE_SOON",
                reason_token=token,
                subject="Afati i kthimit po afrohet",
                message=msg,
                html_body=html_body,
                channels=channels,
                dry_run=dry_run,
                metadata={"loan_id": loan.id, "due_at": loan.due_at.isoformat()},
            )
            if res["delivered_email"] or res["delivered_sms"]:
                sent_count += 1

        # 2) New fines
        fine_since = now - timedelta(days=max(1, fine_lookback_days))
        fines = Fine.objects.select_related("member", "member__user", "loan", "loan__copy", "loan__copy__book").filter(
            status=FineStatus.UNPAID, created_at__gte=fine_since
        )
        for fine in fines:
            token = f"fine:{fine.id}:created"
            if self._already_notified(action_type="MEMBER_NOTIFICATION_FINE_CREATED", reason_token=token):
                skipped_count += 1
                continue
            msg = (
                f"Përshëndetje {fine.member.full_name or fine.member.member_no},\n\n"
                f"Është krijuar një gjobë e re prej {fine.amount} € për huazimin "
                f"'{fine.loan.copy.book.title}'.\n"
                "Ju lutem kryeni pagesën sa më shpejt për të shmangur kufizimet e huazimit.\n\n"
                "Smart Library"
            )
            html_body = render_to_string(
                "emails/member_notification.html",
                {
                    "title": "Njoftim për gjobë të re",
                    "subject": "Njoftim për gjobë të re",
                    "member_name": fine.member.full_name or fine.member.member_no,
                    "body": (
                        f"Është krijuar një gjobë e re prej <b>{fine.amount} €</b> për librin "
                        f"<b>{fine.loan.copy.book.title}</b>."
                    ),
                    "cta_text": "Shiko gjobat",
                    "cta_url": "/anetar/",
                    "library_name": "Smart Library • Biblioteka Kamëz",
                },
            )
            res = self._notify_member(
                member=fine.member,
                action_type="MEMBER_NOTIFICATION_FINE_CREATED",
                reason_token=token,
                subject="Njoftim për gjobë të re",
                message=msg,
                html_body=html_body,
                channels=channels,
                dry_run=dry_run,
                metadata={"fine_id": fine.id, "amount": str(fine.amount)},
            )
            if res["delivered_email"] or res["delivered_sms"]:
                sent_count += 1

        # 3) Reservation expiring soon
        reservations = Reservation.objects.select_related("member", "member__user", "book").filter(
            status=ReservationStatus.APPROVED,
            loan__isnull=True,
        )
        for reservation in reservations:
            expiry_date = reservation.pickup_date + timedelta(days=grace_days)
            expiry_dt = timezone.make_aware(datetime.combine(expiry_date, time(23, 59, 59)))
            seconds_left = int((expiry_dt - now).total_seconds())
            if seconds_left <= 0 or seconds_left > reservation_warning_hours * 3600:
                continue
            token = f"reservation:{reservation.id}:expiring:{today.isoformat()}"
            if self._already_notified(action_type="MEMBER_NOTIFICATION_RESERVATION_EXPIRING", reason_token=token):
                skipped_count += 1
                continue
            msg = (
                f"Përshëndetje {reservation.member.full_name or reservation.member.member_no},\n\n"
                f"Rezervimi për librin '{reservation.book.title}' po skadon më "
                f"{expiry_dt.strftime('%d/%m/%Y %H:%M')}.\n"
                "Ju lutem paraqituni sa më shpejt për ta marrë librin.\n\n"
                "Smart Library"
            )
            html_body = render_to_string(
                "emails/member_notification.html",
                {
                    "title": "Rezervimi juaj po skadon",
                    "subject": "Rezervimi juaj po skadon",
                    "member_name": reservation.member.full_name or reservation.member.member_no,
                    "body": (
                        f"Rezervimi për librin <b>{reservation.book.title}</b> po skadon më "
                        f"{expiry_dt.strftime('%d/%m/%Y %H:%M')}."
                    ),
                    "cta_text": "Hap rezervimet",
                    "cta_url": "/anetar/",
                    "library_name": "Smart Library • Biblioteka Kamëz",
                },
            )
            res = self._notify_member(
                member=reservation.member,
                action_type="MEMBER_NOTIFICATION_RESERVATION_EXPIRING",
                reason_token=token,
                subject="Rezervimi juaj po skadon",
                message=msg,
                html_body=html_body,
                channels=channels,
                dry_run=dry_run,
                metadata={"reservation_id": reservation.id, "expires_at": expiry_dt.isoformat()},
            )
            if res["delivered_email"] or res["delivered_sms"]:
                sent_count += 1

        mode = "DRY RUN" if dry_run else "LIVE"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: njoftime të dërguara={sent_count}, të anashkaluara (already-notified)={skipped_count}, channels={channels}"
            )
        )
