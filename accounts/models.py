import re

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrator"
    STAFF = "STAFF", "Staf/Librarian"
    MEMBER = "MEMBER", "Anëtar"


class User(AbstractUser):
    role = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.MEMBER)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_reason = models.CharField(max_length=255, blank=True, default="")
    accepted_terms_at = models.DateTimeField(null=True, blank=True)
    accepted_terms_version = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        verbose_name = "Përdorues"
        verbose_name_plural = "Përdorues"


class MemberStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Aktiv"
    SUSPENDED = "SUSPENDED", "Pezulluar"
    BLOCKED = "BLOCKED", "I bllokuar"


class MemberType(models.TextChoices):
    STANDARD = "STANDARD", "Standard"
    STUDENT = "STUDENT", "Student"
    VIP = "VIP", "VIP"


class MemberProfile(models.Model):
    user = models.OneToOneField(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="member_profile",
    )
    member_no = models.CharField(max_length=32, unique=True, blank=True, default="")
    status = models.CharField(max_length=16, choices=MemberStatus.choices, default=MemberStatus.ACTIVE)
    member_type = models.CharField(max_length=16, choices=MemberType.choices, default=MemberType.STANDARD)

    full_name = models.CharField(max_length=160, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")

    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Datëlindja")
    place_of_birth = models.CharField(max_length=160, blank=True, default="", verbose_name="Vendlindja")
    national_id = models.CharField(max_length=32, blank=True, default="", verbose_name="Nr. ID")
    photo = models.ImageField(upload_to="member_photos/", null=True, blank=True, verbose_name="Foto")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _generate_username(self) -> str:
        # full_name -> "emer.mbiemer" (lowercase, ascii)
        full_name = (self.full_name or "").strip()
        parts = [p for p in full_name.replace("_", " ").split() if p]
        if len(parts) >= 2:
            # use "-" so slugify keeps a separator, then convert to "."
            base = f"{parts[0]}-{parts[-1]}"
        elif len(parts) == 1:
            base = parts[0]
        else:
            base = self.member_no

        base = slugify(base, allow_unicode=False).replace("-", ".")
        base = ".".join([p for p in base.split(".") if p])
        base = (base or self.member_no).lower()

        # ensure unique
        candidate = base
        i = 2
        while User.objects.filter(username=candidate).exists():
            candidate = f"{base}{i}"
            i += 1
        return candidate

    def _ensure_user(self) -> None:
        if self.user_id:
            return
        username = self._generate_username()
        user = User.objects.create_user(
            username=username,
            password="12345678",
            role=UserRole.MEMBER,
            is_staff=False,
        )
        # try to fill first/last name
        full_name = (self.full_name or "").strip()
        parts = [p for p in full_name.split() if p]
        if parts:
            user.first_name = parts[0]
            if len(parts) >= 2:
                user.last_name = parts[-1]
            user.save(update_fields=["first_name", "last_name"])
        self.user = user

    @classmethod
    def _next_member_no(cls) -> str:
        # Find max numeric suffix for member_no like "M101" and increment.
        max_n = 0
        for s in cls.objects.exclude(member_no="").values_list("member_no", flat=True):
            m = re.match(r"^M(\d+)$", (s or "").strip())
            if m:
                try:
                    max_n = max(max_n, int(m.group(1)))
                except ValueError:
                    continue
        return f"M{max_n + 1:03d}"

    def save(self, *args, **kwargs):
        if not (self.member_no or "").strip():
            # Prefer stable numbering based on user id if present.
            if self.user_id:
                candidate = f"M{int(self.user_id):03d}"
                if not MemberProfile.objects.filter(member_no=candidate).exists():
                    self.member_no = candidate
                else:
                    self.member_no = MemberProfile._next_member_no()
            else:
                self.member_no = MemberProfile._next_member_no()

        super().save(*args, **kwargs)
        if not self.user_id:
            # create member user if missing
            self._ensure_user()
            super().save(update_fields=["user"])

    def __str__(self) -> str:
        uname = self.user.username if self.user_id else "pa-user"
        return f"{self.member_no} ({uname})"

    class Meta:
        verbose_name = "Profil anëtari"
        verbose_name_plural = "Profile anëtarësh"
