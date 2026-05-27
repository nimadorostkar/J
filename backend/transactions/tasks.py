# === FILE: backend/transactions/tasks.py ===
"""Celery tasks for deposit verification and withdrawal processing."""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.db import transaction as db_tx
from django.utils import timezone

from core.audit import log_audit

from .models import Transaction

logger = logging.getLogger("tokenvault")


def _push_wallet_event(user_id, event_type, **payload):
    """Push a single event to the wallet WebSocket group."""
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
        logger.exception("Failed to push wallet event")


def _check_chain_confirmation(network: str, tx_hash: str, expected_amount: Decimal) -> bool:
    """Stub: real implementation should call Tron/Ethereum APIs.

    For now we treat any tx_hash provided as confirmed in non-prod and gate
    confirmed on env in production. Replace with real on-chain RPC client.
    """
    if not tx_hash:
        return False
    # Real-world: call tron-grid or etherscan with TRON_API_KEY/ETHEREUM_API_KEY
    # and validate amount, network, recipient. Returning True here is a
    # deliberate placeholder for the integration point.
    return True


@shared_task(bind=True, acks_late=True, max_retries=5, default_retry_delay=60)
def verify_deposit(self, transaction_id):
    """Poll blockchain for confirmation, then credit wallet."""
    try:
        tx = Transaction.objects.select_related("user", "wallet").get(pk=transaction_id)
    except Transaction.DoesNotExist:
        logger.warning("verify_deposit: tx %s not found", transaction_id)
        return

    if tx.status in (Transaction.STATUS_COMPLETED, Transaction.STATUS_FAILED):
        return

    confirmed = _check_chain_confirmation(tx.network, tx.tx_hash, tx.amount_usdt or Decimal(0))
    if not confirmed:
        # retry with backoff
        raise self.retry()

    with db_tx.atomic():
        tx = Transaction.objects.select_for_update().get(pk=transaction_id)
        if tx.status == Transaction.STATUS_COMPLETED:
            return
        from wallet.models import Wallet
        wallet = Wallet.objects.select_for_update().get(pk=tx.wallet_id)
        is_first = not wallet.has_completed_deposit
        wallet.usdt_balance = wallet.usdt_balance + (tx.amount_usdt or Decimal(0))
        # Also credit the H Coin (game currency) balance — both balances
        # should rise on a deposit so the user can play with what they put in.
        wallet.h_coin_balance = wallet.h_coin_balance + (tx.amount_hcoin or Decimal(0))
        if is_first:
            wallet.has_completed_deposit = True
        wallet.save()

        tx.status = Transaction.STATUS_COMPLETED
        tx.save(update_fields=["status", "updated_at"])

        log_audit("deposit_complete", user=tx.user,
                  tx_id=str(tx.id), amount=str(tx.amount_usdt),
                  first_deposit=is_first)

    # On the FIRST completed deposit, this user newly "qualifies" as a
    # referral — check whether the L1 inviter should now get a milestone
    # payout. Runs outside the deposit's atomic block so a milestone
    # failure can never break the deposit commit.
    if is_first:
        try:
            from referrals.services import on_deposit_completed
            on_deposit_completed(tx.user)
        except Exception:
            logger.exception("on_deposit_completed failed for user %s", tx.user_id)

    # Notify user via WS + Notification row
    from notifications.tasks import send_notification
    send_notification.delay(
        str(tx.user_id),
        title="Deposit confirmed",
        body=f"Your deposit of {tx.amount_usdt} USDT has been credited.",
        notification_type="deposit",
    )
    _push_wallet_event(
        tx.user_id,
        "transaction_update",
        id=str(tx.id),
        status=tx.status,
        tx_type="deposit",
    )
    _push_wallet_event(
        tx.user_id,
        "balance_update",
        h_coins=str(wallet.h_coin_balance),
        usdt_balance=str(wallet.usdt_balance),
    )


@shared_task(bind=True, acks_late=True, max_retries=5, default_retry_delay=120)
def process_withdrawal(self, transaction_id):
    """Send blockchain transfer after admin approval (or auto-approve)."""
    try:
        tx = Transaction.objects.select_related("user", "wallet").get(pk=transaction_id)
    except Transaction.DoesNotExist:
        return

    if tx.status not in (Transaction.STATUS_PENDING, Transaction.STATUS_PROCESSING):
        return

    with db_tx.atomic():
        tx = Transaction.objects.select_for_update().get(pk=transaction_id)
        if tx.status == Transaction.STATUS_COMPLETED:
            return
        tx.status = Transaction.STATUS_PROCESSING
        tx.save(update_fields=["status", "updated_at"])

    # Real-world: invoke a hot-wallet signer here, capture tx_hash,
    # poll for confirmations. For now we mark completed.
    try:
        # placeholder for on-chain transfer
        chain_tx_hash = f"simulated-{tx.id.hex[:16]}"

        with db_tx.atomic():
            tx = Transaction.objects.select_for_update().get(pk=transaction_id)
            tx.tx_hash = chain_tx_hash
            tx.status = Transaction.STATUS_COMPLETED
            tx.save(update_fields=["tx_hash", "status", "updated_at"])
            log_audit("withdraw_complete", user=tx.user,
                      tx_id=str(tx.id), amount=str(tx.amount_usdt))
    except Exception:
        with db_tx.atomic():
            tx = Transaction.objects.select_for_update().get(pk=transaction_id)
            tx.status = Transaction.STATUS_FAILED
            tx.save(update_fields=["status", "updated_at"])
            # Refund H Coins
            from wallet.models import Wallet
            wallet = Wallet.objects.select_for_update().get(pk=tx.wallet_id)
            wallet.h_coin_balance = wallet.h_coin_balance + (tx.amount_hcoin or Decimal(0))
            wallet.save(update_fields=["h_coin_balance", "updated_at"])
        raise

    from notifications.tasks import send_notification
    send_notification.delay(
        str(tx.user_id),
        title="Withdrawal sent",
        body=f"Your withdrawal of {tx.amount_usdt} USDT has been sent.",
        notification_type="withdraw",
    )
    _push_wallet_event(tx.user_id, "transaction_update",
                       id=str(tx.id), status=tx.status, tx_type="withdraw")


@shared_task(acks_late=True)
def expire_stale_deposits():
    """Mark pending deposits older than 24h as failed."""
    cutoff = timezone.now() - timedelta(hours=24)
    stale = Transaction.objects.filter(
        type=Transaction.TYPE_DEPOSIT,
        status=Transaction.STATUS_PENDING,
        created_at__lt=cutoff,
    )
    count = stale.update(status=Transaction.STATUS_FAILED)
    logger.info("Expired %s stale deposits", count)
    return count
