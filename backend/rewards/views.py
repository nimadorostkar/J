# === FILE: backend/rewards/views.py ===
"""Reward cycle endpoints: read, activate, claim, global."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_tx
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_audit
from referrals.services import distribute_commission
from transactions.models import Transaction
from wallet.models import Wallet

from .models import GlobalCycle, RewardCycle
from .serializers import GlobalCycleSerializer, RewardCycleSerializer


def _ensure_global_cycle():
    """Make sure a current global cycle exists; create one if not."""
    now = timezone.now()
    gc = GlobalCycle.objects.filter(is_active=True, end_time__gt=now).first()
    if gc:
        return gc
    GlobalCycle.objects.filter(is_active=True).update(is_active=False)
    return GlobalCycle.objects.create(
        label="Season",
        start_time=now,
        end_time=now + timedelta(days=settings.GLOBAL_CYCLE_DAYS),
        is_active=True,
    )


class RewardCycleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle = (
            RewardCycle.objects.filter(user=request.user)
            .exclude(status=RewardCycle.STATUS_CLAIMED)
            .order_by("-started_at")
            .first()
        )
        wallet = Wallet.objects.filter(user=request.user).first()
        if cycle:
            return Response(RewardCycleSerializer(cycle).data)
        return Response({
            "active": False,
            "status": None,
            "endTime": None,
            "durationMs": (wallet.reward_duration_hours if wallet else settings.REWARD_DURATION_HOURS) * 3600 * 1000,
            "rewardTokens": str(Decimal(settings.REWARD_AMOUNT_HCOIN)),
        })


class ActivateCycleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        with db_tx.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            existing = RewardCycle.objects.select_for_update().filter(
                user=request.user,
                status__in=[RewardCycle.STATUS_ACTIVE, RewardCycle.STATUS_CLAIMABLE],
            ).first()
            if existing:
                return Response(
                    {"code": "CYCLE_ACTIVE",
                     "message": "A reward cycle is already active."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            now = timezone.now()
            cycle = RewardCycle.objects.create(
                user=request.user,
                ends_at=now + timedelta(hours=wallet.reward_duration_hours),
                reward_amount_hcoin=Decimal(settings.REWARD_AMOUNT_HCOIN),
                status=RewardCycle.STATUS_ACTIVE,
            )
            wallet.reward_active = True
            wallet.reward_end_time = cycle.ends_at
            wallet.save(update_fields=["reward_active", "reward_end_time", "updated_at"])
        return Response(RewardCycleSerializer(cycle).data, status=status.HTTP_201_CREATED)


class ClaimCycleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        idem_key = request.headers.get("Idempotency-Key")

        with db_tx.atomic():
            cycle = (
                RewardCycle.objects.select_for_update()
                .filter(
                    user=request.user,
                    status__in=[RewardCycle.STATUS_ACTIVE, RewardCycle.STATUS_CLAIMABLE],
                )
                .order_by("-started_at")
                .first()
            )
            if not cycle:
                return Response(
                    {"code": "NO_CYCLE", "message": "No active reward cycle."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            now = timezone.now()
            if cycle.ends_at > now:
                return Response(
                    {"code": "CYCLE_NOT_READY",
                     "message": "Reward cycle has not ended yet.",
                     "endTime": cycle.ends_at.isoformat()},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            wallet = Wallet.objects.select_for_update().get(user=request.user)
            amount = cycle.reward_amount_hcoin
            wallet.h_coin_balance = wallet.h_coin_balance + amount
            wallet.reward_active = False
            wallet.reward_end_time = None
            wallet.save(update_fields=[
                "h_coin_balance", "reward_active", "reward_end_time", "updated_at"
            ])

            cycle.status = RewardCycle.STATUS_CLAIMED
            cycle.claimed_at = now
            cycle.save(update_fields=["status", "claimed_at"])

            tx = Transaction.objects.create(
                user=request.user,
                wallet=wallet,
                type=Transaction.TYPE_REWARD,
                network=None,
                amount_hcoin=amount,
                status=Transaction.STATUS_COMPLETED,
                idempotency_key=idem_key,
            )
            log_audit("reward_claim", user=request.user,
                      tx_id=str(tx.id), amount=str(amount))

            # Pay out referral commission INSIDE the same atomic block.
            distribute_commission(request.user, amount)

        # WS notifications (outside the atomic block is fine — DB already committed)
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            layer = get_channel_layer()
            if layer:
                async_to_sync(layer.group_send)(
                    f"wallet_{request.user.id}",
                    {
                        "type": "balance_update",
                        "h_coins": str(wallet.h_coin_balance),
                        "usdt_balance": str(wallet.usdt_balance),
                    },
                )
        except Exception:
            pass

        return Response({
            "tokens": str(amount),
            "transaction": {
                "id": str(tx.id),
                "type": tx.type,
                "amount_hcoin": str(tx.amount_hcoin),
                "status": tx.status,
                "date": tx.created_at,
            },
        })


class GlobalCycleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        gc = _ensure_global_cycle()
        return Response({"endTime": gc.end_time, "label": gc.label})
