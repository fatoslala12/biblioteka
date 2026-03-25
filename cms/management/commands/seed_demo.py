from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import MemberProfile, MemberType
from catalog.models import Author, Book, BookType, Copy, CopyStatus, Genre, Publisher, Tag
from circulation.models import Loan
from circulation.services import create_reservation_request, place_hold, return_copy, checkout_copy
from policies.models import LibraryPolicy, LoanRule


class Command(BaseCommand):
    help = "Create demo data: books, copies, members, and sample circulation."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding demo data..."))

        self._ensure_policy()
        members = self._seed_members()
        books_with_copies = self._seed_books_and_copies()
        self._seed_activity(members, books_with_copies)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Suggested logins for members (default password: 12345678):")
        for member in members:
            uname = member.user.username if member.user_id else "N/A"
            self.stdout.write(f"- {member.member_no} | {member.full_name} | username: {uname}")

    def _ensure_policy(self) -> None:
        policy, _ = LibraryPolicy.objects.get_or_create(name="default")
        policy.fine_per_day = 10
        policy.fine_cap = 200
        policy.hold_window_hours = 48
        policy.max_renewals = 2
        policy.default_loan_period_days = 14
        policy.default_max_active_loans = 5
        policy.fine_block_threshold = 300
        policy.save()

        # One predictable rule for students on general books.
        LoanRule.objects.get_or_create(
            policy=policy,
            member_type=MemberType.STUDENT,
            book_type=BookType.GENERAL,
            defaults={"loan_period_days": 21, "max_active_loans": 7},
        )

    def _seed_members(self) -> list[MemberProfile]:
        demo_members = [
            {
                "full_name": "Ardit Hoxha",
                "member_type": MemberType.STUDENT,
                "phone": "0681000001",
                "address": "Tirane",
                "national_id": "DEMO000001",
            },
            {
                "full_name": "Elira Kola",
                "member_type": MemberType.STANDARD,
                "phone": "0681000002",
                "address": "Durres",
                "national_id": "DEMO000002",
            },
            {
                "full_name": "Blerina Leka",
                "member_type": MemberType.VIP,
                "phone": "0681000003",
                "address": "Vlore",
                "national_id": "DEMO000003",
            },
            {
                "full_name": "Kledi Meta",
                "member_type": MemberType.STUDENT,
                "phone": "0681000004",
                "address": "Shkoder",
                "national_id": "DEMO000004",
            },
            {
                "full_name": "Sara Dervishi",
                "member_type": MemberType.STANDARD,
                "phone": "0681000005",
                "address": "Korce",
                "national_id": "DEMO000005",
            },
            {
                "full_name": "Gentian Konomi",
                "member_type": MemberType.STUDENT,
                "phone": "0681000006",
                "address": "Elbasan",
                "national_id": "DEMO000006",
            },
            {
                "full_name": "Megi Shehu",
                "member_type": MemberType.STANDARD,
                "phone": "0681000007",
                "address": "Fier",
                "national_id": "DEMO000007",
            },
            {
                "full_name": "Orges Cani",
                "member_type": MemberType.VIP,
                "phone": "0681000008",
                "address": "Lezhe",
                "national_id": "DEMO000008",
            },
            {
                "full_name": "Dorina Basha",
                "member_type": MemberType.STUDENT,
                "phone": "0681000009",
                "address": "Berat",
                "national_id": "DEMO000009",
            },
            {
                "full_name": "Klevis Puka",
                "member_type": MemberType.STANDARD,
                "phone": "0681000010",
                "address": "Kukes",
                "national_id": "DEMO000010",
            },
            {
                "full_name": "Erinda Gjoka",
                "member_type": MemberType.STUDENT,
                "phone": "0681000011",
                "address": "Lushnje",
                "national_id": "DEMO000011",
            },
            {
                "full_name": "Alban Vata",
                "member_type": MemberType.STANDARD,
                "phone": "0681000012",
                "address": "Pogradec",
                "national_id": "DEMO000012",
            },
            {
                "full_name": "Jona Malaj",
                "member_type": MemberType.VIP,
                "phone": "0681000013",
                "address": "Gjirokaster",
                "national_id": "DEMO000013",
            },
            {
                "full_name": "Sokol Rama",
                "member_type": MemberType.STANDARD,
                "phone": "0681000014",
                "address": "Tirane",
                "national_id": "DEMO000014",
            },
            {
                "full_name": "Elda Kodra",
                "member_type": MemberType.STUDENT,
                "phone": "0681000015",
                "address": "Shkoder",
                "national_id": "DEMO000015",
            },
        ]

        result: list[MemberProfile] = []
        for payload in demo_members:
            member, created = MemberProfile.objects.get_or_create(
                national_id=payload["national_id"],
                defaults=payload,
            )
            if not created:
                member.full_name = payload["full_name"]
                member.member_type = payload["member_type"]
                member.phone = payload["phone"]
                member.address = payload["address"]
                member.save()
            result.append(member)

        self.stdout.write(self.style.SUCCESS(f"Members ready: {len(result)}"))
        return result

    def _seed_books_and_copies(self) -> list[tuple[Book, list[Copy]]]:
        books_payload = [
            {
                "title": "Gjenerali i Ushtrise se Vdekur",
                "author": "Ismail Kadare",
                "genre": "Roman",
                "publisher": "Onufri",
                "tags": ["shqip", "klasik"],
                "year": 1963,
                "language": "SQ",
                "copies": 3,
            },
            {
                "title": "Kronike ne Gur",
                "author": "Ismail Kadare",
                "genre": "Roman",
                "publisher": "Onufri",
                "tags": ["shqip", "roman"],
                "year": 1971,
                "language": "SQ",
                "copies": 4,
            },
            {
                "title": "Prilli i Thyer",
                "author": "Ismail Kadare",
                "genre": "Roman",
                "publisher": "Onufri",
                "tags": ["shqip", "letersi"],
                "year": 1978,
                "language": "SQ",
                "copies": 3,
            },
            {
                "title": "Sikur te isha djale",
                "author": "Haki Starmilli",
                "genre": "Roman",
                "publisher": "Toena",
                "tags": ["shqip", "social"],
                "year": 1936,
                "language": "SQ",
                "copies": 3,
            },
            {
                "title": "Lumi i Vdekur",
                "author": "Jakov Xoxa",
                "genre": "Roman",
                "publisher": "Toena",
                "tags": ["shqip", "klasik"],
                "year": 1964,
                "language": "SQ",
                "copies": 3,
            },
            {
                "title": "Njeriu me Top",
                "author": "Dritero Agolli",
                "genre": "Roman",
                "publisher": "Toena",
                "tags": ["shqip", "letersi"],
                "year": 1975,
                "language": "SQ",
                "copies": 3,
            },
            {
                "title": "Shkelqimi dhe Renia e Shokut Zylo",
                "author": "Dritero Agolli",
                "genre": "Satire",
                "publisher": "Toena",
                "tags": ["shqip", "satire"],
                "year": 1973,
                "language": "SQ",
                "copies": 2,
            },
            {
                "title": "Rrethimi",
                "author": "Fatos Kongoli",
                "genre": "Roman",
                "publisher": "Uegen",
                "tags": ["shqip", "modern"],
                "year": 2000,
                "language": "SQ",
                "copies": 2,
            },
            {
                "title": "Kufoma",
                "author": "Fatos Kongoli",
                "genre": "Roman",
                "publisher": "Uegen",
                "tags": ["shqip", "modern"],
                "year": 1995,
                "language": "SQ",
                "copies": 2,
            },
            {
                "title": "Syte e Simonides",
                "author": "Ben Blushi",
                "genre": "Roman Historik",
                "publisher": "Mapo Editions",
                "tags": ["shqip", "historik"],
                "year": 2014,
                "language": "SQ",
                "copies": 3,
            },
            {
                "title": "Hena e Shqiperise",
                "author": "Nasi Lera",
                "genre": "Tregime",
                "publisher": "Toena",
                "tags": ["shqip", "tregime"],
                "year": 2012,
                "language": "SQ",
                "copies": 2,
            },
            {
                "title": "Legjenda e Vetmise",
                "author": "Mimoza Ahmeti",
                "genre": "Poezi",
                "publisher": "Onufri",
                "tags": ["shqip", "poezi"],
                "year": 1990,
                "language": "SQ",
                "copies": 3,
            },
        ]

        result: list[tuple[Book, list[Copy]]] = []
        for index, payload in enumerate(books_payload, start=1):
            author, _ = Author.objects.get_or_create(name=payload["author"])
            genre, _ = Genre.objects.get_or_create(name=payload["genre"])
            publisher, _ = Publisher.objects.get_or_create(name=payload["publisher"])
            tag_objs = [Tag.objects.get_or_create(name=tag)[0] for tag in payload["tags"]]

            book, _ = Book.objects.update_or_create(
                title=payload["title"],
                defaults={
                    "isbn": f"97800000{index:03d}",
                    "description": f"[DEMO] {payload['title']} - data testimi.",
                    "language": payload["language"],
                    "publication_year": payload["year"],
                    "book_type": BookType.GENERAL,
                    "publisher": publisher,
                    "is_deleted": False,
                },
            )
            book.authors.set([author])
            book.genres.set([genre])
            book.tags.set(tag_objs)

            copies: list[Copy] = []
            for i in range(1, int(payload["copies"]) + 1):
                barcode = f"DEMO-{index:02d}-{i:02d}"
                copy, _ = Copy.objects.get_or_create(
                    barcode=barcode,
                    defaults={
                        "book": book,
                        "location": "Salla A",
                        "shelf": f"R-{index:02d}",
                        "condition": "GOOD",
                    },
                )
                if copy.book_id != book.id:
                    copy.book = book
                    copy.save(update_fields=["book", "updated_at"])
                copies.append(copy)

            result.append((book, copies))

        self.stdout.write(self.style.SUCCESS(f"Books ready: {len(result)}"))
        return result

    def _seed_activity(self, members: list[MemberProfile], books_with_copies: list[tuple[Book, list[Copy]]]) -> None:
        active_loans_created = 0
        returned_loans_created = 0
        holds_created = 0
        reservation_requests_created = 0

        # 1) Create multiple active loans.
        for i, member in enumerate(members[:10]):
            if i >= len(books_with_copies):
                break
            book, _ = books_with_copies[i]
            demo_note = f"[DEMO] Huazim aktiv SQ #{i + 1}"
            if Loan.objects.filter(note=demo_note).exists():
                continue

            copy = (
                Copy.objects.filter(book=book, status=CopyStatus.AVAILABLE, is_deleted=False)
                .order_by("id")
                .first()
            )
            if not copy:
                continue

            try:
                loan = checkout_copy(member_no=member.member_no, copy_barcode=copy.barcode)
                loan.note = demo_note
                loan.save(update_fields=["note", "updated_at"])
                active_loans_created += 1
            except Exception:
                continue

        # 2) Create multiple returned-overdue loans (to generate fines).
        overdue_pairs = min(5, len(members), len(books_with_copies))
        for i in range(overdue_pairs):
            member = members[-(i + 1)]
            book, _ = books_with_copies[i]
            demo_note = f"[DEMO] Kthim me vonese SQ #{i + 1}"
            if Loan.objects.filter(note=demo_note).exists():
                continue

            copy = (
                Copy.objects.filter(book=book, status=CopyStatus.AVAILABLE, is_deleted=False)
                .order_by("id")
                .first()
            )
            if not copy:
                continue

            try:
                loan = checkout_copy(member_no=member.member_no, copy_barcode=copy.barcode)
                loan.note = demo_note
                loan.due_at = timezone.now() - timedelta(days=3 + i)
                loan.save(update_fields=["note", "due_at", "updated_at"])
                return_copy(copy_barcode=copy.barcode)
                returned_loans_created += 1
            except Exception:
                continue

        # 3) More holds on different books.
        hold_pairs = min(6, len(members), len(books_with_copies))
        for i in range(hold_pairs):
            member = members[i]
            book, _ = books_with_copies[-(i + 1)]
            try:
                place_hold(member_no=member.member_no, book_id=book.id)
                holds_created += 1
            except Exception:
                continue

        # 4) More reservation requests.
        req_pairs = min(8, len(members), len(books_with_copies))
        for i in range(req_pairs):
            member = members[i]
            book, _ = books_with_copies[i]
            pickup = timezone.now().date() + timedelta(days=2 + i)
            dropoff = pickup + timedelta(days=5 + (i % 3))
            try:
                create_reservation_request(
                    member_no=member.member_no,
                    book_id=book.id,
                    pickup_date=pickup,
                    return_date=dropoff,
                    note=f"[DEMO] Kerkese rezervimi SQ #{i + 1}",
                )
                reservation_requests_created += 1
            except Exception:
                continue

        self.stdout.write(
            self.style.SUCCESS(
                "Demo activity created "
                f"(active_loans={active_loans_created}, returned_overdue={returned_loans_created}, "
                f"holds={holds_created}, reservation_requests={reservation_requests_created})."
            )
        )
