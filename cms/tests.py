from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client, TestCase, override_settings
from pathlib import Path

from accounts.models import MemberProfile, UserRole

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
