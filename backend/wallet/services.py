# === FILE: backend/wallet/services.py ===
"""Wallet services: eligibility gate, debit/credit helpers."""
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from core.exceptions import InsufficientBalance, WithdrawalLocked

from .models import Wallet

logger = logging.getLogger("tokenvault")


@dataclass
class EligibilityResult:
    eligible: bool
    missing_conditions: list
    details: dict

    def to_dict(self):
        return {
            "eligible": self.eligible,
            "missingConditions": self.missing_conditions,
            "details": self.details,
        }


def check_withdrawal_eligibility(user) -> EligibilityResult:
    """Return whether `user` can currently withdraw.

    Conditions (BOTH must be met):
      A. At least 1 completed deposit  (wallet.has_completed_deposit)
      B. At least 1 referral           (wallet.has_referral)
    """
    wallet = Wallet.objects.filter(user=user).first()
    has_deposit = bool(wallet and wallet.has_completed_deposit)
    has_referral = bool(wallet and wallet.has_referral)

    missing = []
    if not has_deposit:
        missing.append("initial_deposit")
    if not has_referral:
        missing.append("referral")

    details = {
        "initial_deposit": {
            "met": has_deposit,
            "description": "Make your first USDT deposit to unlock withdrawals.",
        },
        "referral": {
            "met": has_referral,
            "description": "Invite at least one person who registers with your code.",
        },
    }
    return EligibilityResult(
        eligible=not missing,
        missing_conditions=missing,
        details=details,
    )


def assert_can_withdraw(user):
    result = check_withdrawal_eligibility(user)
    if not result.eligible:
        raise WithdrawalLocked(result.missing_conditions, result.details)


@transaction.atomic
def credit_hcoin(user, amount: Decimal):
    if amount <= 0:
        raise ValueError("Credit amount must be positive.")
    wallet = Wallet.objects.select_for_update().get(user=user)
    wallet.h_coin_balance = wallet.h_coin_balance + amount
    wallet.save(update_fields=["h_coin_balance", "updated_at"])
    return wallet


@transaction.atomic
def debit_hcoin(user, amount: Decimal):
    if amount <= 0:
        raise ValueError("Debit amount must be positive.")
    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.h_coin_balance < amount:
        raise InsufficientBalance("Insufficient H Coin balance.")
    wallet.h_coin_balance = wallet.h_coin_balance - amount
    wallet.save(update_fields=["h_coin_balance", "updated_at"])
    return wallet


@transaction.atomic
def credit_usdt(user, amount: Decimal, first_deposit: bool = False):
    if amount <= 0:
        raise ValueError("Credit amount must be positive.")
    wallet = Wallet.objects.select_for_update().get(user=user)
    wallet.usdt_balance = wallet.usdt_balance + amount
    if first_deposit and not wallet.has_completed_deposit:
        wallet.has_completed_deposit = True
        wallet.save(update_fields=["usdt_balance", "has_completed_deposit", "updated_at"])
    else:
        wallet.save(update_fields=["usdt_balance", "updated_at"])
    return wallet


@transaction.atomic
def debit_usdt(user, amount: Decimal):
    if amount <= 0:
        raise ValueError("Debit amount must be positive.")
    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.usdt_balance < amount:
        raise InsufficientBalance("Insufficient USDT balance.")
    wallet.usdt_balance = wallet.usdt_balance - amount
    wallet.save(update_fields=["usdt_balance", "updated_at"])
    return wallet


