# === FILE: backend/rewards/admin.py ===
from django.contrib import admin

from .models import GlobalCycle, RewardCycle


@admin.register(RewardCycle)
class RewardCycleAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "started_at", "ends_at",
                    "reward_amount_hcoin", "claimed_at")
    list_filter = ("status",)
    search_fields = ("user__email",)
    readonly_fields = ("started_at",)


@admin.register(GlobalCycle)
class GlobalCycleAdmin(admin.ModelAdmin):
    list_display = ("label", "start_time", "end_time", "is_active")
    list_filter = ("is_active",)
