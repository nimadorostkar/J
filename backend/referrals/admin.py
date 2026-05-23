# === FILE: backend/referrals/admin.py ===
from django.contrib import admin

from .models import Referral, ReferralMilestoneReward


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        "inviter", "invited_user", "level", "status_display",
        "has_deposit_display", "total_commission_earned_hcoin", "created_at",
    )
    list_filter = ("level",)
    search_fields = ("inviter__email", "invited_user__email")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        # Pre-annotate so list_display doesn't issue N+1 queries.
        qs = super().get_queryset(request)
        return qs.with_status_flags() if hasattr(qs, "with_status_flags") else qs

    @admin.display(boolean=True, description="Has deposit?")
    def has_deposit_display(self, obj):
        if hasattr(obj, "_has_deposit") and obj._has_deposit is not None:
            return bool(obj._has_deposit)
        return obj.has_completed_deposit()

    @admin.display(description="Status")
    def status_display(self, obj):
        # Same vocabulary the API exposes.
        return obj.status_label()


@admin.register(ReferralMilestoneReward)
class ReferralMilestoneRewardAdmin(admin.ModelAdmin):
    list_display = (
        "user", "milestone", "amount_hcoin",
        "transaction", "awarded_at",
    )
    list_filter = ("milestone",)
    search_fields = ("user__email",)
    readonly_fields = ("awarded_at", "user", "milestone",
                       "amount_hcoin", "transaction")
    ordering = ("-awarded_at",)

    def has_add_permission(self, request):
        # Milestone rewards must never be hand-created from the admin —
        # they're awarded by the milestone service inside an atomic block
        # with proper wallet credit + Transaction row.
        return False

    def has_delete_permission(self, request, obj=None):
        # Deleting a row here would let the system pay the same milestone
        # twice. Keep this read-only.
        return False
