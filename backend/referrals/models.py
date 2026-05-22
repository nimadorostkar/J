# === FILE: backend/referrals/models.py ===
"""Referral graph. L1 = direct, L2 = grandchild."""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Referral(models.Model):
    LEVEL_CHOICES = [(1, "Level 1"), (2, "Level 2")]

    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_as_inviter",
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_as_invited",
    )
    level = models.IntegerField(choices=LEVEL_CHOICES)

    total_commission_earned_hcoin = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["inviter", "level"]),
            models.Index(fields=["invited_user", "level"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["inviter", "invited_user", "level"],
                name="unique_inviter_invited_level",
            ),
        ]

    def __str__(self):
        return f"L{self.level} {self.inviter} -> {self.invited_user}"
