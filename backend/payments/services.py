# === FILE: backend/payments/services.py ===
"""High-level operations that bridge the on-chain gateway and the DB.

Every function here is safe to call from a Celery task or a webhook:
  * `confirm_and_credit_deposit(tx_id)` — re-checks on-chain
    confirmations and atomically credits the user's wallet exactly
    once.
  * `broadcast_withdrawal(tx_id)` — signs + broadcasts a USDT transfer
    from the master hot wallet, refunds the wallet on hard-failure.
  * `ingest_chain_event(event)` — idempotently records a scanner-seen
    transfer in GatewayEventLog and (if pre-matched) creates a deposit
    Transaction in `pending`.
  * `record_daily_withdrawal_total(user)` / `assert_within_limits(...)`
    enforce per-user daily caps + per-tx min/max.

Why one module
──────────────
Concentrating these here keeps `wallet/views.py` thin (just request
validation) and lets us swap chains, change confirmation depth, or
toggle dry-run by editing this file alone.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction as db_tx
from django.utils import timezone

from core.audit import log_audit
from transactions.models import Transaction
from wallet.models import DepositAddress, Wallet

from .gateway import ChainTransfer, GatewayError, get_client
from .models import GatewayCursor, GatewayEventLog

logger = logging.getLogger("tokenvault")
User = get_user_model()


# ─── Limits ─────────────────────────────────────────────────────────
class WithdrawalLimitError(Exception):
    """Raised when a withdrawal violates per-tx or daily caps."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def assert_within_withdrawal_limits(user, *, amount_usdt: Decimal) -> None:
    """Enforce min/max per-tx + daily cap. Raises WithdrawalLimitError."""
    min_w = Decimal(settings.MIN_WITHDRAWAL_USDT)
    max_w = Decimal(settings.MAX_WITHDRAWAL_USDT)
    daily_cap = Decimal(settings.DAILY_WITHDRAWAL_LIMIT_USDT)

    if amount_usdt < min_w:
        raise WithdrawalLimitError(
            "BELOW_MIN_WITHDRAWAL",
            f"Minimum withdrawal is {min_w} USDT.",
        )
    if amount_usdt > max_w:
        raise WithdrawalLimitError(
            "ABOVE_MAX_WITHDRAWAL",
            f"Maximum single withdrawal is {max_w} USDT.",
        )

    from django.db.models import Sum

    since = timezone.now() - timedelta(hours=24)
    total_today = Transaction.objects.filter(
        user=user,
        type=Transaction.TYPE_WITHDRAW,
        status__in=[
            Transaction.STATUS_PENDING,
            Transaction.STATUS_PROCESSING,
            Transaction.STATUS_COMPLETED,
        ],
        created_at__gte=since,
    ).aggregate(total=Sum("amount_usdt"))["total"] or Decimal("0")

    if (Decimal(total_today) + amount_usdt) > daily_cap:
        raise WithdrawalLimitError(
            "DAILY_LIMIT_EXCEEDED",
            f"Daily withdrawal limit is {daily_cap} USDT.",
        )


def requires_admin_review(amount_usdt: Decimal) -> bool:
    """Returns True iff the amount is at/above the manual-review threshold."""
    return Decimal(amount_usdt) >= Decimal(settings.WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT)


# ─── Deposit pipeline ───────────────────────────────────────────────
@dataclass
class DepositResult:
    transaction_id: str
    status: str
    confirmations: int
    required: int
    credited: bool


