# === FILE: backend/payments/tasks.py ===
"""Celery tasks for the crypto payment gateway.

These run on the celery beat schedule (see core/celery.py):
  * `scan_master_wallet` — pull recent transfers into the master hot
    wallet for each network, ingest them, pre-create pending deposit
    Transactions for matched users.
  * `poll_pending_deposits` — for every pending deposit, re-check
    confirmations and credit the wallet when the threshold is reached.
  * `poll_pending_withdrawals` — for processing withdrawals, check
    on-chain confirmation and flip to COMPLETED.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from transactions.models import Transaction

from .gateway import GatewayError, get_client
from .services import (
    advance_cursor,
    confirm_and_credit_deposit,
    confirm_pending_withdrawal,
    get_or_create_cursor,
    ingest_chain_event,
    record_cursor_error,
)

logger = logging.getLogger("tokenvault")


@shared_task(bind=True, acks_late=True, max_retries=3, default_retry_delay=60)
def scan_master_wallet(self, network: str | None = None):
    """Poll incoming USDT transfers to the master hot wallet for the
    given network. If `network` is None we sweep all configured
    networks.
    """
    networks = [network] if network else ["TRC20", "ERC20"]
    total = 0
    for net in networks:
        address = (
            settings.USDT_TRC20_WALLET
            if net == "TRC20"
            else settings.USDT_ERC20_WALLET
        )
        if not address:
            logger.debug("scan_master_wallet: %s — no master address configured", net)
            continue

        client = get_client(net)
        cursor = get_or_create_cursor(net)
        try:
            transfers = list(
                client.list_incoming_transfers(
                    address=address,
                    from_block=cursor.last_block,
                    limit=settings.GATEWAY_SCAN_BATCH_SIZE,
                )
            )
        except GatewayError as e:
            logger.warning("scan_master_wallet %s error: %s", net, e)
            record_cursor_error(net, str(e))
            if e.retryable:
                raise self.retry(exc=e, countdown=60)
            continue
        except Exception as e:
            logger.exception("scan_master_wallet %s crashed", net)
            record_cursor_error(net, str(e))
            continue

        max_block = cursor.last_block
        last_hash = cursor.last_tx_hash
        for ev in transfers:
            try:
                ingest_chain_event(ev)
                total += 1
                if ev.block_number and ev.block_number > max_block:
                    max_block = ev.block_number
                if ev.tx_hash:
                    last_hash = ev.tx_hash
            except Exception:
                logger.exception("ingest_chain_event failed for %s %s", net, ev.tx_hash)

        advance_cursor(net, last_block=max_block, last_tx_hash=last_hash)
    return total


@shared_task(bind=True, acks_late=True, max_retries=5, default_retry_delay=60)
def poll_pending_deposits(self, lookback_hours: int = 24):
    """For each pending deposit younger than `lookback_hours`, ask the
    chain how many confirmations it has and credit if ready."""
    cutoff = timezone.now() - timedelta(hours=lookback_hours)
    qs = Transaction.objects.filter(
        type=Transaction.TYPE_DEPOSIT,
        status__in=[Transaction.STATUS_PENDING, Transaction.STATUS_PROCESSING],
        created_at__gte=cutoff,
    ).only("id", "network", "tx_hash")

    credited = 0
    for tx in qs.iterator():
        try:
            result = confirm_and_credit_deposit(str(tx.id))
            if result.credited:
                credited += 1
        except GatewayError as e:
            logger.warning("poll_pending_deposits %s: %s", tx.id, e)
        except Exception:
            logger.exception("poll_pending_deposits crashed for tx %s", tx.id)
    return credited


@shared_task(bind=True, acks_late=True, max_retries=5, default_retry_delay=60)
def poll_pending_withdrawals(self):
    """For each broadcast withdrawal in PROCESSING, check confirmations."""
    qs = Transaction.objects.filter(
        type=Transaction.TYPE_WITHDRAW,
        status=Transaction.STATUS_PROCESSING,
    ).exclude(tx_hash__isnull=True).exclude(tx_hash="")

    confirmed = 0
    for tx in qs.only("id").iterator():
        try:
            res = confirm_pending_withdrawal(str(tx.id))
            if res.status == Transaction.STATUS_COMPLETED:
                confirmed += 1
        except GatewayError as e:
            logger.warning("poll_pending_withdrawals %s: %s", tx.id, e)
        except Exception:
            logger.exception("poll_pending_withdrawals crashed for tx %s", tx.id)
    return confirmed
