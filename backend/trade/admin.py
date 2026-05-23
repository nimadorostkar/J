# === FILE: backend/trade/admin.py ===
from django.contrib import admin

from .models import BotSession


@admin.register(BotSession)
class BotSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "bot_type", "status",
        "fee_amount_hcoin", "profit_amount_hcoin",
        "started_at", "completes_at", "completed_at",
    )
    list_filter = ("status", "bot_type")
    search_fields = ("user__email", "id")
    readonly_fields = (
        "id", "user", "bot_type", "status",
        "balance_at_start_hcoin",
        "fee_percent", "fee_amount_hcoin", "fee_transaction",
        "duration_seconds",
        "profit_min_percent", "profit_max_percent",
        "profit_percent", "profit_amount_hcoin", "profit_transaction",
        "started_at", "completes_at", "completed_at",
    )
    ordering = ("-started_at",)

    def has_add_permission(self, request):
        # Sessions must be created via the API/service path so the wallet
        # debit and fee Transaction land atomically.
        return False
