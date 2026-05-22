# === FILE: backend/transactions/views.py ===
"""Webhook endpoints (signed by blockchain provider) and detail view."""
import hashlib
import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Transaction
from .tasks import verify_deposit


def _verify_signature(request) -> bool:
    """Verify HMAC signature header `X-Webhook-Signature`."""
    received = request.headers.get("X-Webhook-Signature", "")
    secret = (settings.BLOCKCHAIN_WEBHOOK_SECRET or "").encode()
    if not received or not secret:
        return False
    body = request.body or b""
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)


class BlockchainWebhookView(APIView):
    """Provider posts {tx_hash, address, amount, network, confirmations}."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _verify_signature(request):
            return Response(
                {"code": "INVALID_SIGNATURE"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        tx_hash = request.data.get("tx_hash")
        if not tx_hash:
            return Response({"code": "MISSING_TX_HASH"}, status=status.HTTP_400_BAD_REQUEST)
        tx = Transaction.objects.filter(tx_hash=tx_hash).first()
        if not tx:
            return Response({"received": True, "matched": False})
        # Re-verify on-chain asynchronously
        verify_deposit.delay(str(tx.id))
        return Response({"received": True, "matched": True})
