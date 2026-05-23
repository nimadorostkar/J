# === FILE: backend/referrals/serializers.py ===
from rest_framework import serializers

from .models import Referral


class InvitedUserMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    email = serializers.EmailField()
    avatarUrl = serializers.SerializerMethodField()
    joinedAt = serializers.DateTimeField(source="created_at")
    isEmailVerified = serializers.BooleanField(source="is_email_verified")

    def get_avatarUrl(self, obj):
        try:
            return obj.avatar.url if obj.avatar else None
        except Exception:
            return None


class ReferralRowSerializer(serializers.ModelSerializer):
    invitedUser = InvitedUserMiniSerializer(source="invited_user")
    totalCommissionEarnedHcoin = serializers.DecimalField(
        source="total_commission_earned_hcoin",
        max_digits=18, decimal_places=8,
    )
    # Status flags — surface so the frontend can show badges per node.
    isVerified = serializers.SerializerMethodField()
    hasDeposit = serializers.SerializerMethodField()
    isQualified = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = (
            "id", "level", "invitedUser", "totalCommissionEarnedHcoin", "created_at",
            "isVerified", "hasDeposit", "isQualified", "status",
        )

    def _has_deposit(self, obj):
        # Prefer annotated value (from ReferralQuerySet.with_status_flags)
        # to avoid N+1 queries when serializing a list.
        if hasattr(obj, "_has_deposit") and obj._has_deposit is not None:
            return bool(obj._has_deposit)
        return obj.has_completed_deposit()

    def get_hasDeposit(self, obj):
        return self._has_deposit(obj)

    def get_isVerified(self, obj):
        if hasattr(obj, "_is_verified") and obj._is_verified is not None:
            return bool(obj._is_verified)
        return bool(getattr(obj.invited_user, "is_email_verified", False))

    def get_isQualified(self, obj):
        return obj.level == 1 and self._has_deposit(obj)

    def get_status(self, obj):
        if self.get_isQualified(obj):
            return "qualified"
        if self._has_deposit(obj):
            return "first_deposit_completed"
        if self.get_isVerified(obj):
            return "verified"
        return "registered"


class ValidateInviteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)