def confirm_and_credit_deposit(transaction_id: str) -> DepositResult:
    """Look up on-chain confirmations and credit the wallet if the
    threshold is reached.

    Safe to call repeatedly: it's a no-op once the Transaction is in
    a terminal state. All DB writes are atomic under SELECT FOR UPDATE.
    """
    tx = Transaction.objects.select_related("user", "wallet").get(pk=transaction_id)
    if tx.type != Transaction.TYPE_DEPOSIT:
        raise ValueError("confirm_and_credit_deposit: not a deposit")
    if tx.status in (Transaction.STATUS_COMPLETED, Transaction.STATUS_FAILED):
        return DepositResult(str(tx.id), tx.status, 0, 0, credited=False)

    client = get_client(tx.network or "TRC20")
    transfer = client.get_transfer(tx.tx_hash) if tx.tx_hash else None

    required = (
        settings.MIN_CONFIRMATIONS_TRC20
        if tx.network == "TRC20"
        else settings.MIN_CONFIRMATIONS_ERC20
    )

    if not transfer:
        # No on-chain record yet — keep pending.
        return DepositResult(str(tx.id), tx.status, 0, required, credited=False)

    # Defence in depth: in real mode, ensure recipient + amount match.
    if not settings.GATEWAY_DRY_RUN:
        expected_master = (
            settings.USDT_TRC20_WALLET
            if tx.network == "TRC20"
            else settings.USDT_ERC20_WALLET
        )
        if transfer.to_address.lower() != (expected_master or "").lower():
            _fail_deposit(tx, reason="Recipient address mismatch")
            return DepositResult(str(tx.id), Transaction.STATUS_FAILED, 0, required, credited=False)
        if tx.amount_usdt and abs(Decimal(transfer.amount_usdt) - Decimal(tx.amount_usdt)) > Decimal("0.01"):
            _fail_deposit(tx, reason=f"Amount mismatch: chain={transfer.amount_usdt} db={tx.amount_usdt}")
            return DepositResult(str(tx.id), Transaction.STATUS_FAILED, 0, required, credited=False)

    if transfer.confirmations < required:
        return DepositResult(
            str(tx.id), tx.status, int(transfer.confirmations), required, credited=False
        )

    return _credit_deposit_atomic(tx, transfer, required)


def _credit_deposit_atomic(tx: Transaction, transfer: ChainTransfer, required: int) -> DepositResult:
    """Atomic critical section: lock the wallet, lock the tx, credit
    once, mark completed."""
    from notifications.tasks import send_notification
    from transactions.tasks import _push_wallet_event

    with db_tx.atomic():
        tx_locked = Transaction.objects.select_for_update().get(pk=tx.pk)
        if tx_locked.status == Transaction.STATUS_COMPLETED:
            return DepositResult(str(tx.id), tx_locked.status, transfer.confirmations, required, credited=False)

        wallet = Wallet.objects.select_for_update().get(pk=tx_locked.wallet_id)
        is_first = not wallet.has_completed_deposit
        wallet.usdt_balance = wallet.usdt_balance + (tx_locked.amount_usdt or Decimal(0))
        wallet.h_coin_balance = wallet.h_coin_balance + (tx_locked.amount_hcoin or Decimal(0))
        update_fields = ["usdt_balance", "h_coin_balance", "updated_at"]
        if is_first:
            wallet.has_completed_deposit = True
            update_fields.append("has_completed_deposit")
        wallet.save(update_fields=update_fields)

        tx_locked.status = Transaction.STATUS_COMPLETED
        tx_locked.block_number = transfer.block_number or tx_locked.block_number
        tx_locked.confirmations = int(transfer.confirmations)
        tx_locked.from_address = transfer.from_address or tx_locked.from_address
        tx_locked.save(
            update_fields=[
                "status",
                "block_number",
                "confirmations",
                "from_address",
                "updated_at",
            ]
        )
        log_audit(
            "deposit_complete",
            user=tx_locked.user,
            tx_id=str(tx_locked.id),
            amount=str(tx_locked.amount_usdt),
            first_deposit=is_first,
            confirmations=int(transfer.confirmations),
            block_number=int(transfer.block_number),
        )

        db_tx.on_commit(
            lambda: _post_credit_side_effects(
                user_id=tx_locked.user_id,
                wallet_id=tx_locked.wallet_id,
                tx_id=str(tx_locked.id),
                is_first=is_first,
            )
        )

    return DepositResult(
        str(tx.id),
        Transaction.STATUS_COMPLETED,
        int(transfer.confirmations),
        required,
        credited=True,
    )


