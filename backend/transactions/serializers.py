# === FILE: backend/transactions/serializers.py ===
from rest_framework import serializers

from .models import Transaction


class CommissionFromUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    firstName = serializers.CharField(source="first_name")


class TransactionSerializer(serializers.ModelSerializer):
    amount_usdt = serializers.DecimalField(max_digits=18, decimal_places=8, allow_null=True)
    amount_hcoin = serializers.DecimalField(max_digits=18, decimal_places=8)
    from_user = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id", "type", "description", "network",
            "amount_usdt", "amount_hcoin",
            "wallet_address", "tx_hash", "status",
            "commission_level", "commission_rate", "from_user",
            "date",
        )
        read_only_fields = fields

    def get_from_user(self, obj):
        if obj.type != Transaction.TYPE_COMMISSION or not obj.commission_from_user_id:
            return None
        u = obj.commission_from_user
        return {"id": str(u.id), "firstName": u.first_name}

    def get_description(self, obj):
        if obj.type == Transaction.TYPE_DEPOSIT:
            return f"Deposit via {obj.network}"
        if obj.type == Transaction.TYPE_WITHDRAW:
            return f"Withdraw via {obj.network}"
        if obj.type == Transaction.TYPE_REWARD:
            return "Reward cycle claim"
        if obj.type == Transaction.TYPE_COMMISSION and obj.commission_from_user_id:
            return (f"Commission from {obj.commission_from_user.first_name}'s "
                    f"reward (Level {obj.commission_level})")
        return obj.get_type_display()
