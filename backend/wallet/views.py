# === FILE: backend/wallet/views.py ===
"""Wallet endpoints: balance, transactions, networks, deposit, withdraw."""
import io
import uuid
from decimal import Decimal

import qrcode
from django.conf import settings
from django.core.cache import cache
from django.db import transaction as db_tx
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.audit import log_audit
from transactions.models import Transaction
from transactions.serializers import TransactionSerializer
from transactions.tasks import process_withdrawal, verify_deposit

from .address_utils import validate_address
from .models import DepositAddress, Wallet
from .serializers import (
    AdminManualDepositSerializer,
    DepositInitSerializer,
    WalletSerializer,
    WithdrawInitSerializer,
)
from .services import (
    admin_credit_manual_deposit,
    assert_can_withdraw,
    check_withdrawal_eligibility,
    debit_usdt,
)
from payments.services import (
    WithdrawalLimitError,
    assert_within_withdrawal_limits,
    requires_admin_review,
)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        return Response(WalletSerializer(wallet).data)


class TransactionsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.pagination import CursorPagination

        qs = Transaction.objects.filter(user=request.user).select_related("commission_from_user")
        type_filter = request.query_params.get("type")
        if type_filter:
            qs = qs.filter(type=type_filter)
        qs = qs.order_by("-created_at")
        paginator = CursorPagination()
        paginated = paginator.paginate_queryset(qs, request)
        ser = TransactionSerializer(paginated, many=True)
        return paginator.get_paginated_response(ser.data)


class NetworksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([
            {
                "id": "TRC20",
                "name": "Tron (TRC20)",
                "fee": str(Decimal(settings.WITHDRAWAL_FEE_USDT)),
                "minDeposit": str(Decimal(settings.MIN_DEPOSIT_USDT)),
            },
            {
                "id": "ERC20",
                "name": "Ethereum (ERC20)",
                "fee": str(Decimal(settings.WITHDRAWAL_FEE_USDT)),
                "minDeposit": str(Decimal(settings.MIN_DEPOSIT_USDT)),
            },
        ])


class DepositAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        network = request.query_params.get("network", "TRC20").upper()
        if network not in {"TRC20", "ERC20"}:
            return Response(
                {"code": "INVALID_NETWORK", "message": "Network must be TRC20 or ERC20."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Prefer per-user address (if ops assigned one), else fall back to env wallet
        da = DepositAddress.objects.filter(
            user=request.user, network=network, is_active=True
        ).first()
        if da:
            address = da.address
        else:
            address = settings.USDT_TRC20_WALLET if network == "TRC20" else settings.USDT_ERC20_WALLET

        qr_url = request.build_absolute_uri(
            f"/api/v1/wallet/deposit-address/qr/?network={network}"
        )
        return Response({
            "address": address,
            "network": network,
            "qrCodeUrl": qr_url,
            "minimum": str(Decimal(settings.MIN_DEPOSIT_USDT)),
        })


class DepositAddressQRView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        network = request.query_params.get("network", "TRC20").upper()
        address = settings.USDT_TRC20_WALLET if network == "TRC20" else settings.USDT_ERC20_WALLET
        img = qrcode.make(address or "no-address")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return HttpResponse(buf.getvalue(), content_type="image/png")


class DepositInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = DepositInitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        amount = ser.validated_data["amountUsdt"]
        network = ser.validated_data["network"]
        tx_hash = ser.validated_data.get("txHash") or None

        idem_key = request.headers.get("Idempotency-Key") or str(uuid.uuid4())

        # Idempotency check
        existing = Transaction.objects.filter(
            user=request.user, idempotency_key=idem_key
        ).first()
        if existing:
            return Response(TransactionSerializer(existing).data, status=status.HTTP_200_OK)

        with db_tx.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            tx = Transaction.objects.create(
                user=request.user,
                wallet=wallet,
                type="deposit",
                network=network,
                amount_usdt=amount,
                amount_hcoin=amount / Decimal(settings.USDT_PER_HCOIN),
                tx_hash=tx_hash,
                status="pending",
                idempotency_key=idem_key,
                ip_address=_client_ip(request),
            )
            log_audit("deposit_init", user=request.user, ip=_client_ip(request),
                      tx_id=str(tx.id), amount=str(amount), network=network)

        # Kick off blockchain verification asynchronously
        verify_deposit.delay(str(tx.id))
        return Response(TransactionSerializer(tx).data, status=status.HTTP_202_ACCEPTED)


class DepositStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, tx_id):
        tx = Transaction.objects.filter(id=tx_id, user=request.user, type="deposit").first()
        if not tx:
            return Response({"code": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)
        return Response(TransactionSerializer(tx).data)


class WithdrawThrottle(UserRateThrottle):
    rate = "3/min"


class WithdrawInitView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [WithdrawThrottle]

    def post(self, request):
        ser = WithdrawInitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        network = ser.validated_data["network"]
        addr = ser.validated_data["address"].strip()
        tokens = ser.validated_data["tokens"]

        # Gate first — raises WithdrawalLocked which the global handler converts to 403
        assert_can_withdraw(request.user)

        if not validate_address(network, addr):
            return Response(
                {"code": "INVALID_ADDRESS",
                 "message": f"Invalid {network} wallet address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_usdt = tokens * Decimal(settings.USDT_PER_HCOIN)
        fee = Decimal(settings.WITHDRAWAL_FEE_USDT)
        net_amount = amount_usdt - fee

        # Per-tx min/max + 24h daily cap (raises WithdrawalLimitError).
        try:
            assert_within_withdrawal_limits(request.user, amount_usdt=amount_usdt)
        except WithdrawalLimitError as e:
            return Response(
                {"code": e.code, "message": e.message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        idem_key = request.headers.get("Idempotency-Key") or str(uuid.uuid4())
        existing = Transaction.objects.filter(
            user=request.user, idempotency_key=idem_key
        ).first()
        if existing:
            return Response(TransactionSerializer(existing).data, status=status.HTTP_200_OK)

        needs_review = requires_admin_review(amount_usdt)

        with db_tx.atomic():
            # Debit H Coins (raises InsufficientBalance if not enough)
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            if wallet.h_coin_balance < tokens:
                return Response(
                    {"code": "INSUFFICIENT_BALANCE",
                     "message": "Insufficient H Coin balance for this withdrawal."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            wallet.h_coin_balance = wallet.h_coin_balance - tokens
            wallet.save(update_fields=["h_coin_balance", "updated_at"])

            tx = Transaction.objects.create(
                user=request.user,
                wallet=wallet,
                type="withdraw",
                network=network,
                amount_usdt=net_amount,
                amount_hcoin=tokens,
                wallet_address=addr,
                status="pending",
                requires_admin_review=needs_review,
                network_fee_usdt=fee,
                idempotency_key=idem_key,
                ip_address=_client_ip(request),
            )
            log_audit("withdraw_init", user=request.user, ip=_client_ip(request),
                      tx_id=str(tx.id), amount=str(amount_usdt), network=network,
                      address=addr[:8] + "...", needs_admin_review=needs_review)

        # Auto-broadcast only if both the env flag is set AND the
        # amount is below the admin-review threshold.
        if settings.WITHDRAWAL_AUTO_APPROVE and not needs_review:
            process_withdrawal.delay(str(tx.id))

        return Response(TransactionSerializer(tx).data, status=status.HTTP_202_ACCEPTED)


class WithdrawStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, tx_id):
        tx = Transaction.objects.filter(id=tx_id, user=request.user, type="withdraw").first()
        if not tx:
            return Response({"code": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)
        return Response(TransactionSerializer(tx).data)


class WithdrawEligibilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(check_withdrawal_eligibility(request.user).to_dict())


class AdminManualDepositView(APIView):
    """Admin-only endpoint that credits a user's wallet as a real deposit.

    POST /api/v1/wallet/admin/manual-deposit/

    Body (JSON):
        userId     (int)     — target user, OR
        userEmail  (str)     — target user (alternative to userId),
        amountUsdt (decimal) — positive USDT amount,
        note       (str)     — optional internal note (audit log only).

    Headers (optional):
        Idempotency-Key      — UUID; safe to retry with the same value.

    Response (201): TransactionSerializer of the created (completed) deposit.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        ser = AdminManualDepositSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        User = get_user_model()
        target = None
        if v.get("userId"):
            # User.id is a UUID — an invalid string would otherwise raise
            # ValidationError from the DB layer, surfacing as a 500.
            try:
                target = User.objects.filter(pk=v["userId"]).first()
            except (ValueError, ValidationError):
                target = None
        elif v.get("userEmail"):
            target = User.objects.filter(email__iexact=v["userEmail"]).first()
        if not target:
            return Response(
                {"code": "USER_NOT_FOUND", "message": "Target user not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Make sure the user has a Wallet — same as DepositInitView/WalletView do.
        Wallet.objects.get_or_create(user=target)

        try:
            tx = admin_credit_manual_deposit(
                admin_user=request.user,
                target_user=target,
                amount_usdt=v["amountUsdt"],
                note=v.get("note", ""),
                idempotency_key=request.headers.get("Idempotency-Key"),
                ip=_client_ip(request),
            )
        except (ValueError, PermissionError) as e:
            return Response(
                {"code": "INVALID_REQUEST", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(TransactionSerializer(tx).data, status=status.HTTP_201_CREATED)
