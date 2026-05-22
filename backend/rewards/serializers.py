# === FILE: backend/rewards/serializers.py ===
from rest_framework import serializers

from .models import GlobalCycle, RewardCycle


class RewardCycleSerializer(serializers.ModelSerializer):
    active = serializers.SerializerMethodField()
    endTime = serializers.DateTimeField(source="ends_at")
    durationMs = serializers.SerializerMethodField()
    rewardTokens = serializers.DecimalField(
        source="reward_amount_hcoin", max_digits=18, decimal_places=8
    )

    class Meta:
        model = RewardCycle
        fields = ("id", "active", "status", "endTime", "durationMs", "rewardTokens")

    def get_active(self, obj):
        return obj.status in (RewardCycle.STATUS_ACTIVE, RewardCycle.STATUS_CLAIMABLE)

    def get_durationMs(self, obj):
        delta = (obj.ends_at - obj.started_at).total_seconds() * 1000
        return int(delta)


class GlobalCycleSerializer(serializers.ModelSerializer):
    endTime = serializers.DateTimeField(source="end_time")

    class Meta:
        model = GlobalCycle
        fields = ("id", "label", "endTime", "start_time", "is_active")
        read_only_fields = fields
