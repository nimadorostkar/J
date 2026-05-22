# === FILE: backend/referrals/services.py ===
"""Referral commission engine.

`distribute_commission(user, profit_hcoin)` MUST be called *inside* the
same atomic block as the original profit credit. It is intentionally
synchronous so inviters are paid (or not paid) atomically with the
event that triggered the payout.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_tx

from core.audit import log_audit

logger = logging.getLogger("tokenvault")


def _push_event(user_id, event_type, **payload):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            f"wallet_{user_id}",
            {"type": event_type, **payload},
        )
    except Exception:
        logger.exception("Failed to push commission event")


def distribute_commission(user, profit_hcoin: Decimal):
    """Credit L1 (and L2, if applicable) inviters their share of `profit_hcoin`.

    Must be called from inside an atomic block. Internally we use a
    nested savepoint via `transaction.atomic()` and `select_for_update()`
    on referral rows + wallets to guard against concurrent writes.
    """
    if profit_hcoin is None or profit_hcoin <= 0:
        return

    from referrals.models import Referral
    from transactions.models import Transaction
    from wallet.models import Wallet

    l1_pct = Decimal(settings.REFERRAL_L1_COMMISSION_PCT)
    l2_pct = Decimal(settings.REFERRAL_L2_COMMISSION_PCT)

    with db_tx.atomic():
        # ── Level 1 ──────────────────────────────────────────────
        ref_l1 = (
            Referral.objects.select_for_update()
            .filter(invited_user=user, level=1)
            .select_related("inviter")
            .first()
        )
        if ref_l1:
            l1_amount = (profit_hcoin * l1_pct / Decimal(100)).quantize(Decimal("0.00000001"))
            if l1_amount > 0:
                inviter = ref_l1.inviter
                inviter_wallet = (
                    Wallet.objects.select_for_update().get(user=inviter)
                )
                inviter_wallet.h_coin_balance = inviter_wallet.h_coin_balance + l1_amount
                inviter_wallet.save(update_fields=["h_coin_balance", "updated_at"])

                Transaction.objects.create(
                    user=inviter,
                    wallet=inviter_wallet,
                    type="commission",
                    network=None,
                    amount_hcoin=l1_amount,
                    status="completed",
                    commission_from_user=user,
                    commission_level=1,
                    commission_rate=l1_pct,
                )
                ref_l1.total_commission_earned_hcoin = (
                    ref_l1.total_commission_earned_hcoin + l1_amount
                )
                ref_l1.save(update_fields=["total_commission_earned_hcoin"])
                log_audit("commission_pay", user=inviter,
                          level=1, amount=str(l1_amount),
                          from_user=str(user.id))

                # Notify (deferred to Celery for the email/notification row)
                from notifications.tasks import send_notification
                send_notification.delay(
                    str(inviter.id),
                    title="Referral commission earned",
                    body=(f"You earned {l1_amount} H Coins commission from "
                          f"{user.first_name or user.email}'s reward."),
                    notification_type="commission",
                )
                _push_event(
                    inviter.id,
                    "commission_received",
                    amount=str(l1_amount),
                    level=1,
                    from_user={"id": str(user.id),
                               "firstName": user.first_name},
                )
                _push_event(
                    inviter.id,
                    "balance_update",
                    h_coins=str(inviter_wallet.h_coin_balance),
                    usdt_balance=str(inviter_wallet.usdt_balance),
                )

        # ── Level 2 ──────────────────────────────────────────────
        ref_l2 = (
            Referral.objects.select_for_update()
            .filter(invited_user=user, level=2)
            .select_related("inviter")
            .first()
        )
        if ref_l2:
            l2_amount = (profit_hcoin * l2_pct / Decimal(100)).quantize(Decimal("0.00000001"))
            if l2_amount > 0:
                inviter = ref_l2.inviter
                inviter_wallet = (
                    Wallet.objects.select_for_update().get(user=inviter)
                )
                inviter_wallet.h_coin_balance = inviter_wallet.h_coin_balance + l2_amount
                inviter_wallet.save(update_fields=["h_coin_balance", "updated_at"])

                Transaction.objects.create(
                    user=inviter,
                    wallet=inviter_wallet,
                    type="commission",
                    network=None,
                    amount_hcoin=l2_amount,
                    status="completed",
                    commission_from_user=user,
                    commission_level=2,
                    commission_rate=l2_pct,
                )
                ref_l2.total_commission_earned_hcoin = (
                    ref_l2.total_commission_earned_hcoin + l2_amount
                )
                ref_l2.save(update_fields=["total_commission_earned_hcoin"])
                log_audit("commission_pay", user=inviter,
                          level=2, amount=str(l2_amount),
                          from_user=str(user.id))

                from notifications.tasks import send_notification
                send_notification.delay(
                    str(inviter.id),
                    title="Level-2 commission earned",
                    body=(f"You earned {l2_amount} H Coins commission from "
                          f"{user.first_name or user.email}'s reward."),
                    notification_type="commission",
                )
                _push_event(
                    inviter.id,
                    "commission_received",
                    amount=str(l2_amount),
                    level=2,
                    from_user={"id": str(user.id),
                               "firstName": user.first_name},
                )
                _push_event(
                    inviter.id,
                    "balance_update",
                    h_coins=str(inviter_wallet.h_coin_balance),
                    usdt_balance=str(inviter_wallet.usdt_balance),
                )
