# === FILE: backend/wallet/tests/test_admin_manual_deposit.py ===
"""Tests for the admin manual-deposit endpoint + service.

We verify that a manual credit:
  - rejects non-admin callers (403)
  - rejects bad input (missing user, non-positive amount)
  - credits the wallet atomically
  - creates a Transaction with type=deposit, status=completed, network=internal
  - sets has_completed_deposit on first credit
  - writes a `deposit_complete` audit row tagged `source=manual`
  - is idempotent when Idempotency-Key is replayed
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from core.audit import AuditLog
from transactions.models import Transaction
from wallet.models import Wallet


User = get_user_model()
URL = "/api/v1/wallet/admin/manual-deposit/"


@override_settings(USDT_PER_HCOIN="1.0", MIN_DEPOSIT_USDT="1")
class AdminManualDepositTests(APITestCase):

    def setUp(self):
        # Patch all post-commit side-effects so we don't need celery/channels/redis
        # to run during unit tests. The side-effect dispatcher is exercised by a
        # separate test below.
        self._patch = mock.patch(
            "wallet.services._fire_manual_deposit_side_effects"
        )
        self.mock_side_effects = self._patch.start()
        self.addCleanup(self._patch.stop)

        self.admin = User.objects.create_user(
            email="admin@example.com", password="x", is_staff=True, is_superuser=True
        )
        self.user = User.objects.create_user(
            email="alice@example.com", password="x"
        )
        # A users.signals post_save handler auto-creates a Wallet for every
        # new User, so we don't need to (and can't) create one here.

    # ─── auth / permission ────────────────────────────────────────────
    def test_anonymous_rejected(self):
        client = APIClient()
        r = client.post(URL, {"userId": str(self.user.pk), "amountUsdt": "10"}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_non_staff_user_rejected(self):
        client = APIClient()
        client.force_authenticate(self.user)
        r = client.post(URL, {"userId": str(self.user.pk), "amountUsdt": "10"}, format="json")
        self.assertEqual(r.status_code, 403)

    # ─── happy path ───────────────────────────────────────────────────
    def test_credits_wallet_and_creates_completed_transaction(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            r = client.post(
                URL,
                {"userId": str(self.user.pk), "amountUsdt": "25.5", "note": "support refund"},
                format="json",
            )
        self.assertEqual(r.status_code, 201, r.content)

        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.usdt_balance, Decimal("25.5"))
        # H Coin balance must also rise — same behaviour as a real deposit.
        # USDT_PER_HCOIN=1.0 in @override_settings, so 25.5 USDT → 25.5 H Coins.
        self.assertEqual(self.user.wallet.h_coin_balance, Decimal("25.5"))
        self.assertTrue(self.user.wallet.has_completed_deposit)

        tx = Transaction.objects.get(user=self.user)
        self.assertEqual(tx.type, "deposit")
        self.assertEqual(tx.status, "completed")
        self.assertEqual(tx.network, "internal")
        self.assertEqual(tx.amount_usdt, Decimal("25.5"))
        self.assertTrue(tx.tx_hash.startswith("manual-"))

        # audit log
        audit = AuditLog.objects.filter(action="deposit_complete").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.meta.get("source"), "manual")
        self.assertEqual(audit.meta.get("admin_user_id"), str(self.admin.pk))
        self.assertEqual(audit.meta.get("note"), "support refund")

        # post-commit dispatcher fired
        self.mock_side_effects.assert_called_once()
        kwargs = self.mock_side_effects.call_args.kwargs
        self.assertEqual(kwargs["is_first"], True)
        self.assertEqual(kwargs["tx_id"], str(tx.id))

    def test_userEmail_lookup(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        r = client.post(
            URL,
            {"userEmail": "ALICE@example.com", "amountUsdt": "5"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.usdt_balance, Decimal("5"))

    def test_second_deposit_does_not_re_qualify(self):
        # First deposit flips has_completed_deposit + would trigger referral hook
        client = APIClient()
        client.force_authenticate(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            client.post(URL, {"userId": str(self.user.pk), "amountUsdt": "10"}, format="json")
        self.mock_side_effects.reset_mock()

        # Second deposit must NOT re-fire the first-deposit branch
        with self.captureOnCommitCallbacks(execute=True):
            r = client.post(URL, {"userId": str(self.user.pk), "amountUsdt": "7"}, format="json")
        self.assertEqual(r.status_code, 201)
        kwargs = self.mock_side_effects.call_args.kwargs
        self.assertEqual(kwargs["is_first"], False)

        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.usdt_balance, Decimal("17"))
        self.assertEqual(self.user.wallet.h_coin_balance, Decimal("17"))

    # ─── validation ───────────────────────────────────────────────────
    def test_missing_user_returns_400(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        r = client.post(URL, {"amountUsdt": "1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_unknown_user_returns_404(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        r = client.post(URL, {"userId": 999999, "amountUsdt": "1"}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_negative_amount_rejected(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        r = client.post(URL, {"userId": str(self.user.pk), "amountUsdt": "-5"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_zero_amount_rejected(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        r = client.post(URL, {"userId": str(self.user.pk), "amountUsdt": "0"}, format="json")
        self.assertEqual(r.status_code, 400)

    # ─── idempotency ──────────────────────────────────────────────────
    def test_idempotency_key_replay_returns_same_tx(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        key = "11111111-2222-3333-4444-555555555555"

        r1 = client.post(
            URL, {"userId": str(self.user.pk), "amountUsdt": "9"},
            format="json", HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(r1.status_code, 201)

        r2 = client.post(
            URL, {"userId": str(self.user.pk), "amountUsdt": "9"},
            format="json", HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r1.data["id"], r2.data["id"])

        # Wallet credited only ONCE on both balances
        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.usdt_balance, Decimal("9"))
        self.assertEqual(self.user.wallet.h_coin_balance, Decimal("9"))
        self.assertEqual(
            Transaction.objects.filter(user=self.user).count(), 1
        )
