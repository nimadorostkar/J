# === FILE: backend/wallet/models.py ===
"""Wallet model — one per user. Stores balances + withdrawal-gate booleans."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    h_coin_balance = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    usdt_balance = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )

    reward_active = models.BooleanField(default=False)
    reward_end_time = models.DateTimeField(null=True, blank=True)
    reward_duration_hours = models.IntegerField(default=12)

    # Cached booleans for the withdrawal-eligibility gate (O(1) reads).
    has_completed_deposit = models.BooleanField(default=False)
    has_referral = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(h_coin_balance__gte=0), name="wallet_hcoin_nonneg"
            ),
            CheckConstraint(
                check=Q(usdt_balance__gte=0), name="wallet_usdt_nonneg"
            ),
        ]

    @property
    def usdt_equivalent(self) -> Decimal:
        return self.h_coin_balance * Decimal(settings.USDT_PER_HCOIN)

    def __str__(self):
        return f"Wallet<{self.user.email}>"


class DepositAddress(models.Model):
    """Deposit addresses surfaced to users — usually configured by ops."""

    NETWORK_CHOICES = [("TRC20", "TRC20"), ("ERC20", "ERC20")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deposit_addresses",
        null=True,
        blank=True,
        help_text="Null for global shared addresses.",
    )
    network = models.CharField(max_length=10, choices=NETWORK_CHOICES)
    address = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["network", "is_active"])]

    def __str__(self):
        return f"{self.network}:{self.address[:8]}..."