def _post_credit_side_effects(*, user_id, wallet_id, tx_id, is_first):
    """Fan-out notifications and WS pushes AFTER the credit commits."""
    from transactions.tasks import _push_wallet_event
    try:
        tx = Transaction.objects.select_related("wallet").get(pk=tx_id)
    except Transaction.DoesNotExist:
        return

    if is_first:
        try:
            from referrals.services import on_deposit_completed
            on_deposit_completed(tx.user)
        except Exception:
            logger.exception("on_deposit_completed failed after deposit credit")

    try:
        from notifications.tasks import send_notification
        send_notification.delay(
            str(user_id),
            title="Deposit confirmed",
            body=f"Your deposit of {tx.amount_usdt} USDT has been credited.",
            notification_type="deposit",
        )
    except Exception:
        logger.exception("notification dispatch failed")

    try:
        _push_wallet_event(
            user_id, "transaction_update",
            id=str(tx.id), status=tx.status, tx_type="deposit",
        )
        _push_wallet_event(
            user_id, "balance_update",
            h_coins=str(tx.wallet.h_coin_balance),
            usdt_balance=str(tx.wallet.usdt_balance),
        )
    except Exception:
        logger.exception("WS push failed")


def _fail_deposit(tx: Transaction, *, reason: str) -> None:
    """Hard-fail a deposit transaction with an audit trail."""
    with db_tx.atomic():
        t = Transaction.objects.select_for_update().get(pk=tx.pk)
        if t.status in (Transaction.STATUS_COMPLETED, Transaction.STATUS_FAILED):
            return
        t.status = Transaction.STATUS_FAILED
        t.failure_reason = reason[:500]
        t.save(update_fields=["status", "failure_reason", "updated_at"])
        log_audit("deposit_failed", user=t.user, tx_id=str(t.id), reason=reason)


# ─── Scanner: ingest detected on-chain transfers ────────────────────
def ingest_chain_event(event: ChainTransfer) -> GatewayEventLog | None:
    """Idempotently record a single inbound transfer.

    If we can match the sender (via a DepositAddress row) to a user we
    auto-create a `pending` deposit Transaction; otherwise we keep the
    event in GatewayEventLog so ops can match it manually.
    """
    # Idempotency — unique(network, tx_hash, log_index).
    obj, created = GatewayEventLog.objects.get_or_create(
        network=event.network,
        tx_hash=event.tx_hash,
        log_index=event.log_index,
        defaults={
            "block_number": event.block_number,
            "from_address": event.from_address,
            "to_address": event.to_address,
            "amount_usdt": event.amount_usdt,
            "confirmations_at_ingest": event.confirmations,
        },
    )
    if not created:
        # Already ingested. Update confirmations snapshot for visibility.
        if event.confirmations > (obj.confirmations_at_ingest or 0):
            obj.confirmations_at_ingest = event.confirmations
            obj.save(update_fields=["confirmations_at_ingest"])
        return obj

    # Try to match sender to a user via their registered deposit
    # address. With one master hot wallet we identify the depositor by
    # the address they sent from (the user must have linked it in our
    # DepositAddress table).
    user = _match_user_by_from_address(event)
    if user is None:
        logger.info(
            "payments: unmatched %s deposit %s from %s amount %s",
            event.network, event.tx_hash[:10], event.from_address, event.amount_usdt,
        )
        return obj

    # Pre-create a pending Transaction. confirm_and_credit_deposit()
    # will move it to completed when confirmations reach the threshold.
    wallet, _ = Wallet.objects.get_or_create(user=user)
    amount_usdt = Decimal(event.amount_usdt).quantize(Decimal("0.00000001"))
    if amount_usdt < Decimal(settings.MIN_DEPOSIT_USDT):
        # Below minimum — record but don't credit.
        obj.matched_user_id = str(user.pk)
        obj.save(update_fields=["matched_user_id"])
        return obj

    amount_hcoin = amount_usdt / Decimal(settings.USDT_PER_HCOIN)
    new_tx = Transaction.objects.create(
        user=user,
        wallet=wallet,
        type=Transaction.TYPE_DEPOSIT,
        network=event.network,
        amount_usdt=amount_usdt,
        amount_hcoin=amount_hcoin,
        tx_hash=event.tx_hash,
        status=Transaction.STATUS_PENDING,
        from_address=event.from_address,
        block_number=event.block_number,
        confirmations=event.confirmations,
        idempotency_key=uuid.uuid5(uuid.NAMESPACE_URL, f"scanner:{event.network}:{event.tx_hash}:{event.log_index}"),
    )
    obj.matched_user_id = str(user.pk)
    obj.matched_transaction_id = new_tx.id
    obj.save(update_fields=["matched_user_id", "matched_transaction_id"])
    log_audit(
        "deposit_init",
        user=user,
        tx_id=str(new_tx.id),
        amount=str(amount_usdt),
        network=event.network,
        source="scanner",
    )
    return obj


