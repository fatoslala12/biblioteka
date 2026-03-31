from datetime import timedelta
import io
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import MemberProfile, UserRole
from audit.models import AuditEntry
from catalog.models import Book, Copy, CopyStatus
from circulation.models import Loan, LoanStatus, Reservation, ReservationRequest, ReservationRequestStatus, ReservationStatus
from circulation.services import auto_expire_overdue_reservations, create_reservation_request
from circulation.exceptions import PolicyViolation
from fines.models import Fine, FineStatus, Payment, PaymentMethod
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


class UnpaidFineBlockingTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff_block_tests",
            email="staff_block_tests@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=True,
        )
        self.member_user = User.objects.create_user(
            username="member_block_tests",
            email="member_block_tests@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
        )
        self.member = MemberProfile.objects.create(
            user=self.member_user,
            full_name="Member Block Tests",
            phone="0677777777",
            national_id="BLK123456X",
            place_of_birth="Tirane",
            address="Rruga Block",
            member_no="M-BLOCK-001",
        )
        self.book = Book.objects.create(title="Blocking Book", isbn="9786666666666")
        self.copy = Copy.objects.create(book=self.book, barcode="BLK-COPY-1", status=CopyStatus.AVAILABLE)
        self.loan_for_fine = Loan.objects.create(
            member=self.member,
            copy=self.copy,
            due_at=timezone.now() - timedelta(days=3),
            status=LoanStatus.RETURNED,
            loaned_by=self.staff,
        )
        self.fine = Fine.objects.create(
            loan=self.loan_for_fine,
            member=self.member,
            amount="50.00",
            status=FineStatus.UNPAID,
            reason="Vonesë",
        )
        self.reserve_book = Book.objects.create(title="Reserve Block Book", isbn="9787777777777")
        self.reserve_copy = Copy.objects.create(book=self.reserve_book, barcode="BLK-COPY-2", status=CopyStatus.AVAILABLE)

    def test_member_with_unpaid_fine_cannot_create_reservation_request(self):
        with self.assertRaisesMessage(PolicyViolation, "Ju keni një gjobë të papaguar"):
            create_reservation_request(
                member_no=self.member.member_no,
                book_id=self.reserve_book.id,
                pickup_date=timezone.localdate() + timedelta(days=1),
                return_date=timezone.localdate() + timedelta(days=3),
                created_by=self.staff,
                source_screen="test.unpaid_fine_block_reservation",
            )

    def test_member_can_proceed_after_paying_full_fine(self):
        Payment.objects.create(
            fine=self.fine,
            amount="50.00",
            method=PaymentMethod.CASH,
            recorded_by=self.staff,
        )
        self.fine.status = FineStatus.PAID
        self.fine.save(update_fields=["status", "updated_at"])

        req = create_reservation_request(
            member_no=self.member.member_no,
            book_id=self.reserve_book.id,
            pickup_date=timezone.localdate() + timedelta(days=1),
            return_date=timezone.localdate() + timedelta(days=3),
            created_by=self.staff,
            source_screen="test.unpaid_fine_after_payment",
        )
        self.assertEqual(req.status, ReservationRequestStatus.PENDING)


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
        self.assertIn("priority", payload)
        self.assertIn("thresholds", payload)
        self.assertIn("alerts", payload)
        self.assertIn("actions_needed_today", payload)
        self.assertGreaterEqual(payload["loans"]["overdue"], 1)
        self.assertGreaterEqual(payload["reservations"]["overdue_auto_expire_candidates"], 1)
        self.assertGreaterEqual(payload["reservation_requests"]["pending"], 1)
        self.assertGreaterEqual(payload["fines"]["unpaid_count"], 1)

    def test_daily_ops_report_can_save_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "daily_ops_report.json"
            call_command("daily_ops_report", "--save-file", str(target))
            self.assertTrue(target.exists())
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertIn("generated_at", payload)
            self.assertIn("fines", payload)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="ops@test.com",
        OPS_REPORT_RECIPIENTS=["ops1@test.com", "ops2@test.com"],
    )
    def test_daily_ops_report_can_send_email_to_default_recipients(self):
        from django.core import mail

        call_command("daily_ops_report", "--send-email")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Daily Ops Report - Smart Library", mail.outbox[0].subject)
        self.assertEqual(set(mail.outbox[0].to), {"ops1@test.com", "ops2@test.com"})

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="ops@test.com",
        OPS_REPORT_RECIPIENTS=["ops1@test.com"],
    )
    def test_daily_ops_report_uses_high_priority_subject_when_threshold_crossed(self):
        from django.core import mail

        call_command(
            "daily_ops_report",
            "--send-email",
            "--threshold-overdue-loans",
            "1",
            "--threshold-overdue-reservations",
            "50",
            "--threshold-pending-requests",
            "50",
            "--threshold-unpaid-fines-total",
            "10000.00",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("[HIGH PRIORITY]", mail.outbox[0].subject)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="ops@test.com",
        OPS_REPORT_RECIPIENTS=["ops1@test.com"],
    )
    def test_daily_ops_report_uses_medium_priority_subject_when_near_threshold(self):
        from django.core import mail

        call_command(
            "daily_ops_report",
            "--send-email",
            "--threshold-overdue-loans",
            "50",
            "--threshold-overdue-reservations",
            "50",
            "--threshold-pending-requests",
            "50",
            "--threshold-unpaid-fines-total",
            "250.00",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("[MEDIUM PRIORITY]", mail.outbox[0].subject)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="ops@test.com",
        OPS_REPORT_RECIPIENTS=["ops1@test.com"],
    )
    def test_daily_ops_report_uses_critical_priority_subject_when_threshold_doubled(self):
        from django.core import mail

        call_command(
            "daily_ops_report",
            "--send-email",
            "--threshold-overdue-loans",
            "1",
            "--threshold-overdue-reservations",
            "1",
            "--threshold-pending-requests",
            "1",
            "--threshold-unpaid-fines-total",
            "1.00",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("[CRITICAL PRIORITY]", mail.outbox[0].subject)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="ops@test.com",
    SMS_WEBHOOK_URL="",
    PUBLIC_BASE_URL="https://biblioteka.example.al",
)
class MemberNotificationsCommandTests(TestCase):
    def setUp(self):
        self.member_user = User.objects.create_user(
            username="member_notify",
            email="member_notify@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
        )
        self.staff = User.objects.create_user(
            username="staff_notify",
            email="staff_notify@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=True,
        )
        self.member = MemberProfile.objects.create(
            user=self.member_user,
            full_name="Member Notify",
            phone="0691111111",
            national_id="NOT123X",
            place_of_birth="Tirane",
            address="Rruga Notify",
        )
        self.book = Book.objects.create(title="Notify Book", isbn="9784444444444")
        self.copy = Copy.objects.create(book=self.book, barcode="NOT-COPY-1", status=CopyStatus.ON_LOAN)

    @override_settings(NOTIFY_DUE_SOON_DAYS=2, NOTIFY_FINE_CREATED_LOOKBACK_DAYS=5, NOTIFY_RESERVATION_EXPIRY_HOURS=48)
    def test_notify_members_sends_email_for_due_soon_fine_and_reservation_expiring(self):
        from django.core import mail

        now = timezone.now()
        loan = Loan.objects.create(
            member=self.member,
            copy=self.copy,
            due_at=now + timedelta(days=1),
            status=LoanStatus.ACTIVE,
            loaned_by=self.staff,
        )
        fine_loan = Loan.objects.create(
            member=self.member,
            copy=self.copy,
            due_at=now - timedelta(days=4),
            status=LoanStatus.RETURNED,
            loaned_by=self.staff,
        )
        fine = Fine.objects.create(
            loan=fine_loan,
            member=self.member,
            amount="120.00",
            status=FineStatus.UNPAID,
            reason="Overdue",
        )
        policy, _ = LibraryPolicy.objects.get_or_create(name="default")
        policy.reservation_grace_days = 0
        policy.save(update_fields=["reservation_grace_days", "updated_at"])
        reservation = Reservation.objects.create(
            member=self.member,
            book=self.book,
            pickup_date=timezone.localdate(),
            return_date=timezone.localdate() + timedelta(days=2),
            status=ReservationStatus.APPROVED,
            created_by=self.staff,
        )

        call_command("notify_members", "--channels", "email")
        self.assertGreaterEqual(len(mail.outbox), 3)
        subjects = " | ".join(m.subject for m in mail.outbox)
        self.assertIn("Afati i kthimit po afrohet", subjects)
        self.assertIn("Njoftim për gjobë të re", subjects)
        self.assertIn("Rezervimi juaj po skadon", subjects)
        # HTML premium template is attached to outgoing notifications.
        self.assertTrue(any(msg.alternatives for msg in mail.outbox))
        self.assertTrue(any("Njoftim automatik për anëtarin" in alt[0] for msg in mail.outbox for alt in msg.alternatives))
        self.assertTrue(
            any(
                "https://biblioteka.example.al/anetar/?focus=loans" in alt[0]
                and f"loan_id={loan.id}" in alt[0]
                and f"#loan-{loan.id}" in alt[0]
                for msg in mail.outbox
                for alt in msg.alternatives
            )
        )
        self.assertTrue(
            any(
                "https://biblioteka.example.al/anetar/?focus=fines" in alt[0]
                and f"fine_id={fine.id}" in alt[0]
                and f"#fine-{fine.id}" in alt[0]
                for msg in mail.outbox
                for alt in msg.alternatives
            )
        )
        self.assertTrue(
            any(
                "https://biblioteka.example.al/anetar/?focus=reservations" in alt[0]
                and f"reservation_id={reservation.id}" in alt[0]
                and "#member-reservations" in alt[0]
                for msg in mail.outbox
                for alt in msg.alternatives
            )
        )

        self.assertTrue(
            AuditEntry.objects.filter(
                action_type="MEMBER_NOTIFICATION_DUE_SOON",
                reason__startswith=f"loan:{loan.id}:due_soon:",
            ).exists()
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                action_type="MEMBER_NOTIFICATION_FINE_CREATED",
                reason=f"fine:{fine.id}:created",
            ).exists()
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                action_type="MEMBER_NOTIFICATION_RESERVATION_EXPIRING",
                reason__startswith=f"reservation:{reservation.id}:expiring:",
            ).exists()
        )

    def test_notify_members_avoids_duplicate_notifications(self):
        from django.core import mail

        Loan.objects.create(
            member=self.member,
            copy=self.copy,
            due_at=timezone.now() + timedelta(days=1),
            status=LoanStatus.ACTIVE,
            loaned_by=self.staff,
        )

        call_command("notify_members", "--channels", "email")
        first_count = len(mail.outbox)
        call_command("notify_members", "--channels", "email")
        second_count = len(mail.outbox)
        self.assertEqual(first_count, second_count)
