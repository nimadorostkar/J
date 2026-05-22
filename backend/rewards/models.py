# === FILE: backend/rewards/models.py ===
"""Per-user reward cycle and global 30-day cycle."""
from decimal import Decimal

from django.conf import settings
from django.db import models


class RewardCycle(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_CLAIMABLE = "claimable"
    STATUS_CLAIMED = "claimed"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_CLAIMABLE, "Claimable"),
        (STATUS_CLAIMED, "Claimed"),
        (STATUS_EXPIRED, "Expired"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reward_cycles",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField()
    claimed_at = models.DateTimeField(null=True, blank=True)
    reward_amount_hcoin = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "ends_at"]),
        ]
        ordering = ["-started_at"]


class GlobalCycle(models.Model):
    """30-day shared countdown shown on the Home tab."""

    label = models.CharField(max_length=64, default="Season")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.label} ({self.start_time:%Y-%m-%d} -> {self.end_time:%Y-%m-%d})"