def _match_user_by_from_address(event: ChainTransfer):
    """Best-effort user lookup by the sender address.

    Operators link a user to a `from` address by inserting a row in
    `wallet.DepositAddress` with `address=<the user's external wallet
    address>` and `network=<TRC20|ERC20>`.

    For exchanges where each user gets a unique RECEIVING sub-address
    you'd swap this lookup to match `event.to_address` instead.
    """
    if not event.from_address:
        return None
    da = (
        DepositAddress.objects.select_related("user")
        .filter(network=event.network, address__iexact=event.from_address, is_active=True, user__isnull=False)
        .first()
    )
    return da.user if da else None


# ─── Withdrawal pipeline ────────────────────────────────────────────
@dataclass
class WithdrawalResult:
    transaction_id: str
    status: str
    tx_hash: str | None
    error: str | None


def broadcast_withdrawal(transaction_id: str) -> WithdrawalResult:
    """Sign + broadcast a USDT transfer for a pending withdrawal.

    On success: stores tx_hash, marks STATUS_PROCESSING, returns.
    Confirmation polling (see tasks.poll_pending_withdrawals) will flip
    it to COMPLETED once the chain confirms.

    On hard failure: refunds the user's H Coin balance (the amount we
    debited at WithdrawInitView), records the failure_reason, and
    raises GatewayError so Celery retry can decide.
    """
    tx = Transaction.objects.select_related("user", "wallet").get(pk=transaction_id)
    if tx.type != Transaction.TYPE_WITHDRAW:
        raise ValueError("broadcast_withdrawal: not a withdrawal")
    if tx.status not in (Transaction.STATUS_PENDING, Transaction.STATUS_PROCESSING):
        return WithdrawalResult(str(tx.id), tx.status, tx.tx_hash, None)
    if tx.requires_admin_review and not tx.admin_approved_at:
        return WithdrawalResult(str(tx.id), tx.status, None, "Awaiting admin approval")

    # Atomically claim the row so two workers can't double-broadcast.
    with db_tx.atomic():
        tx_locked = Transaction.objects.select_for_update().get(pk=tx.pk)
        if tx_locked.status != Transaction.STATUS_PENDING:
            return WithdrawalResult(str(tx.id), tx_locked.status, tx_locked.tx_hash, None)
        tx_locked.status = Transaction.STATUS_PROCESSING
        tx_locked.save(update_fields=["status", "updated_at"])

    # Read the destination address (encrypted at rest — the
    # EncryptedCharField decrypts transparently on access).
    to_address = tx.wallet_address
    amount_usdt = Decimal(tx.amount_usdt or 0)

    client = get_client(tx.network)
    try:
        tx_hash = client.send_usdt(to_address=to_address, amount_usdt=amount_usdt)
    except GatewayError as e:
        _fail_withdrawal(tx, reason=str(e), refund=not e.retryable)
        return WithdrawalResult(str(tx.id), Transaction.STATUS_FAILED if not e.retryable else Transaction.STATUS_PROCESSING, None, str(e))
    except Exception as e:
        _fail_withdrawal(tx, reason=f"Unexpected: {e}", refund=True)
        return WithdrawalResult(str(tx.id), Transaction.STATUS_FAILED, None, str(e))

    with db_tx.atomic():
        t = Transaction.objects.select_for_update().get(pk=tx.pk)
        t.tx_hash = tx_hash
        # Stay in PROCESSING until confirmation poller sees min confs.
        t.save(update_fields=["tx_hash", "updated_at"])
        log_audit(
            "withdraw_broadcast",
            user=t.user,
            tx_id=str(t.id),
            tx_hash=tx_hash,
            amount=str(amount_usdt),
            network=t.network,
        )

    return WithdrawalResult(str(tx.id), Transaction.STATUS_PROCESSING, tx_hash, None)


