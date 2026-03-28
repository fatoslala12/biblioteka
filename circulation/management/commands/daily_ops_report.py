import json
from datetime import datetime, time, timedelta
from decimal import Decimal

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

        if options.get("as_json"):
            self.stdout.write(json.dumps(report, ensure_ascii=False))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("=== Daily Ops Report ==="))
        self.stdout.write(f"Generated at: {report['generated_at']}")
        self.stdout.write(f"Policy -> grace_days: {grace_days}, warning_hours: {warning_hours}")
        self.stdout.write(f"Loans -> active: {active_loans}, overdue: {overdue_loans}")
        self.stdout.write(
            "Reservations -> approved_open: "
            f"{approved_reservations}, expiring_soon: {expiring_soon}, "
            f"overdue_candidates: {overdue_reservations}"
        )
        self.stdout.write(f"Reservation requests -> pending: {pending_requests}")
        self.stdout.write(f"Fines -> unpaid_count: {unpaid_fines_count}, unpaid_total: {unpaid_fines_total}")
