from django.db import models


class FineStatus(models.TextChoices):
    UNPAID = "UNPAID", "E papaguar"
    PAID = "PAID", "E paguar"
    WAIVED = "WAIVED", "E falur"


class Fine(models.Model):
    loan = models.OneToOneField("circulation.Loan", on_delete=models.PROTECT, related_name="fine")
    member = models.ForeignKey("accounts.MemberProfile", on_delete=models.PROTECT, related_name="fines")

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=FineStatus.choices, default=FineStatus.UNPAID)
    reason = models.CharField(max_length=255, blank=True, default="Vonesë")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    waived_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="waived_fines",
    )
    waived_reason = models.CharField(max_length=255, blank=True, default="")

    def __str__(self) -> str:
        return f"Gjoba #{self.id} - {self.member.member_no} - {self.amount} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Gjobë"
        verbose_name_plural = "Gjoba"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Para në dorë"
    CARD = "CARD", "Kartë"
    OTHER = "OTHER", "Tjetër"


class Payment(models.Model):
    fine = models.ForeignKey(Fine, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference = models.CharField(max_length=120, blank=True, default="")
    recorded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="recorded_payments")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Pagesa #{self.id} - {self.amount} ({self.get_method_display()})"

    class Meta:
        verbose_name = "Pagesë"
        verbose_name_plural = "Pagesa"