def confirm_pending_withdrawal(transaction_id: str) -> WithdrawalResult:
    """Poll the chain for a broadcast withdrawal's confirmation."""
    tx = Transaction.objects.select_related("user", "wallet").get(pk=transaction_id)
    if tx.type != Transaction.TYPE_WITHDRAW or tx.status != Transaction.STATUS_PROCESSING or not tx.tx_hash:
        return WithdrawalResult(str(tx.id), tx.status, tx.tx_hash, None)

    client = get_client(tx.network)
    try:
        transfer = client.get_transfer(tx.tx_hash)
    except GatewayError as e:
        logger.warning("Confirmation poll failed: %s", e)
        return WithdrawalResult(str(tx.id), tx.status, tx.tx_hash, str(e))

    required = (
        settings.MIN_CONFIRMATIONS_TRC20
        if tx.network == "TRC20"
        else settings.MIN_CONFIRMATIONS_ERC20
    )
    if not transfer or transfer.confirmations < required:
        return WithdrawalResult(
            str(tx.id), tx.status, tx.tx_hash,
            f"Awaiting confirmations ({transfer.confirmations if transfer else 0}/{required})",
        )

    with db_tx.atomic():
        t = Transaction.objects.select_for_update().get(pk=tx.pk)
        if t.status == Transaction.STATUS_COMPLETED:
            return WithdrawalResult(str(tx.id), t.status, t.tx_hash, None)
        t.status = Transaction.STATUS_COMPLETED
        t.confirmations = int(transfer.confirmations)
        t.block_number = int(transfer.block_number or 0)
        t.save(update_fields=["status", "confirmations", "block_number", "updated_at"])
        log_audit("withdraw_complete", user=t.user, tx_id=str(t.id), tx_hash=t.tx_hash,
                  amount=str(t.amount_usdt))

    from transactions.tasks import _push_wallet_event
    from notifications.tasks import send_notification
    try:
        send_notification.delay(
            str(tx.user_id),
            title="Withdrawal complete",
            body=f"Your withdrawal of {tx.amount_usdt} USDT has been confirmed.",
            notification_type="withdraw",
        )
        _push_wallet_event(tx.user_id, "transaction_update",
                           id=str(tx.id), status=Transaction.STATUS_COMPLETED, tx_type="withdraw")
    except Exception:
        logger.exception("post-confirm notify failed")

    return WithdrawalResult(str(tx.id), Transaction.STATUS_COMPLETED, tx.tx_hash, None)


def _fail_withdrawal(tx: Transaction, *, reason: str, refund: bool) -> None:
    """Mark a withdrawal failed and (optionally) refund the user."""
    with db_tx.atomic():
        t = Transaction.objects.select_for_update().get(pk=tx.pk)
        if t.status in (Transaction.STATUS_COMPLETED, Transaction.STATUS_FAILED):
            return
        t.status = Transaction.STATUS_FAILED
        t.failure_reason = (reason or "")[:500]
        t.save(update_fields=["status", "failure_reason", "updated_at"])

        if refund:
            wallet = Wallet.objects.select_for_update().get(pk=t.wallet_id)
            wallet.h_coin_balance = wallet.h_coin_balance + (t.amount_hcoin or Decimal(0))
            wallet.save(update_fields=["h_coin_balance", "updated_at"])

        log_audit("withdraw_failed", user=t.user, tx_id=str(t.id), reason=reason, refunded=refund)


# ─── Cursor / scanner helpers ───────────────────────────────────────
def get_or_create_cursor(network: str) -> GatewayCursor:
    cur, _ = GatewayCursor.objects.get_or_create(network=network)
    return cur


def advance_cursor(network: str, *, last_block: int, last_tx_hash: str = "") -> None:
    cur = get_or_create_cursor(network)
    if last_block and last_block > cur.last_block:
        cur.last_block = last_block
    if last_tx_hash:
        cur.last_tx_hash = last_tx_hash
    cur.last_scanned_at = timezone.now()
    cur.error_count = 0
    cur.last_error = ""
    cur.save(
        update_fields=[
            "last_block",
            "last_tx_hash",
            "last_scanned_at",
            "error_count",
            "last_error",
            "updated_at",
        ]
    )


def record_cursor_error(network: str, message: str) -> None:
    cur = get_or_create_cursor(network)
    cur.error_count = (cur.error_count or 0) + 1
    cur.last_error = (message or "")[:500]
    cur.save(update_fields=["error_count", "last_error", "updated_at"])
