# === FILE: backend/referrals/admin.py ===
from django.contrib import admin

from .models import Referral


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("inviter", "invited_user", "level",
                    "total_commission_earned_hcoin", "created_at")
    list_filter = ("level",)
    search_fields = ("inviter__email", "invited_user__email")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
