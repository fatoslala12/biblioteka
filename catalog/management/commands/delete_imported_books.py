"""
Fshin librat e importuar (me kopje barkod IMP-*) dhe të gjitha të dhënat e tyre.
Ose librat jo-shqip kur përdoret --non-shqip.
Përdorim: python manage.py delete_imported_books [--non-shqip] [--no-input]
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.models import Book, Copy
from circulation.models import Hold, Loan, Reservation, ReservationRequest
from fines.models import Fine, Payment


class Command(BaseCommand):
    help = "Fshin librat e importuar (me kopje IMP-*) ose librat jo-shqip (--non-shqip)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Ekzekuto pa kërkuar konfirmim",
        )
        parser.add_argument(
            "--non-shqip",
            action="store_true",
            help="Fshin librat me gjuhë të ndryshme nga Shqip (p.sh. Anglisht, English, etj.)",
        )

    def handle(self, *args, **options):
        if options["non_shqip"]:
            # Librat ku gjuha nuk është Shqip (bosh, anglisht, etj.)
            books = Book.objects.filter(
                is_deleted=False
            ).exclude(
                Q(language__iexact="shqip") | Q(language__iexact="albanian")
            )
        else:
            imp_copies = Copy.objects.filter(barcode__startswith="IMP-", is_deleted=False)
            book_ids = imp_copies.values_list("book_id", flat=True).distinct()
            books = Book.objects.filter(id__in=book_ids, is_deleted=False)

        count = books.count()
        if count == 0:
            mode = "jo-shqip" if options["non_shqip"] else "të importuar"
            self.stdout.write(self.style.SUCCESS(f"Nuk ka libra {mode} për fshirje."))
            return

        if not options["no_input"]:
            confirm = input(f"Fshihet {count} libra dhe të gjitha kopjet, huazimet, rezervimet e lidhura. Vazhdoj? (po/jo): ")
            if confirm.lower() not in ("po", "yes", "p", "y"):
                self.stdout.write("Anuluar.")
                return

        deleted_loans = 0
        deleted_fines = 0
        deleted_copies = 0
        deleted_books = 0

        for book in books:
            for copy in book.copies.filter(is_deleted=False):
                for loan in copy.loans.all():
                    fine = getattr(loan, "fine", None)
                    if fine:
                        Payment.objects.filter(fine=fine).delete()
                        fine.delete()
                        deleted_fines += 1
                    loan.delete()
                    deleted_loans += 1
                copy.is_deleted = True
                copy.save()
                deleted_copies += 1

            Hold.objects.filter(book=book).delete()
            Reservation.objects.filter(book=book).delete()
            ReservationRequest.objects.filter(book=book).delete()

            book.is_deleted = True
            book.save()
            deleted_books += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"U fshinë: {deleted_books} libra, {deleted_copies} kopje, {deleted_loans} huazime, {deleted_fines} gjoba."
            )
        )
