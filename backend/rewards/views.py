# === FILE: backend/rewards/views.py ===
"""Reward cycle endpoints: read, activate, claim, global."""
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN

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


def _cycle_duration() -> timedelta:
    """Length of a single reward cycle (default: 15 days)."""
    return timedelta(days=settings.REWARD_DURATION_DAYS)


def _compute_reward_amount(wallet) -> Decimal:
    """
    Reward = REWARD_PERCENT % of the wallet's current H Coin balance,
    floored at REWARD_MIN_HCOIN so users with empty wallets still get
    something on their first activation.
    """
    balance = wallet.h_coin_balance or Decimal(0)
    pct = Decimal(settings.REWARD_PERCENT) / Decimal(100)
    raw = (balance * pct).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    floor = Decimal(settings.REWARD_MIN_HCOIN)
    return max(raw, floor)


def _check_activation_eligibility(user, wallet):
    """
    Returns (eligible: bool, reasons: list[dict]) where each reason has a
    machine-readable `code` and a user-facing `message`. Both rules are
    checked so the UI can list every missing requirement at once.

    Rules:
      1. Wallet H Coin balance must be > 0.
      2. User must have at least one successfully invited referral.
    """
    reasons = []

    balance = (wallet.h_coin_balance if wallet else Decimal(0)) or Decimal(0)
    if balance <= 0:
        reasons.append({
            "code": "INSUFFICIENT_BALANCE",
            "message": "Insufficient wallet balance to activate reward cycle.",
        })

    # Qualified referral = L1 invited user with ≥1 completed deposit.
    # Signups alone no longer satisfy this rule (anti-fake-account).
    from referrals.models import Referral
    has_qualified_referral = Referral.objects.qualified_for(user).exists()

    # Keep the cached wallet.has_referral flag in sync so other code paths
    # that read it (admin views, dashboards) see the latest state.
    if wallet and bool(wallet.has_referral) != has_qualified_referral:
        wallet.has_referral = has_qualified_referral
        wallet.save(update_fields=["has_referral", "updated_at"])

    if not has_qualified_referral:
        reasons.append({
            "code": "NO_QUALIFIED_REFERRAL",
            "message": (
                "At least one invited user with a completed deposit is "
                "required to activate the reward cycle."
            ),
        })

    return (len(reasons) == 0, reasons)


def _target_global_end_time():
    """
    Resolve the configured "season" end time.

    If GLOBAL_CYCLE_END_DATE is set in env / settings (format YYYY-MM-DD),
    return it as a tz-aware datetime at 00:00 UTC. Otherwise return
    `now + GLOBAL_CYCLE_DAYS` for the rolling cycle behaviour.
    """
    raw = (getattr(settings, "GLOBAL_CYCLE_END_DATE", None) or "").strip()
    if raw:
        try:
            from datetime import datetime, timezone as dtz
            return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=dtz.utc)
        except Exception:
            pass
    return timezone.now() + timedelta(days=settings.GLOBAL_CYCLE_DAYS)


def _ensure_global_cycle():
    """
    Make sure the active global cycle exists and ends at the configured
    target date. If an existing cycle has a stale end_time, rewrite it
    in place so the Home countdown jumps to the new target immediately.
    """
    now = timezone.now()
    target = _target_global_end_time()

    gc = GlobalCycle.objects.filter(is_active=True).order_by("-start_time").first()

    if gc and gc.end_time > now:
        # Existing cycle still in the future — sync its end_time if needed.
        if gc.end_time != target:
            gc.end_time = target
            gc.save(update_fields=["end_time"])
        return gc

    # No active cycle (or it already expired) — start a fresh one.
    GlobalCycle.objects.filter(is_active=True).update(is_active=False)
    return GlobalCycle.objects.create(
        label="Season",
        start_time=now,
        end_time=target,
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
        # No active cycle — preview what the next one would look like AND
        # surface eligibility so the SPA can disable the button preemptively.
        duration = _cycle_duration()
        preview_amount = _compute_reward_amount(wallet) if wallet else Decimal(settings.REWARD_MIN_HCOIN)
        eligible, reasons = _check_activation_eligibility(request.user, wallet)
        return Response({
            "active": False,
            "status": None,
            "endTime": None,
            "durationMs": int(duration.total_seconds() * 1000),
            "durationDays": settings.REWARD_DURATION_DAYS,
            "rewardPercent": settings.REWARD_PERCENT,
            "rewardTokens": str(preview_amount),
            "canActivate": eligible,
            "ineligibilityReasons": reasons,
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

            # === Pre-activation guards ===
            # 1) wallet balance must be > 0
            # 2) user must have ≥ 1 successful invited referral
            eligible, reasons = _check_activation_eligibility(request.user, wallet)
            if not eligible:
                # Use the first reason for the top-level code/message so older
                # clients that don't read `reasons` still get something useful,
                # while new clients can show every missing requirement.
                primary = reasons[0]
                return Response(
                    {
                        "code": primary["code"],
                        "message": primary["message"],
                        "reasons": reasons,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            now = timezone.now()
            duration = _cycle_duration()
            amount = _compute_reward_amount(wallet)
            cycle = RewardCycle.objects.create(
                user=request.user,
                ends_at=now + duration,
                reward_amount_hcoin=amount,
                status=RewardCycle.STATUS_ACTIVE,
            )
            wallet.reward_active = True
            wallet.reward_end_time = cycle.ends_at
            wallet.save(update_fields=["reward_active", "reward_end_time", "updated_at"])
            log_audit(
                "reward_cycle_activate", user=request.user,
                cycle_id=str(cycle.id), amount=str(amount),
                duration_days=settings.REWARD_DURATION_DAYS,
                balance_at_activation=str(wallet.h_coin_balance),
            )
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
