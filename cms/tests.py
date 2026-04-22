from datetime import timedelta
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from pathlib import Path

from accounts.models import MemberProfile, UserRole
from audit.services import log_audit_event
from catalog.models import Book, Copy, CopyStatus
from circulation.models import Loan, LoanStatus, ReservationRequest, ReservationRequestStatus
from fines.models import Fine, FineStatus, Payment, PaymentMethod
from policies.models import LibraryPolicy

from cms.models import Announcement, Event, WeeklyBook
from notifications.models import NotificationKind, UserNotification

User = get_user_model()


@override_settings(RATELIMIT_ENABLE=False)
class MemberSignUpTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username="staff_signup_notif",
            email="staff_signup_notif@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=True,
        )

    def test_sign_up_get_ok(self):
        r = self.client.get("/regjistrohu/")
        self.assertEqual(r.status_code, 200)

    def test_sign_up_creates_member_and_profile(self):
        data = {
            "email": "newmember_signup@test.com",
            "password1": "K9#mP2$vLxQw!nR8tY",
            "password2": "K9#mP2$vLxQw!nR8tY",
            "full_name": "Test User",
            "phone": "0691234567",
            "date_of_birth": "1995-05-15",
            "national_id": "K12345678X_SIGNUP",
            "place_of_birth": "Tiranë",
            "address": "Rruga Test 1",
            "trap_field": "",
            "accept_terms": "on",
        }
        r = self.client.post("/regjistrohu/", data, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.endswith("/anetar/"))
        u = User.objects.get(email="newmember_signup@test.com")
        self.assertEqual(u.username, "newmember_signup@test.com")
        self.assertEqual(u.role, UserRole.MEMBER)
        mp = u.member_profile
        self.assertTrue(mp.member_no.startswith("M"))
        self.assertEqual(mp.full_name, "Test User")
        self.assertTrue(
            UserNotification.objects.filter(
                user=self.staff,
                kind=NotificationKind.MEMBER_NEW_STAFF,
                title__icontains="Anëtar i ri",
            ).exists()
        )

    def test_hidden_trap_field_does_not_block_real_signup(self):
        data = {
            "email": "bot@test.com",
            "password1": "K9#mP2$vLxQw!nR8tY",
            "password2": "K9#mP2$vLxQw!nR8tY",
            "full_name": "Bot User",
            "phone": "0691234567",
            "date_of_birth": "1995-05-15",
            "national_id": "BOT999",
            "place_of_birth": "Tiranë",
            "address": "X",
            "trap_field": "http://spam.com",
            "accept_terms": "on",
        }
        r = self.client.post("/regjistrohu/", data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.endswith("/anetar/"))
        self.assertTrue(User.objects.filter(email="bot@test.com").exists())

    def test_sign_up_requires_terms_acceptance(self):
        data = {
            "email": "terms_missing@test.com",
            "password1": "K9#mP2$vLxQw!nR8tY",
            "password2": "K9#mP2$vLxQw!nR8tY",
            "full_name": "Terms Missing",
            "phone": "0691234567",
            "date_of_birth": "1995-05-15",
            "national_id": "TM12345678X",
            "place_of_birth": "Tirane",
            "address": "Rruga Test",
            "trap_field": "",
        }
        r = self.client.post("/regjistrohu/", data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="terms_missing@test.com").exists())


