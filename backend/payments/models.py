# === FILE: backend/payments/models.py ===
"""Persistent state for the on-chain scanner.

`GatewayCursor` remembers the last block / tx the scanner has processed
for each network so it can resume after a restart without re-scanning
the entire chain (and without double-crediting).
"""
from django.db import models


class GatewayCursor(models.Model):
    """One row per network — the scanner's high-water mark."""

    NETWORK_CHOICES = [("TRC20", "TRC20"), ("ERC20", "ERC20")]

    network = models.CharField(max_length=10, choices=NETWORK_CHOICES, unique=True)
    last_block = models.BigIntegerField(default=0)
    last_tx_hash = models.CharField(max_length=128, blank=True, default="")
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    error_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gateway cursor"
        verbose_name_plural = "Gateway cursors"

    def __str__(self):
        return f"{self.network}@{self.last_block}"


class GatewayEventLog(models.Model):
    """Append-only log of every chain event the scanner ingests.

    Acts as the idempotency oracle: before a Transaction is credited the
    code checks `tx_hash + log_index` here. Persisting a row in a DB
    transaction next to the wallet credit means even a crashed worker
    can't double-credit on retry.
    """

    network = models.CharField(max_length=10, choices=GatewayCursor.NETWORK_CHOICES)
    tx_hash = models.CharField(max_length=128, db_index=True)
    log_index = models.IntegerField(default=0)
    block_number = models.BigIntegerField()
    from_address = models.CharField(max_length=128)
    to_address = models.CharField(max_length=128, db_index=True)
    amount_usdt = models.DecimalField(max_digits=30, decimal_places=8)
    confirmations_at_ingest = models.IntegerField(default=0)
    matched_user_id = models.CharField(max_length=64, blank=True, default="")
    matched_transaction_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["network", "to_address"]),
            models.Index(fields=["matched_user_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["network", "tx_hash", "log_index"],
                name="gateway_event_unique",
            ),
        ]

    def __str__(self):
        return f"{self.network} {self.tx_hash[:10]}.. {self.amount_usdt} USDT"
