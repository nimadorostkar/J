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

    class Meta:
        model = Referral
        fields = ("id", "level", "invitedUser", "totalCommissionEarnedHcoin", "created_at")


class ValidateInviteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)
