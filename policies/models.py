from django.db import models


class LibraryPolicy(models.Model):
    """
    MVP: one active policy row (named 'default').
    Later we can add multiple policies/branches.
    """

    name = models.CharField(max_length=64, unique=True, default="default")

    fine_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    fine_cap = models.DecimalField(max_digits=10, decimal_places=2, default=200)

    hold_window_hours = models.PositiveIntegerField(default=48)
    max_renewals = models.PositiveIntegerField(default=2)

    default_loan_period_days = models.PositiveIntegerField(default=14)
    default_max_active_loans = models.PositiveIntegerField(default=5)
    reservation_grace_days = models.PositiveIntegerField(
        default=0,
        help_text="Days after pickup_date before approved reservation auto-expires.",
    )
    reservation_warning_hours = models.PositiveIntegerField(
        default=24,
        help_text="Warning window before reservation auto-expiry (hours).",
    )

    fine_block_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=300,
        help_text="If member unpaid fines exceed this threshold, block checkout/renew.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Politikë biblioteke"
        verbose_name_plural = "Politika biblioteke"


class LoanRule(models.Model):
    policy = models.ForeignKey(LibraryPolicy, on_delete=models.CASCADE, related_name="loan_rules")
    member_type = models.CharField(max_length=16)  # matches accounts.MemberType
    book_type = models.CharField(max_length=16)  # matches catalog.BookType

    loan_period_days = models.PositiveIntegerField()
    max_active_loans = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Rregull huazimi"
        verbose_name_plural = "Rregulla huazimi"
        constraints = [
            models.UniqueConstraint(fields=["policy", "member_type", "book_type"], name="uniq_rule_per_policy_member_book"),
        ]

    def __str__(self) -> str:
        return f"{self.policy.name}: {self.member_type}/{self.book_type}"
