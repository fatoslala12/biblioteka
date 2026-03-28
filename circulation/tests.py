from datetime import timedelta
import io
import json

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import MemberProfile, UserRole
from audit.models import AuditEntry
from catalog.models import Book, Copy, CopyStatus
from circulation.models import Loan, LoanStatus, Reservation, ReservationRequest, ReservationRequestStatus, ReservationStatus
from circulation.services import auto_expire_overdue_reservations
from fines.models import Fine, FineStatus
from policies.models import LibraryPolicy

User = get_user_model()


class ReservationAutoExpireTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff_auto_expire",
            email="staff_auto_expire@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=True,
        )
        self.member_user = User.objects.create_user(
            username="member_auto_expire",
            email="member_auto_expire@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
        )
        self.member = MemberProfile.objects.create(
            user=self.member_user,
            full_name="Member Auto Expire",
            phone="0680000000",
            national_id="AE123456X",
            place_of_birth="Tirane",
            address="Rruga Test 10",
        )
        self.book = Book.objects.create(title="Auto Expire Book", isbn="9780000000001")
        policy, _ = LibraryPolicy.objects.get_or_create(name="default")
        policy.reservation_grace_days = 0
        policy.reservation_warning_hours = 24
        policy.save(update_fields=["reservation_grace_days", "reservation_warning_hours", "updated_at"])

    def test_auto_expire_marks_only_overdue_approved_reservations(self):
        today = timezone.localdate()
        overdue = Reservation.objects.create(
            member=self.member,
            book=self.book,
            pickup_date=today - timedelta(days=2),
            return_date=today + timedelta(days=5),
            status=ReservationStatus.APPROVED,
            created_by=self.staff,
        )
        not_overdue = Reservation.objects.create(
            member=self.member,
            book=self.book,
            pickup_date=today,
            return_date=today + timedelta(days=5),
            status=ReservationStatus.APPROVED,
            created_by=self.staff,
        )

        count = auto_expire_overdue_reservations(actor=self.staff, source_screen="test.auto_expire")

        self.assertEqual(count, 1)
        overdue.refresh_from_db()
        not_overdue.refresh_from_db()
        self.assertEqual(overdue.status, ReservationStatus.EXPIRED)
        self.assertEqual(not_overdue.status, ReservationStatus.APPROVED)

    def test_auto_expire_creates_audit_entry(self):
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            member=self.member,
            book=self.book,
            pickup_date=today - timedelta(days=1),
            return_date=today + timedelta(days=3),
            status=ReservationStatus.APPROVED,
            created_by=self.staff,
        )

        auto_expire_overdue_reservations(actor=self.staff, source_screen="test.auto_expire")

        audit = AuditEntry.objects.filter(
            app_label="circulation",
            model_name="reservation",
            object_id=str(reservation.id),
            action_type="RESERVATION_AUTO_EXPIRED",
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor_id, self.staff.id)

    def test_auto_expire_respects_policy_grace_days(self):
        policy = LibraryPolicy.objects.get(name="default")
        policy.reservation_grace_days = 2
        policy.save(update_fields=["reservation_grace_days", "updated_at"])

        today = timezone.localdate()
        within_grace = Reservation.objects.create(
            member=self.member,
            book=self.book,
            pickup_date=today - timedelta(days=1),
            return_date=today + timedelta(days=3),
            status=ReservationStatus.APPROVED,
            created_by=self.staff,
        )
        outside_grace = Reservation.objects.create(
            member=self.member,
            book=self.book,
            pickup_date=today - timedelta(days=3),
            return_date=today + timedelta(days=3),
            status=ReservationStatus.APPROVED,
            created_by=self.staff,
        )

        count = auto_expire_overdue_reservations(actor=self.staff, source_screen="test.auto_expire.grace")
        self.assertEqual(count, 1)
        within_grace.refresh_from_db()
        outside_grace.refresh_from_db()
        self.assertEqual(within_grace.status, ReservationStatus.APPROVED)
        self.assertEqual(outside_grace.status, ReservationStatus.EXPIRED)


class DailyOpsReportCommandTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff_ops_report",
            email="staff_ops_report@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=True,
        )
        self.member_user = User.objects.create_user(
            username="member_ops_report",
            email="member_ops_report@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
        )
        self.member = MemberProfile.objects.create(
            user=self.member_user,
            full_name="Member Ops Report",
            phone="0690000000",
            national_id="OPS123456X",
            place_of_birth="Tirane",
            address="Rruga Ops",
        )
        self.book = Book.objects.create(title="Ops Report Book", isbn="9782222222222")
        self.copy = Copy.objects.create(book=self.book, barcode="OPS-COPY-1", status=CopyStatus.ON_LOAN)

        policy, _ = LibraryPolicy.objects.get_or_create(name="default")
        policy.reservation_grace_days = 1
        policy.reservation_warning_hours = 48
        policy.save(update_fields=["reservation_grace_days", "reservation_warning_hours", "updated_at"])

        now = timezone.now()
        Loan.objects.create(
            member=self.member,
            copy=self.copy,
            due_at=now - timedelta(days=1),
            status=LoanStatus.ACTIVE,
            loaned_by=self.staff,
        )
        Reservation.objects.create(
            member=self.member,
            book=self.book,
            pickup_date=timezone.localdate() - timedelta(days=3),
            return_date=timezone.localdate() + timedelta(days=2),
            status=ReservationStatus.APPROVED,
            created_by=self.staff,
        )
        ReservationRequest.objects.create(
            member=self.member,
            book=self.book,
            status=ReservationRequestStatus.PENDING,
            created_by=self.staff,
        )
        fine_loan = Loan.objects.create(
            member=self.member,
            copy=self.copy,
            due_at=now + timedelta(days=5),
            status=LoanStatus.RETURNED,
            loaned_by=self.staff,
        )
        Fine.objects.create(
            loan=fine_loan,
            member=self.member,
            amount="200.00",
            status=FineStatus.UNPAID,
            reason="Overdue",
        )

    def test_daily_ops_report_json_output_contains_key_metrics(self):
        out = io.StringIO()
        call_command("daily_ops_report", "--json", stdout=out)
        payload = json.loads(out.getvalue().strip())

        self.assertIn("loans", payload)
        self.assertIn("reservations", payload)
        self.assertIn("reservation_requests", payload)
        self.assertIn("fines", payload)
        self.assertGreaterEqual(payload["loans"]["overdue"], 1)
        self.assertGreaterEqual(payload["reservations"]["overdue_auto_expire_candidates"], 1)
        self.assertGreaterEqual(payload["reservation_requests"]["pending"], 1)
        self.assertGreaterEqual(payload["fines"]["unpaid_count"], 1)
