from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from pathlib import Path

from accounts.models import MemberProfile, UserRole
from audit.services import log_audit_event
from catalog.models import Book, Copy, CopyStatus
from circulation.models import Loan, LoanStatus, ReservationRequest, ReservationRequestStatus
from fines.models import Fine, FineStatus
from policies.models import LibraryPolicy

User = get_user_model()


@override_settings(RATELIMIT_ENABLE=False)
class MemberSignUpTests(TestCase):
    def setUp(self):
        self.client = Client()

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
            "company_website": "",
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

    def test_honeypot_blocks(self):
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
            "company_website": "http://spam.com",
        }
        r = self.client.post("/regjistrohu/", data)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="bot@test.com").exists())


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
        member = MemberProfile.objects.create(
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
            member=member,
            copy=copy,
            due_at=timezone.now(),
            status=LoanStatus.RETURNED,
            loaned_by=self.admin_user,
        )
        self.fine = Fine.objects.create(
            loan=loan,
            member=member,
            amount="150.00",
            status=FineStatus.UNPAID,
            reason="Overdue",
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
        self.assertContains(fine_change, "Timeline")

        policy_change = self.client.get(f"/admin/policies/librarypolicy/{self.policy.id}/change/")
        self.assertEqual(policy_change.status_code, 200)
        self.assertContains(policy_change, "Timeline")


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
        self.assertContains(resp, "Executive Overview")
        self.assertContains(resp, "Action Needed Today")
        self.assertContains(resp, "7d trend")
