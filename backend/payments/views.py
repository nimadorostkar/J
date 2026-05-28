# === FILE: backend/payments/views.py ===
"""Admin-only endpoints for the manual-review withdrawal queue.

GET  /api/v1/payments/admin/withdrawals/pending/      — list withdrawals
                                                        waiting for review.
POST /api/v1/payments/admin/withdrawals/<id>/approve/ — approve + queue payout.
POST /api/v1/payments/admin/withdrawals/<id>/reject/  — refund + mark failed.
GET  /api/v1/payments/admin/gateway/status/           — scanner cursor + RPC health.
"""
from decimal import Decimal

from django.db import transaction as db_tx
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_audit
from transactions.models import Transaction
from transactions.serializers import TransactionSerializer
from transactions.tasks import process_withdrawal
from wallet.models import Wallet

from .gateway import GatewayError, get_client
from .models import GatewayCursor


class PendingWithdrawalsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            Transaction.objects.filter(
                type=Transaction.TYPE_WITHDRAW,
                status=Transaction.STATUS_PENDING,
                requires_admin_review=True,
            )
            .order_by("-created_at")
        )
        # Limit response — pagination is a future enhancement; admins
        # typically see <100 pending at a time.
        rows = qs[:200]
        return Response({
            "count": qs.count(),
            "results": TransactionSerializer(rows, many=True).data,
        })


class ApproveWithdrawalView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, tx_id):
        tx = Transaction.objects.filter(
            id=tx_id, type=Transaction.TYPE_WITHDRAW,
        ).first()
        if not tx:
            return Response({"code": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)
        if tx.status != Transaction.STATUS_PENDING:
            return Response(
                {"code": "INVALID_STATE", "message": f"Withdrawal already in state {tx.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with db_tx.atomic():
            t = Transaction.objects.select_for_update().get(pk=tx.pk)
            t.admin_approved_by = request.user
            t.admin_approved_at = timezone.now()
            t.requires_admin_review = False
            t.save(update_fields=[
                "admin_approved_by", "admin_approved_at",
                "requires_admin_review", "updated_at",
            ])
            log_audit("withdraw_approve", user=request.user, tx_id=str(t.id),
                      amount=str(t.amount_usdt), network=t.network)

        process_withdrawal.delay(str(tx.id))
        return Response(TransactionSerializer(tx).data)


class RejectWithdrawalView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, tx_id):
        reason = (request.data.get("reason") or "Rejected by admin").strip()
        tx = Transaction.objects.filter(
            id=tx_id, type=Transaction.TYPE_WITHDRAW,
        ).first()
        if not tx:
            return Response({"code": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)
        if tx.status != Transaction.STATUS_PENDING:
            return Response(
                {"code": "INVALID_STATE", "message": f"Withdrawal already in state {tx.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with db_tx.atomic():
            t = Transaction.objects.select_for_update().get(pk=tx.pk)
            wallet = Wallet.objects.select_for_update().get(pk=t.wallet_id)
            wallet.h_coin_balance = wallet.h_coin_balance + (t.amount_hcoin or Decimal(0))
            wallet.save(update_fields=["h_coin_balance", "updated_at"])
            t.status = Transaction.STATUS_FAILED
            t.failure_reason = reason[:500]
            t.save(update_fields=["status", "failure_reason", "updated_at"])
            log_audit("withdraw_reject", user=request.user, tx_id=str(t.id), reason=reason)

        return Response(TransactionSerializer(tx).data)


class GatewayStatusView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        out = {"networks": {}}
        for net in ("TRC20", "ERC20"):
            cursor = GatewayCursor.objects.filter(network=net).first()
            entry = {
                "lastBlock": cursor.last_block if cursor else 0,
                "lastScannedAt": cursor.last_scanned_at.isoformat() if cursor and cursor.last_scanned_at else None,
                "errorCount": cursor.error_count if cursor else 0,
                "lastError": cursor.last_error if cursor else "",
                "rpcReachable": None,
                "chainHeight": None,
            }
            try:
                client = get_client(net)
                entry["chainHeight"] = client.get_chain_height()
                entry["rpcReachable"] = True
            except GatewayError as e:
                entry["rpcReachable"] = False
                entry["lastError"] = str(e)
            except Exception as e:
                entry["rpcReachable"] = False
                entry["lastError"] = str(e)
            out["networks"][net] = entry

        from django.conf import settings as dj_settings
        out["dryRun"] = bool(dj_settings.GATEWAY_DRY_RUN)
        out["pendingDeposits"] = Transaction.objects.filter(
            type=Transaction.TYPE_DEPOSIT, status=Transaction.STATUS_PENDING,
        ).count()
        out["pendingReviewWithdrawals"] = Transaction.objects.filter(
            type=Transaction.TYPE_WITHDRAW,
            status=Transaction.STATUS_PENDING,
            requires_admin_review=True,
        ).count()
        out["broadcastWithdrawals"] = Transaction.objects.filter(
            type=Transaction.TYPE_WITHDRAW, status=Transaction.STATUS_PROCESSING,
        ).count()
        return Response(out)
