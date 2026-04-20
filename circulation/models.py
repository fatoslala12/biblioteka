from django.db import models
from django.db.models import Q


class LoanStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Aktiv"
    RETURNED = "RETURNED", "I kthyer"


class Loan(models.Model):
    member = models.ForeignKey(
        "accounts.MemberProfile", on_delete=models.PROTECT, related_name="loans", verbose_name="Anëtari"
    )
    copy = models.ForeignKey("catalog.Copy", on_delete=models.PROTECT, related_name="loans", verbose_name="Kopja")

    status = models.CharField(
        max_length=16, choices=LoanStatus.choices, default=LoanStatus.ACTIVE, verbose_name="Statusi"
    )
    loaned_at = models.DateTimeField(auto_now_add=True, verbose_name="Huazuar më")
    due_at = models.DateTimeField(verbose_name="Afati i kthimit")
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name="Kthyer më")

    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Shënim")
    loaned_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_loans",
        verbose_name="Huazuar nga (stafi)",
    )
    returned_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_returns",
        verbose_name="Dorëzuar nga (stafi)",
    )

    renew_count = models.PositiveIntegerField(default=0, verbose_name="Nr. zgjatjeve")

    due_soon_reminder_for = models.DateField(
        null=True,
        blank=True,
        verbose_name="Kujtesë “afati nesër” dërguar për",
        help_text="Data e afatit të kthimit për të cilën është dërguar tashmë njoftimi një ditë para.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Huazim"
        verbose_name_plural = "Huazime"
        indexes = [
            models.Index(fields=["status", "due_at"]),
        ]

    def __str__(self) -> str:
        return f"Loan {self.id} - {self.copy.barcode} ({self.member.member_no})"


class HoldStatus(models.TextChoices):
    WAITING = "WAITING", "Në radhë"
    READY_FOR_PICKUP = "READY_FOR_PICKUP", "Gati për marrje"
    EXPIRED = "EXPIRED", "Skaduar"
    FULFILLED = "FULFILLED", "U realizua"
    CANCELLED = "CANCELLED", "Anuluar"


class Hold(models.Model):
    member = models.ForeignKey("accounts.MemberProfile", on_delete=models.PROTECT, related_name="holds")
    book = models.ForeignKey("catalog.Book", on_delete=models.PROTECT, related_name="holds")

    position = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=HoldStatus.choices, default=HoldStatus.WAITING)

    created_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Rezervim"
        verbose_name_plural = "Rezervime"
        constraints = [
            models.UniqueConstraint(fields=["book", "position"], name="uniq_hold_position_per_book"),
        ]
        indexes = [
            models.Index(fields=["book", "status", "position"]),
            models.Index(fields=["member", "status"]),
        ]

    def __str__(self) -> str:
        return f"Hold {self.id} - {self.book.title} ({self.member.member_no})"


class ReservationStatus(models.TextChoices):
    APPROVED = "APPROVED", "Rezervim i pranuar"
    BORROWED = "BORROWED", "U huazua"
    EXPIRED = "EXPIRED", "Skaduar"
    CANCELLED = "CANCELLED", "Anuluar"


class Reservation(models.Model):
    """
    Reservation approved by staff for a specific date range.
    Later it can be converted to an actual Loan when the member picks up the copy.
    """

    member = models.ForeignKey("accounts.MemberProfile", on_delete=models.PROTECT, related_name="reservations")
    book = models.ForeignKey("catalog.Book", on_delete=models.PROTECT, related_name="reservations")

    pickup_date = models.DateField(verbose_name="Do ta marrë më")
    return_date = models.DateField(verbose_name="Do ta dorëzojë më")

    status = models.CharField(max_length=20, choices=ReservationStatus.choices, default=ReservationStatus.APPROVED)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_reservations",
        verbose_name="Krijuar nga (stafi)",
    )
    borrowed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="borrowed_from_reservations",
        verbose_name="Huazuar nga (stafi)",
    )
    source_request = models.OneToOneField(
        "circulation.ReservationRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservation",
        verbose_name="Kërkesa burimore",
    )
    loan = models.OneToOneField(
        "circulation.Loan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="from_reservation",
        verbose_name="Huazimi",
    )

    pickup_soon_reminder_for = models.DateField(
        null=True,
        blank=True,
        verbose_name="Kujtesë “marrje nesër” dërguar për",
        help_text="Data e marrjes për të cilën është dërguar tashmë njoftimi një ditë para.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rezervim"
        verbose_name_plural = "Rezervime"
        indexes = [
            models.Index(fields=["status", "pickup_date"]),
            models.Index(fields=["book", "status", "pickup_date"]),
            models.Index(fields=["member", "status", "pickup_date"]),
        ]

    def __str__(self) -> str:
        return f"Rezervim {self.id} - {self.book.title} ({self.member.member_no})"


class ReservationRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Në pritje"
    APPROVED = "APPROVED", "Pranuar"
    REJECTED = "REJECTED", "Refuzuar"
    CANCELLED = "CANCELLED", "Anuluar"


class ReservationRequest(models.Model):
    member = models.ForeignKey(
        "accounts.MemberProfile", on_delete=models.PROTECT, related_name="reservation_requests"
    )
    book = models.ForeignKey("catalog.Book", on_delete=models.PROTECT, related_name="reservation_requests")

    status = models.CharField(
        max_length=20, choices=ReservationRequestStatus.choices, default=ReservationRequestStatus.PENDING
    )
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Shënim (opsionale)")

    pickup_date = models.DateField(null=True, blank=True, verbose_name="Do ta marrë më")
    return_date = models.DateField(null=True, blank=True, verbose_name="Do ta dorëzojë më")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_reservation_requests",
        verbose_name="Regjistruar nga (stafi)",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservation_request_decisions",
        verbose_name="Vendosur nga",
    )
    decision_reason = models.CharField(max_length=255, blank=True, default="", verbose_name="Arsye (për refuzim)")

    class Meta:
        verbose_name = "Kërkesë për rezervim"
        verbose_name_plural = "Kërkesa për rezervim"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["member", "status", "created_at"]),
            models.Index(fields=["book", "status", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "book"],
                condition=Q(status=ReservationRequestStatus.PENDING),
                name="uniq_pending_request_per_member_book",
            )
        ]

    def __str__(self) -> str:
        return f"Kërkesë {self.id} - {self.book.title} ({self.member.member_no})"