class HealthzTests(TestCase):
    def test_healthz_ok_and_cache_header(self):
        r = self.client.get("/healthz/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content.decode("utf-8"), "ok")
        self.assertIn("max-age=30", r.headers.get("Cache-Control", ""))


class AdminAuthRedirectTests(TestCase):
    def test_admin_login_redirects_to_custom_signin(self):
        r = self.client.get("/admin/login/?next=/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/hyr/?next=/admin/")

    def test_admin_logout_redirects_home(self):
        r = self.client.get("/admin/logout/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/")

    def test_admin_logout_really_logs_out_user(self):
        u = User.objects.create_user(
            username="logout_test_user",
            email="logout_test_user@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=True,
        )
        self.client.force_login(u)
        r = self.client.get("/admin/logout/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/")
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RATELIMIT_ENABLE=False,
)
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="forgot_member",
            email="forgot_member@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
        )

    def test_forgot_password_sends_email_and_redirects(self):
        r = self.client.post("/harrova-fjalekalimin/", {"email": "forgot_member@test.com"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/rivendosje-derguar/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Rivendos fjalëkalimin", mail.outbox[0].subject)

    def test_forgot_password_unknown_email_still_redirects(self):
        r = self.client.post("/harrova-fjalekalimin/", {"email": "unknown@test.com"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/rivendosje-derguar/")


class PublicSmokeTests(TestCase):
    def test_home_signin_signup_pages_load(self):
        for url in ("/", "/hyr/", "/regjistrohu/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, msg=f"Expected 200 for {url}")

    def test_admin_index_requires_auth_and_redirects(self):
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin/login/?next=/admin/", r["Location"])

        # Then custom admin login endpoint redirects to public sign in page.
        r2 = self.client.get(r["Location"])
        self.assertEqual(r2.status_code, 302)
        self.assertIn("/hyr/?next=/admin/", r2["Location"])


class MemberPortalIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="member_integration",
            email="member_integration@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
            is_superuser=False,
        )
        MemberProfile.objects.create(
            user=self.user,
            full_name="Member Integration",
            phone="0681111111",
            national_id="INT12345X",
            place_of_birth="Tirane",
            address="Rruga Integrim 1",
        )

    def test_member_login_redirects_to_member_portal(self):
        response = self.client.post(
            "/hyr/",
            {"username": "member_integration", "password": "K9#mP2$vLxQw!nR8tY"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/anetar/")

    def test_member_portal_loads_for_authenticated_member(self):
        self.client.force_login(self.user)
        response = self.client.get("/anetar/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gjoba & Pagesa")
        self.assertContains(response, "Të papaguara")
        self.assertContains(response, "slMemberNotifBellBtn")

    def test_member_notifications_list_loads(self):
        self.client.force_login(self.user)
        UserNotification.objects.create(
            user=self.user,
            kind=NotificationKind.RESERVATION_SUBMITTED_MEMBER,
            title="Test njoftim",
            body="Përmbajtje test.",
        )
        r = self.client.get("/anetar/notifications/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test njoftim")

    def test_member_notifications_legacy_redirects(self):
        self.client.force_login(self.user)
        r = self.client.get("/anetar/njoftime/", follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/anetar/notifications/"))


class StaffPanelNotificationsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username="staff_notif_panel",
            email="staff_notif_panel@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=False,
            is_superuser=False,
        )

    def test_panel_notifications_loads(self):
        self.client.force_login(self.staff)
        UserNotification.objects.create(
            user=self.staff,
            kind=NotificationKind.RESERVATION_NEW_STAFF,
            title="Panel list item",
            body="",
        )
        r = self.client.get("/panel/notifications/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "slMemberNotifBellBtn")
        self.assertContains(r, "Panel list item")


class StaffNotificationBadgeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            username="badge_member",
            email="badge_member@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
        )
        self.staff_admin = User.objects.create_user(
            username="badge_staff_admin",
            email="badge_staff_admin@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.STAFF,
            is_staff=True,
        )
        self.superadmin = User.objects.create_superuser(
            username="badge_superadmin",
            email="badge_superadmin@test.com",
            password="K9#mP2$vLxQw!nR8tY",
        )

    def test_badge_json_forbidden_for_member(self):
        self.client.force_login(self.member)
        r = self.client.get("/_staff-notif-badge/")
        self.assertEqual(r.status_code, 403)

    def test_badge_json_ok_for_is_staff_user(self):
        self.client.force_login(self.staff_admin)
        UserNotification.objects.create(
            user=self.member,
            kind=NotificationKind.RESERVATION_SUBMITTED_MEMBER,
            title="Member ping",
            body="Hello member",
        )
        UserNotification.objects.create(
            user=self.staff_admin,
            kind=NotificationKind.RESERVATION_NEW_STAFF,
            title="Staff ping",
            body="Hello",
        )
        r = self.client.get("/_staff-notif-badge/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertGreaterEqual(data.get("unread", 0), 1)
        self.assertIn("admin_changelist", data)
        self.assertTrue(any("mark_read_url" in p for p in data.get("preview", [])))
        self.assertTrue(any(p.get("title") == "Member ping" for p in data.get("preview", [])))
        self.assertTrue(any(p.get("title") == "Staff ping" for p in data.get("preview", [])))

    def test_admin_change_with_mark_read_marks_notification_read(self):
        notif = UserNotification.objects.create(
            user=self.member,
            kind=NotificationKind.RESERVATION_SUBMITTED_MEMBER,
            title="Will be read",
            body="",
        )
        self.client.force_login(self.superadmin)
        r = self.client.get(f"/admin/notifications/usernotification/{notif.id}/change/?mark_read=1")
        self.assertEqual(r.status_code, 200)
        notif.refresh_from_db()
        self.assertIsNotNone(notif.read_at)


class DesignSystemCssTests(TestCase):
    def test_admin_css_contains_required_design_tokens(self):
        css_path = Path(settings.BASE_DIR) / "static" / "css" / "admin.css"
        content = css_path.read_text(encoding="utf-8")

        required_tokens = (
            "--sl-space-2",
            "--sl-radius-md",
            "--sl-fs-12",
            "--sl-fs-14",
            "--sl-fs-16",
            "--sl-fs-20",
            "--sl-fs-28",
            "--sl-shadow-sm",
            "--sl-shadow-md",
            "--sl-shadow-lg",
        )
        for token in required_tokens:
            self.assertIn(token, content)

    def test_admin_css_contains_reusable_component_selectors(self):
        css_path = Path(settings.BASE_DIR) / "static" / "css" / "admin.css"
        content = css_path.read_text(encoding="utf-8")

        required_components = (
            ".sl-filter-bar",
            ".sl-action-pills",
            ".sl-data-card",
            ".sl-stat-tile",
            ".sl-table-wrap",
        )
        for selector in required_components:
            self.assertIn(selector, content)


class AdminAuditSmokeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_smoke",
            email="admin_smoke@test.com",
            password="K9#mP2$vLxQw!nR8tY",
        )
        self.member_user = User.objects.create_user(
            username="member_smoke",
            email="member_smoke@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
            is_superuser=False,
        )
        self.member = MemberProfile.objects.create(
            user=self.member_user,
            full_name="Member Smoke",
            phone="0670000000",
            national_id="SMOKE123X",
            place_of_birth="Tirane",
            address="Rruga Smoke",
        )
        self.book = Book.objects.create(title="Smoke Book", isbn="9781111111111")
        self.req = ReservationRequest.objects.create(
            member=self.member,
            book=self.book,
            status=ReservationRequestStatus.PENDING,
        )
        log_audit_event(
            target=self.req,
            action_type="RESERVATION_REQUEST_CREATED_MANUAL",
            actor=self.admin_user,
            source_screen="test.admin.audit_smoke",
            metadata={"request_id": self.req.id},
        )

    def test_reservation_request_admin_pages_load_with_timeline(self):
        self.client.force_login(self.admin_user)

        list_resp = self.client.get("/admin/circulation/reservationrequest/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, "Aktiviteti i fundit")
        self.assertContains(list_resp, "Kërkesë rezervimi e krijuar manualisht")

        change_resp = self.client.get(f"/admin/circulation/reservationrequest/{self.req.id}/change/")
        self.assertEqual(change_resp.status_code, 200)
        self.assertContains(change_resp, "Timeline e auditimit")


class AdminCriticalEntitiesSmokeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_critical_smoke",
            email="admin_critical_smoke@test.com",
            password="K9#mP2$vLxQw!nR8tY",
        )
        member_user = User.objects.create_user(
            username="member_critical_smoke",
            email="member_critical_smoke@test.com",
            password="K9#mP2$vLxQw!nR8tY",
            role=UserRole.MEMBER,
            is_staff=False,
            is_superuser=False,
        )
        self.member = MemberProfile.objects.create(
            user=member_user,
            full_name="Critical Smoke Member",
            phone="0671000000",
            national_id="CRIT123X",
            place_of_birth="Tirane",
            address="Rruga Critical",
        )
        book = Book.objects.create(title="Critical Smoke Book", isbn="9783333333333")
        copy = Copy.objects.create(book=book, barcode="CRIT-COPY-1", status=CopyStatus.AVAILABLE)
        loan = Loan.objects.create(
            member=self.member,
            copy=copy,
            due_at=timezone.now(),
            status=LoanStatus.RETURNED,
            loaned_by=self.admin_user,
        )
        self.fine = Fine.objects.create(
            loan=loan,
            member=self.member,
            amount="150.00",
            status=FineStatus.UNPAID,
            reason="Overdue",
        )
        overdue_book = Book.objects.create(title="Only Overdue Loan Book", isbn="9785555555551")
        overdue_copy = Copy.objects.create(book=overdue_book, barcode="CRIT-COPY-OD-1", status=CopyStatus.ON_LOAN)
        self.overdue_loan = Loan.objects.create(
            member=self.member,
            copy=overdue_copy,
            due_at=timezone.now() - timedelta(days=3),
            status=LoanStatus.ACTIVE,
            loaned_by=self.admin_user,
        )
        not_due_book = Book.objects.create(title="Not Due Loan Book", isbn="9785555555552")
        not_due_copy = Copy.objects.create(book=not_due_book, barcode="CRIT-COPY-ND-1", status=CopyStatus.ON_LOAN)
        self.not_due_loan = Loan.objects.create(
            member=self.member,
            copy=not_due_copy,
            due_at=timezone.now() + timedelta(days=4),
            status=LoanStatus.ACTIVE,
            loaned_by=self.admin_user,
        )
        self.policy, _ = LibraryPolicy.objects.get_or_create(name="default")
        log_audit_event(
            target=self.fine,
            action_type="FINE_CREATED_MANUAL",
            actor=self.admin_user,
            source_screen="test.admin.critical_smoke",
        )
        log_audit_event(
            target=self.policy,
            action_type="POLICY_UPDATED_MANUAL",
            actor=self.admin_user,
            source_screen="test.admin.critical_smoke",
        )

    def test_fine_and_policy_admin_pages_show_timeline_surfaces(self):
        self.client.force_login(self.admin_user)

        fine_list = self.client.get("/admin/fines/fine/")
        self.assertEqual(fine_list.status_code, 200)
        self.assertContains(fine_list, "Aktiviteti i fundit")
        self.assertContains(fine_list, "Gjobë e krijuar manualisht")

        fine_change = self.client.get(f"/admin/fines/fine/{self.fine.id}/change/")
        self.assertEqual(fine_change.status_code, 200)
        self.assertContains(fine_change, "Kronologjia e auditimit")
        self.assertContains(fine_change, "Ndrysho gjobën")

        policy_change = self.client.get(f"/admin/policies/librarypolicy/{self.policy.id}/change/")
        self.assertEqual(policy_change.status_code, 200)
        self.assertContains(policy_change, "Timeline")

    def test_fine_add_form_filters_to_overdue_loans_and_returns_member_preview(self):
        self.client.force_login(self.admin_user)

        add_resp = self.client.get("/admin/fines/fine/add/")
        self.assertEqual(add_resp.status_code, 200)
        self.assertContains(add_resp, "Only Overdue Loan Book")
        self.assertNotContains(add_resp, "Not Due Loan Book")

        preview_resp = self.client.get(f"/admin/fines/fine/loan-preview/{self.overdue_loan.id}/")
        self.assertEqual(preview_resp.status_code, 200)
        payload = preview_resp.json()
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("member_id"), self.member.id)
        self.assertEqual(payload.get("member_nid"), self.member.national_id)

    def test_payment_add_form_is_albanian_and_shows_fine_preview(self):
        self.client.force_login(self.admin_user)
        Payment.objects.create(
            fine=self.fine,
            amount="10.00",
            method=PaymentMethod.CASH,
            recorded_by=self.admin_user,
        )
        payment_list = self.client.get("/admin/fines/payment/")
        self.assertEqual(payment_list.status_code, 200)
        self.assertContains(payment_list, "Nr. huazimi")
        self.assertContains(payment_list, "Anëtari")
        self.assertContains(payment_list, "Mënyra")
        payment_add = self.client.get("/admin/fines/payment/add/")
        self.assertEqual(payment_add.status_code, 200)
        self.assertContains(payment_add, "Regjistro pagesë të re")
        self.assertContains(payment_add, "Shuma e pagesës")
        self.assertContains(payment_add, "Mënyra e pagesës")
        self.assertContains(payment_add, "fines/payment/fine-preview/")

    def test_payment_updates_fine_to_paid_or_partial(self):
        self.client.force_login(self.admin_user)
        partial_amount = "50.00"
        self.client.post(
            "/admin/fines/payment/add/",
            {
                "fine": self.fine.id,
                "amount": partial_amount,
                "method": PaymentMethod.CASH,
                "reference": "Test pjesshem",
            },
            follow=True,
        )
        self.fine.refresh_from_db()
        self.assertEqual(self.fine.status, FineStatus.UNPAID)

        self.client.post(
            "/admin/fines/payment/add/",
            {
                "fine": self.fine.id,
                "amount": "100.00",
                "method": PaymentMethod.CARD,
                "reference": "Test i plote",
            },
            follow=True,
        )
        self.fine.refresh_from_db()
        self.assertEqual(self.fine.status, FineStatus.PAID)
        self.assertEqual(Payment.objects.filter(fine=self.fine).count(), 2)


class AdminExecutiveDashboardSmokeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_exec_dash",
            email="admin_exec_dash@test.com",
            password="K9#mP2$vLxQw!nR8tY",
        )

    def test_admin_dashboard_contains_executive_overview_section(self):
        self.client.force_login(self.admin_user)
        resp = self.client.get("/admin/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Përmbledhje ekzekutive")
        self.assertContains(resp, "Veprime prioritare sot")
        self.assertContains(resp, "Trend 7d")

    def test_admin_dashboard_contains_in_app_notifications_card(self):
        self.client.force_login(self.admin_user)
        UserNotification.objects.create(
            user=self.admin_user,
            kind=NotificationKind.RESERVATION_NEW_STAFF,
            title="Dash notif ping",
            body="Test body",
        )
        resp = self.client.get("/admin/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Njoftime për ju (në aplikacion)")
        self.assertContains(resp, "Dash notif ping")


class HomeCtaAndCmsDetailTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

    def test_home_hides_become_member_when_authenticated(self):
        u = User.objects.create_user(
            username="member_cta@test.com",
            email="member_cta@test.com",
            password="K9#mP2$vLxQw!nR8tY",
        )
        self.client.force_login(u)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Bëhu anëtar")

    def test_home_shows_become_member_when_anonymous(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Bëhu anëtar")

    def test_cms_detail_pages_ok(self):
        ann = Announcement.objects.create(
            title="Njoftim test",
            excerpt="Hyrje",
            content="Teksti i plotë.",
            published_at=self.now,
            is_published=True,
        )
        ev = Event.objects.create(
            title="Event test",
            excerpt="Përshkrim",
            content="Detaje eventi.",
            published_at=self.now,
            is_published=True,
            location="Biblioteka",
        )
        wb = WeeklyBook.objects.create(
            title="Libër jave test",
            excerpt="Shkurt",
            content="Përmbajtje.",
            author="Autor X",
            published_at=self.now,
            is_published=True,
        )
        for url in (f"/njoftime/{ann.id}/", f"/evente/{ev.id}/", f"/libri-i-javes/{wb.id}/"):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, msg=url)
            self.assertContains(resp, "Kthehu")

    def test_cms_detail_404_when_unpublished(self):
        ann = Announcement.objects.create(
            title="Draft",
            excerpt="",
            content="",
            published_at=self.now,
            is_published=False,
        )
        r = self.client.get(f"/njoftime/{ann.id}/")
        self.assertEqual(r.status_code, 404)
