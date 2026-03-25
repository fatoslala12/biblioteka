from django.contrib import admin

from .models import LibraryPolicy, LoanRule


class LoanRuleInline(admin.TabularInline):
    model = LoanRule
    extra = 0


@admin.register(LibraryPolicy)
class LibraryPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "fine_per_day", "fine_cap", "hold_window_hours", "max_renewals", "fine_block_threshold")
    inlines = [LoanRuleInline]
