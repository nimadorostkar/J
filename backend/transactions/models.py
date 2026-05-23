# === FILE: backend/transactions/models.py ===
"""Transaction record — covers deposit, withdraw, reward, and commission."""
import uuid

from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


class Transaction(models.Model):
    TYPE_DEPOSIT = "deposit"
    TYPE_WITHDRAW = "withdraw"
    TYPE_REWARD = "reward"
    TYPE_COMMISSION = "commission"
    TYPE_REFERRAL_MILESTONE = "referral_milestone"
    TYPE_BOT_FEE = "bot_fee"
    TYPE_BOT_PROFIT = "bot_profit"
    TYPE_CHOICES = [
        (TYPE_DEPOSIT, "Deposit"),
        (TYPE_WITHDRAW, "Withdraw"),
        (TYPE_REWARD, "Reward"),
        (TYPE_COMMISSION, "Commission"),
        (TYPE_REFERRAL_MILESTONE, "Referral milestone"),
        (TYPE_BOT_FEE, "Bot fee"),
        (TYPE_BOT_PROFIT, "Bot profit"),
    ]

    NETWORK_CHOICES = [
        ("TRC20", "TRC20"),
        ("ERC20", "ERC20"),
        ("internal", "Internal"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    wallet = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    network = models.CharField(max_length=12, choices=NETWORK_CHOICES, null=True, blank=True)

    amount_usdt = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    amount_hcoin = models.DecimalField(max_digits=18, decimal_places=8)

    # Encrypted-at-rest withdrawal destination address.
    wallet_address = EncryptedCharField(max_length=128, null=True, blank=True)

    tx_hash = models.CharField(max_length=128, null=True, blank=True, db_index=True)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    idempotency_key = models.UUIDField(null=True, blank=True)

    # Commission-specific snapshot fields
    commission_from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commissions_generated",
    )
    commission_level = models.IntegerField(null=True, blank=True)
    commission_rate = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "type"]),
            models.Index(fields=["tx_hash"]),
            models.Index(fields=["type", "commission_from_user"]),
        ]
        constraints = [
            # tx_hash, when present, must be unique
            models.UniqueConstraint(
                fields=["tx_hash"],
                condition=~models.Q(tx_hash=None) & ~models.Q(tx_hash=""),
                name="tx_unique_hash_when_set",
            ),
            # idempotency_key (user-scoped) unique when set
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=~models.Q(idempotency_key=None),
                name="tx_idempotency_unique_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.type} {self.amount_hcoin} ({self.status})"
