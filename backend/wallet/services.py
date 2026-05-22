# === FILE: backend/wallet/services.py ===
"""Wallet services: eligibility gate, debit/credit helpers."""
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from core.exceptions import InsufficientBalance, WithdrawalLocked

from .models import Wallet


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
