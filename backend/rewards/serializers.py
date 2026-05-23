# === FILE: backend/rewards/serializers.py ===
from django.conf import settings
from rest_framework import serializers

from .models import GlobalCycle, RewardCycle


class RewardCycleSerializer(serializers.ModelSerializer):
    active = serializers.SerializerMethodField()
    endTime = serializers.DateTimeField(source="ends_at")
    durationMs = serializers.SerializerMethodField()
    durationDays = serializers.SerializerMethodField()
    rewardPercent = serializers.SerializerMethodField()
    rewardTokens = serializers.DecimalField(
        source="reward_amount_hcoin", max_digits=18, decimal_places=8
    )

    class Meta:
        model = RewardCycle
        fields = (
            "id", "active", "status", "endTime",
            "durationMs", "durationDays",
            "rewardPercent", "rewardTokens",
        )

    def get_active(self, obj):
        return obj.status in (RewardCycle.STATUS_ACTIVE, RewardCycle.STATUS_CLAIMABLE)

    def get_durationMs(self, obj):
        delta = (obj.ends_at - obj.started_at).total_seconds() * 1000
        return int(delta)

    def get_durationDays(self, obj):
        # Length in days the user sees in the UI
        return int(round(self.get_durationMs(obj) / (24 * 3600 * 1000)))

    def get_rewardPercent(self, obj):
        return settings.REWARD_PERCENT


class GlobalCycleSerializer(serializers.ModelSerializer):
    endTime = serializers.DateTimeField(source="end_time")

    class Meta:
        model = GlobalCycle
        fields = ("id", "label", "endTime", "start_time", "is_active")
        read_only_fields = fields
