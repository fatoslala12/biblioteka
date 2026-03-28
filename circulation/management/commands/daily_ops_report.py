import json
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from circulation.models import Loan, LoanStatus, Reservation, ReservationRequest, ReservationRequestStatus, ReservationStatus
from fines.models import Fine, FineStatus
from policies.models import LibraryPolicy


class Command(BaseCommand):
    help = "Raport ditor operacional për adminin (huazime, rezervime, kërkesa, gjoba)."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON.")
        parser.add_argument(
            "--save-file",
            dest="save_file",
            default="",
            help="Save report JSON to a file path (creates parent dirs).",
        )
        parser.add_argument(
            "--send-email",
            action="store_true",
            dest="send_email",
            help="Send report by email.",
        )
        parser.add_argument(
            "--email-to",
            action="append",
            dest="email_to",
            default=[],
            help="Recipient email (use multiple times for many recipients).",
        )

    def _expiring_soon_count(self, *, now, warning_hours: int, grace_days: int) -> int:
        if warning_hours <= 0:
            return 0
        warning_until = now + timedelta(hours=warning_hours)
        count = 0
        pickup_dates = Reservation.objects.filter(
            status=ReservationStatus.APPROVED,
            loan__isnull=True,
        ).values_list("pickup_date", flat=True)
        for pickup_date in pickup_dates:
            expiry_date = pickup_date + timedelta(days=grace_days)
            expiry_dt = timezone.make_aware(datetime.combine(expiry_date, time(23, 59, 59)))
            if now < expiry_dt <= warning_until:
                count += 1
        return count

    def _render_text_report(self, report: dict) -> str:
        policy = report["policy"]
        loans = report["loans"]
        reservations = report["reservations"]
        requests = report["reservation_requests"]
        fines = report["fines"]
        lines = [
            "=== Daily Ops Report ===",
            f"Generated at: {report['generated_at']}",
            f"Policy -> grace_days: {policy['reservation_grace_days']}, warning_hours: {policy['reservation_warning_hours']}",
            f"Loans -> active: {loans['active']}, overdue: {loans['overdue']}",
            (
                "Reservations -> approved_open: "
                f"{reservations['approved_open']}, expiring_soon: {reservations['expiring_soon']}, "
                f"overdue_candidates: {reservations['overdue_auto_expire_candidates']}"
            ),
            f"Reservation requests -> pending: {requests['pending']}",
            f"Fines -> unpaid_count: {fines['unpaid_count']}, unpaid_total: {fines['unpaid_total']}",
        ]
        return "\n".join(lines)

    def _save_report_file(self, *, report: dict, output_file: str) -> None:
        path = Path(output_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _send_report_email(self, *, report: dict, recipients: list[str]) -> int:
        subject = "Daily Ops Report - Smart Library"
        body = self._render_text_report(report)
        sender = getattr(settings, "DEFAULT_FROM_EMAIL", "") or "no-reply@localhost"
        return send_mail(
            subject=subject,
            message=body,
            from_email=sender,
            recipient_list=recipients,
            fail_silently=False,
        )

    def handle(self, *args, **options):
        now = timezone.now()
        today = timezone.localdate()

        policy, _ = LibraryPolicy.objects.get_or_create(name="default")
        grace_days = int(policy.reservation_grace_days or 0)
        warning_hours = int(policy.reservation_warning_hours or 0)
        cutoff_pickup_date = today - timedelta(days=grace_days)

        overdue_loans = Loan.objects.filter(status=LoanStatus.ACTIVE, due_at__lt=now).count()
        active_loans = Loan.objects.filter(status=LoanStatus.ACTIVE).count()
        pending_requests = ReservationRequest.objects.filter(status=ReservationRequestStatus.PENDING).count()

        approved_reservations = Reservation.objects.filter(status=ReservationStatus.APPROVED, loan__isnull=True).count()
        overdue_reservations = Reservation.objects.filter(
            status=ReservationStatus.APPROVED,
            loan__isnull=True,
            pickup_date__lt=cutoff_pickup_date,
        ).count()
        expiring_soon = self._expiring_soon_count(
            now=now,
            warning_hours=warning_hours,
            grace_days=grace_days,
        )

        unpaid_fines_qs = Fine.objects.filter(status=FineStatus.UNPAID)
        unpaid_fines_count = unpaid_fines_qs.count()
        unpaid_fines_total = unpaid_fines_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        report = {
            "generated_at": timezone.localtime(now).isoformat(),
            "policy": {
                "reservation_grace_days": grace_days,
                "reservation_warning_hours": warning_hours,
            },
            "loans": {
                "active": active_loans,
                "overdue": overdue_loans,
            },
            "reservations": {
                "approved_open": approved_reservations,
                "overdue_auto_expire_candidates": overdue_reservations,
                "expiring_soon": expiring_soon,
            },
            "reservation_requests": {
                "pending": pending_requests,
            },
            "fines": {
                "unpaid_count": unpaid_fines_count,
                "unpaid_total": str(unpaid_fines_total),
            },
        }

        save_file = (options.get("save_file") or "").strip()
        if save_file:
            self._save_report_file(report=report, output_file=save_file)
            self.stdout.write(self.style.SUCCESS(f"Raporti u ruajt te: {save_file}"))

        send_email_requested = bool(options.get("send_email"))
        cli_recipients = [e.strip() for e in (options.get("email_to") or []) if (e or "").strip()]
        default_recipients = [e.strip() for e in getattr(settings, "OPS_REPORT_RECIPIENTS", []) if (e or "").strip()]
        recipients = cli_recipients or default_recipients
        if send_email_requested:
            if not recipients:
                self.stdout.write(self.style.WARNING("Asnjë email për dërgim. Shto --email-to ose OPS_REPORT_RECIPIENTS."))
            else:
                sent = self._send_report_email(report=report, recipients=recipients)
                self.stdout.write(self.style.SUCCESS(f"Raporti u dërgua me email ({sent} mesazh/e)."))

        if options.get("as_json"):
            self.stdout.write(json.dumps(report, ensure_ascii=False))
            return

        self.stdout.write(self._render_text_report(report))
