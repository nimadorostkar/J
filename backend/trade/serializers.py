# === FILE: backend/trade/serializers.py ===
from rest_framework import serializers

from .models import BotSession


class BotSessionSerializer(serializers.ModelSerializer):
    """Read-only serializer for surfacing a BotSession to the API."""

    botType = serializers.CharField(source="bot_type")
    botLabel = serializers.SerializerMethodField()
    balanceAtStartHcoin = serializers.DecimalField(
        source="balance_at_start_hcoin", max_digits=18, decimal_places=8,
    )
    feePercent = serializers.DecimalField(
        source="fee_percent", max_digits=5, decimal_places=2,
    )
    feeAmountHcoin = serializers.DecimalField(
        source="fee_amount_hcoin", max_digits=18, decimal_places=8,
    )
    profitMinPercent = serializers.DecimalField(
        source="profit_min_percent", max_digits=5, decimal_places=2,
    )
    profitMaxPercent = serializers.DecimalField(
        source="profit_max_percent", max_digits=5, decimal_places=2,
    )
    profitPercent = serializers.DecimalField(
        source="profit_percent", max_digits=5, decimal_places=2,
        allow_null=True,
    )
    profitAmountHcoin = serializers.DecimalField(
        source="profit_amount_hcoin", max_digits=18, decimal_places=8,
        allow_null=True,
    )
    durationSeconds = serializers.IntegerField(source="duration_seconds")
    startedAt = serializers.DateTimeField(source="started_at")
    completesAt = serializers.DateTimeField(source="completes_at")
    completedAt = serializers.DateTimeField(source="completed_at", allow_null=True)
    feeTransactionId = serializers.UUIDField(source="fee_transaction_id", allow_null=True)
    profitTransactionId = serializers.UUIDField(source="profit_transaction_id", allow_null=True)

    class Meta:
        model = BotSession
        fields = (
            "id", "botType", "botLabel", "status",
            "balanceAtStartHcoin",
            "feePercent", "feeAmountHcoin",
            "profitMinPercent", "profitMaxPercent",
            "profitPercent", "profitAmountHcoin",
            "durationSeconds",
            "startedAt", "completesAt", "completedAt",
            "feeTransactionId", "profitTransactionId",
        )
        read_only_fields = fields

    def get_botLabel(self, obj):
        return obj.get_bot_type_display()


class ActivateBotSerializer(serializers.Serializer):
    botType = serializers.ChoiceField(choices=[BotSession.BOT_BASIC, BotSession.BOT_EXPERT])
