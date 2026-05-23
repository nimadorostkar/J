# === FILE: backend/trade/models.py ===
"""Bot trading sessions.

A BotSession represents a single activation of either the Basic or Expert
bot. The flow is:

   ┌──────────────┐   activate    ┌────────────┐   complete    ┌────────────┐
   │ user balance │───── fee ────▶│  ACTIVE    │──── profit ──▶│ COMPLETED  │
   └──────────────┘               └────────────┘               └────────────┘

Only one ACTIVE session per user is allowed at any time (enforced by a
partial unique constraint on (user, status='active')).
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class BotSession(models.Model):
    BOT_BASIC = "basic"
    BOT_EXPERT = "expert"
    BOT_CHOICES = [
        (BOT_BASIC, "Basic Bot Trader"),
        (BOT_EXPERT, "Expert Bot Trader"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bot_sessions",
    )
    bot_type = models.CharField(max_length=16, choices=BOT_CHOICES)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )

    # Snapshots taken at activation — the user always pays/earns based on
    # the balance/percentages at the time they activated the bot.
    balance_at_start_hcoin = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0"),
        help_text="User's H Coin balance immediately before fee deduction.",
    )
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2)
    fee_amount_hcoin = models.DecimalField(max_digits=18, decimal_places=8)

    duration_seconds = models.IntegerField()
    profit_min_percent = models.DecimalField(max_digits=5, decimal_places=2)
    profit_max_percent = models.DecimalField(max_digits=5, decimal_places=2)

    # Populated only when status == COMPLETED.
    profit_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    profit_amount_hcoin = models.DecimalField(
        max_digits=18, decimal_places=8, null=True, blank=True,
    )

    started_at = models.DateTimeField(auto_now_add=True)
    completes_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    fee_transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    profit_transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["status", "completes_at"]),
        ]
        constraints = [
            # At most one active session per user — partial unique index.
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="active"),
                name="unique_active_bot_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.bot_type} {self.status} ({self.user})"

    @property
    def is_due(self) -> bool:
        from django.utils import timezone
        return self.status == self.STATUS_ACTIVE and self.completes_at <= timezone.now()
