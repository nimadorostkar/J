# === FILE: backend/payments/tests/test_services.py ===
"""Integration tests for the payments gateway services.

These tests run under settings.GATEWAY_DRY_RUN=True (the test
defaults), so no real RPC is hit — the dry-run branch of each gateway
client returns synthetic confirmed transfers.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from payments.gateway import ChainTransfer
from payments.services import (
    WithdrawalLimitError,
    assert_within_withdrawal_limits,
    broadcast_withdrawal,
    confirm_and_credit_deposit,
    ingest_chain_event,
    requires_admin_review,
)
from transactions.models import Transaction
from wallet.models import DepositAddress, Wallet


User = get_user_model()


def _make_user(email="alice@example.com"):
    u = User.objects.create_user(email=email, password="testpass123")
    Wallet.objects.get_or_create(user=u)
    return u


@override_settings(
    GATEWAY_DRY_RUN=True,
    MIN_CONFIRMATIONS_TRC20=2,
    MIN_CONFIRMATIONS_ERC20=2,
    USDT_PER_HCOIN=10,
    MIN_DEPOSIT_USDT=1,
)
class DepositCreditTests(TestCase):
    def test_credits_wallet_once_when_confirmed(self):
        user = _make_user()
        wallet = user.wallet
        tx = Transaction.objects.create(
            user=user, wallet=wallet,
            type=Transaction.TYPE_DEPOSIT, network="TRC20",
            amount_usdt=Decimal("100"), amount_hcoin=Decimal("10"),
            tx_hash="simulated-foo", status=Transaction.STATUS_PENDING,
        )

        result = confirm_and_credit_deposit(str(tx.id))
        self.assertTrue(result.credited)

        wallet.refresh_from_db()
        self.assertEqual(wallet.usdt_balance, Decimal("100"))
        self.assertEqual(wallet.h_coin_balance, Decimal("10"))

        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.STATUS_COMPLETED)

        # Idempotent: second call must not double-credit.
        result2 = confirm_and_credit_deposit(str(tx.id))
        self.assertFalse(result2.credited)
        wallet.refresh_from_db()
        self.assertEqual(wallet.usdt_balance, Decimal("100"))

    def test_no_credit_when_transfer_missing(self):
        user = _make_user()
        tx = Transaction.objects.create(
            user=user, wallet=user.wallet,
            type=Transaction.TYPE_DEPOSIT, network="TRC20",
            amount_usdt=Decimal("50"), amount_hcoin=Decimal("5"),
            tx_hash="",  # no on-chain hash yet
            status=Transaction.STATUS_PENDING,
        )
        result = confirm_and_credit_deposit(str(tx.id))
        self.assertFalse(result.credited)
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.STATUS_PENDING)


@override_settings(
    GATEWAY_DRY_RUN=True,
    MIN_DEPOSIT_USDT=1,
    USDT_PER_HCOIN=10,
)
class ScannerIngestTests(TestCase):
    def test_unmatched_event_is_recorded_but_no_tx(self):
        before = Transaction.objects.count()
        event = ChainTransfer(
            tx_hash="0xabc1",
            log_index=0,
            block_number=100,
            from_address="TAnonymousAddress",
            to_address="TMaster",
            amount_usdt=Decimal("5"),
            confirmations=0,
            network="TRC20",
        )
        log = ingest_chain_event(event)
        self.assertIsNotNone(log)
        self.assertEqual(log.matched_user_id, "")
        self.assertEqual(Transaction.objects.count(), before)

    def test_matched_sender_creates_pending_deposit(self):
        user = _make_user()
        DepositAddress.objects.create(
            user=user, network="TRC20", address="TUserSourceAddr", is_active=True,
        )
        event = ChainTransfer(
            tx_hash="0xabc2",
            log_index=0,
            block_number=200,
            from_address="TUserSourceAddr",  # matches above
            to_address="TMaster",
            amount_usdt=Decimal("25"),
            confirmations=0,
            network="TRC20",
        )
        log = ingest_chain_event(event)
        self.assertEqual(log.matched_user_id, str(user.pk))
        self.assertIsNotNone(log.matched_transaction_id)
        tx = Transaction.objects.get(pk=log.matched_transaction_id)
        self.assertEqual(tx.user_id, user.pk)
        self.assertEqual(tx.amount_usdt, Decimal("25"))
        self.assertEqual(tx.status, Transaction.STATUS_PENDING)

    def test_duplicate_event_is_idempotent(self):
        user = _make_user()
        DepositAddress.objects.create(
            user=user, network="TRC20", address="TUserSourceAddr", is_active=True,
        )
        event = ChainTransfer(
            tx_hash="0xdup",
            log_index=0,
            block_number=201,
            from_address="TUserSourceAddr",
            to_address="TMaster",
            amount_usdt=Decimal("11"),
            confirmations=1,
            network="TRC20",
        )
        a = ingest_chain_event(event)
        b = ingest_chain_event(event)
        self.assertEqual(a.pk, b.pk)
        # Only ONE deposit transaction was created.
        self.assertEqual(
            Transaction.objects.filter(tx_hash="0xdup").count(), 1
        )


@override_settings(
    GATEWAY_DRY_RUN=True,
    MIN_WITHDRAWAL_USDT=5,
    MAX_WITHDRAWAL_USDT=1000,
    DAILY_WITHDRAWAL_LIMIT_USDT=2000,
    WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT=500,
)
class WithdrawalSafetyTests(TestCase):
    def test_below_minimum_rejected(self):
        u = _make_user()
        with self.assertRaises(WithdrawalLimitError) as ctx:
            assert_within_withdrawal_limits(u, amount_usdt=Decimal("1"))
        self.assertEqual(ctx.exception.code, "BELOW_MIN_WITHDRAWAL")

    def test_above_maximum_rejected(self):
        u = _make_user()
        with self.assertRaises(WithdrawalLimitError) as ctx:
            assert_within_withdrawal_limits(u, amount_usdt=Decimal("5000"))
        self.assertEqual(ctx.exception.code, "ABOVE_MAX_WITHDRAWAL")

    def test_daily_cap_enforced(self):
        u = _make_user()
        Transaction.objects.create(
            user=u, wallet=u.wallet,
            type=Transaction.TYPE_WITHDRAW, network="TRC20",
            amount_usdt=Decimal("1500"), amount_hcoin=Decimal("150"),
            status=Transaction.STATUS_COMPLETED,
        )
        # Adding 600 would push over the 2000 daily cap.
        with self.assertRaises(WithdrawalLimitError) as ctx:
            assert_within_withdrawal_limits(u, amount_usdt=Decimal("600"))
        self.assertEqual(ctx.exception.code, "DAILY_LIMIT_EXCEEDED")

    def test_requires_admin_review_threshold(self):
        self.assertFalse(requires_admin_review(Decimal("100")))
        self.assertTrue(requires_admin_review(Decimal("500")))
        self.assertTrue(requires_admin_review(Decimal("999999")))


@override_settings(
    GATEWAY_DRY_RUN=True,
    MIN_CONFIRMATIONS_TRC20=2,
    USDT_PER_HCOIN=10,
)
class WithdrawalBroadcastTests(TestCase):
    def test_broadcast_writes_tx_hash_and_processing(self):
        u = _make_user()
        u.wallet.h_coin_balance = Decimal("100")
        u.wallet.save()
        tx = Transaction.objects.create(
            user=u, wallet=u.wallet,
            type=Transaction.TYPE_WITHDRAW, network="TRC20",
            amount_usdt=Decimal("50"), amount_hcoin=Decimal("5"),
            wallet_address="TUserPayoutAddress",
            status=Transaction.STATUS_PENDING,
        )
        result = broadcast_withdrawal(str(tx.id))
        self.assertEqual(result.status, Transaction.STATUS_PROCESSING)
        tx.refresh_from_db()
        self.assertTrue(tx.tx_hash and tx.tx_hash.startswith("simulated-"))
        self.assertEqual(tx.status, Transaction.STATUS_PROCESSING)

    def test_admin_review_blocks_broadcast(self):
        u = _make_user()
        tx = Transaction.objects.create(
            user=u, wallet=u.wallet,
            type=Transaction.TYPE_WITHDRAW, network="TRC20",
            amount_usdt=Decimal("99999"), amount_hcoin=Decimal("9999.9"),
            wallet_address="TUserPayoutAddress",
            status=Transaction.STATUS_PENDING,
            requires_admin_review=True,
        )
        result = broadcast_withdrawal(str(tx.id))
        self.assertEqual(result.status, Transaction.STATUS_PENDING)
        self.assertIn("Awaiting admin", result.error or "")
        tx.refresh_from_db()
        self.assertIsNone(tx.tx_hash)
