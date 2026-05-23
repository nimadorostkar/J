# === FILE: backend/trade/services.py ===
"""Bot activation / completion logic.

`activate_bot(user, bot_type)`:
  • SELECT FOR UPDATE on the user's wallet to serialize.
  • Reject if another bot is already active.
  • Reject if the percentage-based fee evaluates to ≤ 0.
  • Deduct the fee from the wallet, write a Transaction (TYPE_BOT_FEE),
    create the BotSession row, schedule the Celery completion task.

`complete_bot_session(session_id)`:
  • Idempotent: short-circuits if status != ACTIVE.
  • Generates a random profit in the configured range, credits the
    wallet, writes a Transaction (TYPE_BOT_PROFIT), flips status to
    COMPLETED.
"""
import logging
import random
from decimal import Decimal, ROUND_DOWN
from datetime import timedelta

from django.conf import settings
from django.db import transaction as db_tx
from django.utils import timezone

from core.audit import log_audit

logger = logging.getLogger("tokenvault")

# Decimal precision for all on-the-fly math.
EIGHT_PLACES = Decimal("0.00000001")


class BotActivationError(Exception):
    """Raised when activation can't proceed. .code + .message map to API."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def bot_config(bot_type: str) -> dict:
    """Return the configured fee/duration/profit-range for a bot type."""
    from .models import BotSession

    if bot_type == BotSession.BOT_BASIC:
        return {
            "feePercent": Decimal(str(settings.BOT_BASIC_FEE_PCT)),
            "durationSeconds": int(settings.BOT_BASIC_DURATION_SECONDS),
            "profitMinPercent": Decimal(str(settings.BOT_BASIC_PROFIT_MIN_PCT)),
            "profitMaxPercent": Decimal(str(settings.BOT_BASIC_PROFIT_MAX_PCT)),
        }
    if bot_type == BotSession.BOT_EXPERT:
        return {
            "feePercent": Decimal(str(settings.BOT_EXPERT_FEE_PCT)),
            "durationSeconds": int(settings.BOT_EXPERT_DURATION_SECONDS),
            "profitMinPercent": Decimal(str(settings.BOT_EXPERT_PROFIT_MIN_PCT)),
            "profitMaxPercent": Decimal(str(settings.BOT_EXPERT_PROFIT_MAX_PCT)),
        }
    raise BotActivationError("INVALID_BOT_TYPE", f"Unknown bot type '{bot_type}'.")


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
        logger.exception("Failed to push bot event")


def activate_bot(user, bot_type: str):
    """Activate a bot for `user`. Returns the new BotSession."""
    from .models import BotSession
    from transactions.models import Transaction
    from wallet.models import Wallet

    cfg = bot_config(bot_type)

    with db_tx.atomic():
        wallet = Wallet.objects.select_for_update().get(user=user)

        # 1. Only one active bot at a time (enforced by DB constraint too).
        if BotSession.objects.filter(
            user=user, status=BotSession.STATUS_ACTIVE,
        ).exists():
            raise BotActivationError(
                "BOT_ALREADY_ACTIVE",
                "Another bot is already running. Wait for it to finish first.",
            )

        balance = wallet.h_coin_balance or Decimal(0)
        fee = (balance * cfg["feePercent"] / Decimal(100)).quantize(
            EIGHT_PLACES, rounding=ROUND_DOWN,
        )

        # 2. The fee must be positive AND ≤ balance.
        if fee <= 0:
            raise BotActivationError(
                "INSUFFICIENT_BALANCE",
                "Your balance is too low to activate this bot.",
            )
        if fee > balance:
            raise BotActivationError(
                "INSUFFICIENT_BALANCE",
                "Insufficient balance to cover the bot fee.",
            )

        # 3. Debit the wallet.
        wallet.h_coin_balance = balance - fee
        wallet.save(update_fields=["h_coin_balance", "updated_at"])

        # 4. Audit row in the user's transaction feed.
        fee_tx = Transaction.objects.create(
            user=user,
            wallet=wallet,
            type=Transaction.TYPE_BOT_FEE,
            network=None,
            amount_hcoin=fee,
            status=Transaction.STATUS_COMPLETED,
        )

        # 5. Create the session.
        now = timezone.now()
        session = BotSession.objects.create(
            user=user,
            bot_type=bot_type,
            status=BotSession.STATUS_ACTIVE,
            balance_at_start_hcoin=balance,
            fee_percent=cfg["feePercent"],
            fee_amount_hcoin=fee,
            duration_seconds=cfg["durationSeconds"],
            profit_min_percent=cfg["profitMinPercent"],
            profit_max_percent=cfg["profitMaxPercent"],
            completes_at=now + timedelta(seconds=cfg["durationSeconds"]),
            fee_transaction=fee_tx,
        )

        log_audit(
            "bot_activate", user=user,
            session_id=str(session.id), bot_type=bot_type,
            fee=str(fee), balance_before=str(balance),
            duration_seconds=cfg["durationSeconds"],
        )

    # 6. Schedule completion. Use Celery countdown for primary delivery;
    # the periodic `reconcile_overdue_bot_sessions` task is a safety net
    # in case Celery/Redis drops the scheduled task.
    try:
        from .tasks import complete_bot_session
        complete_bot_session.apply_async(
            args=[str(session.id)],
            countdown=cfg["durationSeconds"],
        )
    except Exception:
        logger.exception("Failed to schedule completion for bot %s", session.id)

    _push_event(
        user.id, "bot_activated",
        session_id=str(session.id), bot_type=bot_type,
        fee=str(fee), completes_at=session.completes_at.isoformat(),
    )
    _push_event(
        user.id, "balance_update",
        h_coins=str(wallet.h_coin_balance),
        usdt_balance=str(wallet.usdt_balance),
    )

    return session


def complete_bot_session_now(session_id):
    """
    Complete a session by id. Idempotent: a second call after the first
    is a no-op. Called from the Celery task and the reconcile sweep.
    """
    from .models import BotSession
    from transactions.models import Transaction
    from wallet.models import Wallet

    try:
        session = BotSession.objects.select_for_update(skip_locked=True).get(
            pk=session_id,
        )
    except BotSession.DoesNotExist:
        logger.warning("complete_bot_session: %s not found", session_id)
        return None

    # If another worker is already completing it, skip_locked returned None
    # — handled by Django by raising — but if we got the row, check status.
    if session.status != BotSession.STATUS_ACTIVE:
        return session

    cfg_min = session.profit_min_percent
    cfg_max = session.profit_max_percent

    # Random profit percentage in [min, max], in 0.01% increments so the
    # number looks "real" (not a clean integer every time).
    lo = int(cfg_min * 100)
    hi = int(cfg_max * 100)
    pct_x100 = random.randint(lo, hi) if hi > lo else lo
    profit_pct = Decimal(pct_x100) / Decimal(100)

    profit_amount = (
        session.balance_at_start_hcoin * profit_pct / Decimal(100)
    ).quantize(EIGHT_PLACES, rounding=ROUND_DOWN)

    with db_tx.atomic():
        # Refresh under lock to avoid races with concurrent completions.
        wallet = Wallet.objects.select_for_update().get(user_id=session.user_id)
        wallet.h_coin_balance = wallet.h_coin_balance + profit_amount
        wallet.save(update_fields=["h_coin_balance", "updated_at"])

        profit_tx = Transaction.objects.create(
            user_id=session.user_id,
            wallet=wallet,
            type=Transaction.TYPE_BOT_PROFIT,
            network=None,
            amount_hcoin=profit_amount,
            status=Transaction.STATUS_COMPLETED,
        )

        session.status = BotSession.STATUS_COMPLETED
        session.profit_percent = profit_pct
        session.profit_amount_hcoin = profit_amount
        session.completed_at = timezone.now()
        session.profit_transaction = profit_tx
        session.save(update_fields=[
            "status", "profit_percent", "profit_amount_hcoin",
            "completed_at", "profit_transaction",
        ])

        log_audit(
            "bot_complete", user_id=str(session.user_id),
            session_id=str(session.id), bot_type=session.bot_type,
            profit=str(profit_amount), profit_pct=str(profit_pct),
        )

    # Notify the user.
    try:
        from notifications.tasks import send_notification
        send_notification.delay(
            str(session.user_id),
            title=f"{session.get_bot_type_display()} completed",
            body=(f"You earned {profit_amount} H Coins "
                  f"({profit_pct}% profit) from your trading bot."),
            notification_type="bot_complete",
        )
    except Exception:
        logger.exception("Failed to send bot completion notification")

    _push_event(
        session.user_id, "bot_completed",
        session_id=str(session.id),
        profit=str(profit_amount),
        profit_percent=str(profit_pct),
    )
    _push_event(
        session.user_id, "balance_update",
        h_coins=str(wallet.h_coin_balance),
        usdt_balance=str(wallet.usdt_balance),
    )

    return session
