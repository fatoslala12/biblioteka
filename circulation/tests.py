from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import MemberProfile, UserRole
from audit.models import AuditEntry
from catalog.models import Book
from circulation.models import Reservation, ReservationStatus
from circulation.services import auto_expire_overdue_reservations

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
