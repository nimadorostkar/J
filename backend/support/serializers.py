# === FILE: backend/support/serializers.py ===
from rest_framework import serializers

from .models import FAQ, Ticket, TicketMessage


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ("id", "question", "answer", "category", "order")


class TicketMessageSerializer(serializers.ModelSerializer):
    isStaff = serializers.BooleanField(source="is_staff", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = TicketMessage
        fields = ("id", "body", "isStaff", "createdAt")
        read_only_fields = ("id", "isStaff", "createdAt")


class TicketSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Ticket
        fields = ("id", "subject", "category", "status", "createdAt", "updatedAt", "messages")
        read_only_fields = ("id", "status", "createdAt", "updatedAt", "messages")


class CreateTicketSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    category = serializers.CharField(max_length=64, required=False, allow_blank=True)
    body = serializers.CharField()
