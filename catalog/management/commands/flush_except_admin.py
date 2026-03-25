"""
Fshin të gjitha të dhënat e aplikacionit por ruan përdoruesit admin (staff/superuser).
Përdorim: python manage.py flush_except_admin [--no-input]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from accounts.models import MemberProfile, User
from audit.models import AuditEntry
from catalog.models import Author, Book, Copy, Genre, Publisher, Tag
from circulation.models import Hold, Loan, Reservation, ReservationRequest
from cms.models import Announcement, ContactMessage, Event, Video
from fines.models import Fine, Payment
from policies.models import LoanRule, LibraryPolicy


class Command(BaseCommand):
    help = "Fshin të gjitha të dhënat por ruan përdoruesit admin (staff/superuser)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Ekzekuto pa kërkuar konfirmim",
        )

    def handle(self, *args, **options):
        if not options["no_input"]:
            confirm = input(
                "Do të fshihen të gjitha të dhënat (libra, anëtarë, huazime, etj.) përveç llogarive admin. Vazhdoj? (po/jo): "
            )
            if confirm.lower() not in ("po", "yes", "p", "y"):
                self.stdout.write("Anuluar.")
                return

        with transaction.atomic():
            # 1. Gjoba dhe pagesa
            Payment.objects.all().delete()
            Fine.objects.all().delete()

            # 2. Audit
            AuditEntry.objects.all().delete()

            # 3. Rezervime (para huazimeve për shkak të OneToOne loan)
            Reservation.objects.all().update(loan_id=None)
            Reservation.objects.all().delete()
            ReservationRequest.objects.all().delete()
            Hold.objects.all().delete()

            # 4. Huazime
            Loan.objects.all().delete()

            # 5. Kopje dhe libra
            Copy.objects.all().delete()
            Book.objects.all().delete()

            # 6. Autorë, zhanre, botues, etiketa
            Author.objects.all().delete()
            Genre.objects.all().delete()
            Publisher.objects.all().delete()
            Tag.objects.all().delete()

            # 7. CMS
            ContactMessage.objects.all().delete()
            Announcement.objects.all().delete()
            Event.objects.all().delete()
            Video.objects.all().delete()

            # 8. Profile anëtarësh (fshijmë të gjitha)
            MemberProfile.objects.all().delete()

            # 9. Politika (mund të kërkohet një 'default' më vonë)
            LoanRule.objects.all().delete()
            LibraryPolicy.objects.all().delete()

            # 10. Fshij përdoruesit që NUK janë admin (staff ose superuser)
            non_admin = User.objects.filter(is_staff=False, is_superuser=False)
            non_admin.delete()

        admin_count = User.objects.filter(
            Q(is_staff=True) | Q(is_superuser=True)
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"U krye. U fshinë huazime, libra, kopje, anëtarë, gjoba, etj. "
                f"Mbetën {admin_count} llogari admin."
            )
        )
