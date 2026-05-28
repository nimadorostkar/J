# === FILE: backend/transactions/tasks.py ===
"""Celery tasks for deposit verification and withdrawal processing.

The heavy lifting (real RPC calls, atomic credit/debit, idempotency)
lives in `payments.services`. These task wrappers keep the existing
public Celery signatures (`verify_deposit`, `process_withdrawal`,
`expire_stale_deposits`) so anywhere in the codebase that already
imports them keeps working.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction as db_tx
from django.utils import timezone

from .models import Transaction

logger = logging.getLogger("tokenvault")


def _push_wallet_event(user_id, event_type, **payload):
    """Push a single event to the wallet WebSocket group.

    Imported by views, services, and tasks across the codebase. Keep
    its signature stable.
    """
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


@shared_task(bind=True, acks_late=True, max_retries=10, default_retry_delay=60)
def verify_deposit(self, transaction_id):
    """Check on-chain confirmations and credit the wallet when ready.

    Delegates to `payments.services.confirm_and_credit_deposit`. The
    task retries with exponential backoff until confirmations reach
    the threshold or 24h passes (then `expire_stale_deposits` will
    mark it failed).
    """
    from payments.services import confirm_and_credit_deposit
    from payments.gateway import GatewayError

    try:
        tx = Transaction.objects.select_related("user", "wallet").get(pk=transaction_id)
    except Transaction.DoesNotExist:
        logger.warning("verify_deposit: tx %s not found", transaction_id)
        return

    if tx.status in (Transaction.STATUS_COMPLETED, Transaction.STATUS_FAILED):
        return

    try:
        result = confirm_and_credit_deposit(str(tx.id))
    except GatewayError as e:
        # Soft retry — RPC was unreachable.
        if e.retryable:
            raise self.retry(exc=e, countdown=min(600, 60 * (2 ** self.request.retries)))
        logger.error("verify_deposit hard failure: %s", e)
        return
    except Exception:
        logger.exception("verify_deposit crashed for %s", transaction_id)
        raise self.retry(countdown=120)

    if result.credited:
        return

    # Not enough confirmations yet — retry with backoff (capped).
    countdown = min(600, 60 * (2 ** self.request.retries))
    raise self.retry(countdown=countdown)


@shared_task(bind=True, acks_late=True, max_retries=5, default_retry_delay=120)
def process_withdrawal(self, transaction_id):
    """Sign + broadcast a withdrawal, then schedule confirmation poll."""
    from payments.gateway import GatewayError
    from payments.services import broadcast_withdrawal

    try:
        tx = Transaction.objects.select_related("user", "wallet").get(pk=transaction_id)
    except Transaction.DoesNotExist:
        return

    if tx.status not in (Transaction.STATUS_PENDING, Transaction.STATUS_PROCESSING):
        return

    try:
        result = broadcast_withdrawal(str(tx.id))
    except GatewayError as e:
        if e.retryable:
            raise self.retry(exc=e, countdown=min(900, 120 * (2 ** self.request.retries)))
        return
    except Exception as e:
        logger.exception("process_withdrawal crashed for %s", transaction_id)
        raise self.retry(exc=e)

    if result.status == Transaction.STATUS_PROCESSING and result.tx_hash:
        # Notify the user we've sent it — final confirmation comes from
        # the poll_pending_withdrawals beat task.
        try:
            from notifications.tasks import send_notification
            send_notification.delay(
                str(tx.user_id),
                title="Withdrawal sent",
                body=f"Your withdrawal of {tx.amount_usdt} USDT has been broadcast.",
                notification_type="withdraw",
            )
            _push_wallet_event(
                tx.user_id, "transaction_update",
                id=str(tx.id), status=result.status, tx_type="withdraw",
            )
        except Exception:
            logger.exception("post-broadcast notify failed")


@shared_task(acks_late=True)
def expire_stale_deposits():
    """Mark pending deposits older than 24h as failed.

    Counterpart to verify_deposit's retry loop — if the chain never
    confirms within the window, the tx is dead.
    """
    cutoff = timezone.now() - timedelta(hours=24)
    stale = Transaction.objects.filter(
        type=Transaction.TYPE_DEPOSIT,
        status=Transaction.STATUS_PENDING,
        created_at__lt=cutoff,
    )
    count = stale.update(status=Transaction.STATUS_FAILED, failure_reason="Deposit window expired (>24h)")
    logger.info("Expired %s stale deposits", count)
    return count
