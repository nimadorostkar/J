# === FILE: backend/wallet/admin.py ===
from django.contrib import admin
from django.utils import timezone

from .models import DepositAddress, Wallet


@admin.action(description="Reset reward cycle")
def reset_reward_cycle(modeladmin, request, queryset):
    queryset.update(reward_active=False, reward_end_time=None)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "h_coin_balance", "usdt_balance",
                    "reward_active", "has_completed_deposit", "has_referral",
                    "updated_at")
    list_filter = ("reward_active", "has_completed_deposit", "has_referral")
    search_fields = ("user__email",)
    readonly_fields = ("updated_at",)
    actions = [reset_reward_cycle]


@admin.register(DepositAddress)
class DepositAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "network", "address", "is_active", "created_at")
    list_filter = ("network", "is_active")
    search_fields = ("address", "user__email")
