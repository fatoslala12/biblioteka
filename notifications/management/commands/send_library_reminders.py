"""
Dërgon njoftime në-app një ditë para:
- afatit të kthimit të huazimit aktiv
- datës së marrjes së rezervimit të pranuar (pa huazim ende)

Vendos në cron (p.sh. çdo ditë 08:00):
  python manage.py send_library_reminders
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from circulation.models import Loan, LoanStatus, Reservation, ReservationStatus
from notifications.services import notify_member_loan_due_tomorrow, notify_member_reservation_pickup_tomorrow


class Command(BaseCommand):
    help = "Njoftime anëtarëve: nesër afat kthimi / nesër marrje rezervimi."

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        loan_sent = 0
        res_sent = 0

        qs_loans = (
            Loan.objects.filter(status=LoanStatus.ACTIVE, due_at__date=tomorrow)
            .exclude(due_soon_reminder_for=tomorrow)
            .select_related("member", "copy", "copy__book")
        )
        for loan in qs_loans:
            notify_member_loan_due_tomorrow(loan.member, book_title=loan.copy.book.title, due_at=loan.due_at)
            Loan.objects.filter(pk=loan.pk).update(due_soon_reminder_for=tomorrow)
            loan_sent += 1

        qs_res = (
            Reservation.objects.filter(
                status=ReservationStatus.APPROVED, loan__isnull=True, pickup_date=tomorrow
            )
            .exclude(pickup_soon_reminder_for=tomorrow)
            .select_related("member", "book")
        )
        for res in qs_res:
            notify_member_reservation_pickup_tomorrow(
                res.member, book_title=res.book.title, pickup_date=res.pickup_date
            )
            Reservation.objects.filter(pk=res.pk).update(pickup_soon_reminder_for=tomorrow)
            res_sent += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"U dërguan njoftime: huazime (afat nesër)={loan_sent}, rezervime (marrje nesër)={res_sent}."
            )
        )
