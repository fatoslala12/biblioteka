from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from accounts.models import UserRole

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
