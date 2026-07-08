from django.contrib.auth.password_validation import validate_password
from django.test import TestCase

from accounts.models import MemberProfile, User, UserRole


class MemberProvisioningSecurityTests(TestCase):
    def test_auto_created_user_gets_random_password_not_known_default(self):
        member = MemberProfile.objects.create(full_name="Test Anetar", national_id="TID999001")
        self.assertIsNotNone(member.user_id)
        user = member.user
        self.assertFalse(user.check_password("12345678"))
        # Password is usable (hashed), just not the old shared default.
        self.assertTrue(user.has_usable_password())

    def test_national_id_unique_when_set(self):
        MemberProfile.objects.create(full_name="A One", national_id="UNIQUEID01")
        with self.assertRaises(Exception):
            MemberProfile.objects.create(full_name="A Two", national_id="UNIQUEID01")

    def test_blank_national_id_allowed_multiple(self):
        MemberProfile.objects.create(full_name="Blank One", national_id="")
        MemberProfile.objects.create(full_name="Blank Two", national_id="")
        self.assertEqual(MemberProfile.objects.filter(national_id="").count(), 2)


class SetPasswordApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_pass",
            password="AdminPass!234",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.member_user = User.objects.create_user(
            username="member_pass",
            password="OldPass!23456",
            role=UserRole.MEMBER,
            email="member_pass@test.com",
        )

    def test_set_password_rejects_weak_password(self):
        self.client.force_login(self.admin)
        res = self.client.post(
            f"/admin/accounts/user/{self.member_user.id}/set-password/",
            data='{"password":"12345678"}',
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertFalse(body.get("ok"))

    def test_set_password_generated_returns_once(self):
        self.client.force_login(self.admin)
        res = self.client.post(
            f"/admin/accounts/user/{self.member_user.id}/set-password/",
            data='{"password":""}',
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("generated"))
        self.assertIn("password", body)
        self.member_user.refresh_from_db()
        self.assertTrue(self.member_user.check_password(body["password"]))
        # Generated password should pass Django validators.
        validate_password(body["password"], user=self.member_user)

    def test_set_password_explicit_does_not_echo_password(self):
        self.client.force_login(self.admin)
        new_pw = "StrongPass!99x"
        res = self.client.post(
            f"/admin/accounts/user/{self.member_user.id}/set-password/",
            data=f'{{"password":"{new_pw}"}}',
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body.get("ok"))
        self.assertFalse(body.get("generated"))
        self.assertNotIn("password", body)
