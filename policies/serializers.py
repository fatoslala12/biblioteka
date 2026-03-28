from rest_framework import serializers

from .models import LibraryPolicy, LoanRule


class LoanRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRule
        fields = ("id", "member_type", "book_type", "loan_period_days", "max_active_loans")


class LibraryPolicySerializer(serializers.ModelSerializer):
    loan_rules = LoanRuleSerializer(many=True, read_only=True)

    class Meta:
        model = LibraryPolicy
        fields = (
            "id",
            "name",
            "fine_per_day",
            "fine_cap",
            "hold_window_hours",
            "max_renewals",
            "default_loan_period_days",
            "default_max_active_loans",
            "reservation_grace_days",
            "reservation_warning_hours",
            "fine_block_threshold",
            "loan_rules",
        )