# ──────────────────────────────────────────────────────────────────────
# Admin: manual deposit
# ──────────────────────────────────────────────────────────────────────
def admin_credit_manual_deposit(
    *,
    admin_user,
    target_user,
    amount_usdt: Decimal,
    note: str = "",
    idempotency_key=None,
    ip: str = None,
):
    """Credit a user's wallet EXACTLY like a real successful USDT deposit.

    The created Transaction row is `type=deposit`, `status=completed`,
    `network=internal` so it shows up in every existing report, wallet
    history, analytics, and notification flow without any code anywhere
    needing to special-case it.

    All side-effects of a real deposit fire:
      * Wallet USDT balance credited (atomic, SELECT FOR UPDATE).
      * `wallet.has_completed_deposit = True` on first deposit.
      * AuditLog row (`deposit_complete` with `meta.source="manual"`).
      * Referral milestone hook (`on_deposit_completed`) on first deposit.
      * Notification row + WebSocket push to the user.
      * WebSocket `balance_update` and `transaction_update` events.

    Idempotency: callers may pass `idempotency_key` (UUID-castable). If a
    Transaction with the same (target_user, idempotency_key) already
    exists, it is returned untouched.
    """
    from transactions.models import Transaction
    from core.audit import log_audit

    if not admin_user or not getattr(admin_user, "is_staff", False):
        # Defence in depth — view already checks IsAdminUser.
        raise PermissionError("Only staff users may issue a manual deposit.")
    if amount_usdt is None or Decimal(amount_usdt) <= 0:
        raise ValueError("Manual deposit amount must be positive.")
    if not target_user or not getattr(target_user, "pk", None):
        raise ValueError("Target user is required.")

    amount_usdt = Decimal(amount_usdt)

    # Coerce idempotency key to UUID (or None). Re-runs with the same key
    # short-circuit to the already-created transaction.
    idem_uuid = None
    if idempotency_key:
        try:
            idem_uuid = uuid.UUID(str(idempotency_key))
        except (TypeError, ValueError):
            # Non-UUID keys are accepted but normalised via UUID5(namespace, key).
            idem_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"manual-deposit:{idempotency_key}")
        existing = Transaction.objects.filter(
            user=target_user, idempotency_key=idem_uuid
        ).first()
        if existing:
            return existing

    amount_hcoin = amount_usdt / Decimal(settings.USDT_PER_HCOIN)
    tx_hash = f"manual-{uuid.uuid4().hex[:24]}"

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(user=target_user)
        is_first = not wallet.has_completed_deposit
        wallet.usdt_balance = wallet.usdt_balance + amount_usdt
        # Mirror the real-deposit flow: credit the equivalent H Coin balance
        # so the game-currency wallet reflects the deposit just like USDT.
        wallet.h_coin_balance = wallet.h_coin_balance + amount_hcoin
        update_fields = ["usdt_balance", "h_coin_balance", "updated_at"]
        if is_first:
            wallet.has_completed_deposit = True
            update_fields.append("has_completed_deposit")
        wallet.save(update_fields=update_fields)

        tx = Transaction.objects.create(
            user=target_user,
            wallet=wallet,
            type=Transaction.TYPE_DEPOSIT,
            network="internal",
            amount_usdt=amount_usdt,
            amount_hcoin=amount_hcoin,
            tx_hash=tx_hash,
            status=Transaction.STATUS_COMPLETED,
            idempotency_key=idem_uuid,
            ip_address=ip,
        )

        # Single audit row — same `deposit_complete` action that real
        # deposits emit, with `source="manual"` so reports can filter if
        # they want; without filtering it counts as a normal deposit.
        # NB: every value must be JSON-serialisable because AuditLog.meta
        # is a JSONField. Coerce UUIDs/Decimals to strings.
        log_audit(
            "deposit_complete",
            user=target_user,
            ip=ip,
            tx_id=str(tx.id),
            amount=str(amount_usdt),
            first_deposit=is_first,
            source="manual",
            admin_user_id=str(admin_user.pk),
            admin_email=getattr(admin_user, "email", ""),
            note=note or "",
        )

        # Run downstream notifications / WS pushes / referral hook AFTER
        # the atomic block commits — otherwise consumers could read stale
        # balances or attempt to resolve a transaction that's not yet visible.
        transaction.on_commit(
            lambda: _fire_manual_deposit_side_effects(tx_id=str(tx.id), is_first=is_first)
        )

    return tx


def _fire_manual_deposit_side_effects(*, tx_id: str, is_first: bool):
    """Mirror `verify_deposit`'s post-commit fan-out for the manual path."""
    from transactions.models import Transaction
    try:
        tx = Transaction.objects.select_related("user", "wallet").get(pk=tx_id)
    except Transaction.DoesNotExist:
        logger.warning("manual deposit side-effects: tx %s missing", tx_id)
        return

    if is_first:
        try:
            from referrals.services import on_deposit_completed
            on_deposit_completed(tx.user)
        except Exception:
            logger.exception(
                "on_deposit_completed failed after manual deposit for user %s", tx.user_id
            )

    try:
        from notifications.tasks import send_notification
        send_notification.delay(
            str(tx.user_id),
            title="Deposit confirmed",
            body=f"Your deposit of {tx.amount_usdt} USDT has been credited.",
            notification_type="deposit",
        )
    except Exception:
        logger.exception("send_notification failed after manual deposit")

    try:
        from transactions.tasks import _push_wallet_event
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
            h_coins=str(tx.wallet.h_coin_balance),
            usdt_balance=str(tx.wallet.usdt_balance),
        )
    except Exception:
        logger.exception("WS push failed after manual deposit")
