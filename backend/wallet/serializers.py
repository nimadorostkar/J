# === FILE: backend/wallet/serializers.py ===
from decimal import Decimal

from django.conf import settings
from rest_framework import serializers

from .models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    hCoins = serializers.DecimalField(
        source="h_coin_balance", max_digits=18, decimal_places=8, read_only=True
    )
    usdtBalance = serializers.DecimalField(
        source="usdt_balance", max_digits=18, decimal_places=8, read_only=True
    )
    usdtEquivalent = serializers.SerializerMethodField()
    rewardActive = serializers.BooleanField(source="reward_active", read_only=True)
    rewardEndTime = serializers.DateTimeField(source="reward_end_time", read_only=True)
    rewardDurationHours = serializers.IntegerField(source="reward_duration_hours", read_only=True)
    hasDeposit = serializers.BooleanField(source="has_completed_deposit", read_only=True)
    hasReferral = serializers.BooleanField(source="has_referral", read_only=True)
    conversionRate = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = (
            "hCoins", "usdtBalance", "usdtEquivalent",
            "rewardActive", "rewardEndTime", "rewardDurationHours",
            "hasDeposit", "hasReferral", "conversionRate",
        )

    def get_usdtEquivalent(self, obj):
        return str((obj.h_coin_balance * Decimal(settings.USDT_PER_HCOIN)).quantize(Decimal("0.00000001")))

    def get_conversionRate(self, obj):
        return settings.USDT_PER_HCOIN


class DepositInitSerializer(serializers.Serializer):
    network = serializers.ChoiceField(choices=["TRC20", "ERC20"])
    amountUsdt = serializers.DecimalField(max_digits=18, decimal_places=8, min_value=Decimal("0"))
    txHash = serializers.CharField(required=False, allow_blank=True)

    def validate_amountUsdt(self, value):
        if value < Decimal(settings.MIN_DEPOSIT_USDT):
            raise serializers.ValidationError(
                f"Minimum deposit is {settings.MIN_DEPOSIT_USDT} USDT."
            )
        return value


class WithdrawInitSerializer(serializers.Serializer):
    network = serializers.ChoiceField(choices=["TRC20", "ERC20"])
    address = serializers.CharField(max_length=128)
    tokens = serializers.DecimalField(max_digits=18, decimal_places=8, min_value=Decimal("0.00000001"))


class AdminManualDepositSerializer(serializers.Serializer):
    """Body for POST /api/v1/wallet/admin/manual-deposit/.

    Accepts EITHER `userId` (preferred) OR `userEmail` to look up the target.
    """
    userId = serializers.IntegerField(required=False)
    userEmail = serializers.CharField(required=False, allow_blank=False, max_length=254)
    amountUsdt = serializers.DecimalField(
        max_digits=18, decimal_places=8, min_value=Decimal("0.00000001"),
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, data):
        if not data.get("userId") and not data.get("userEmail"):
            raise serializers.ValidationError(
                {"user": "Provide userId or userEmail."}
            )
        return data
