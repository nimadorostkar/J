# === FILE: backend/referrals/models.py ===
"""Referral graph. L1 = direct, L2 = grandchild.

Also tracks ReferralMilestoneReward — every Nth successful L1 referral
earns the inviter a fixed coin reward (configurable via settings). The
unique constraint on (user, milestone) is the canonical idempotency
guarantee: even if two registrations race, the second insert raises
IntegrityError and no double-pay happens.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef


# Per-referral status strings exposed to the API.
# Each step strictly implies the previous ones (REGISTERED → VERIFIED → DEPOSITED → QUALIFIED).
REFERRAL_STATUS_REGISTERED = "registered"
REFERRAL_STATUS_VERIFIED = "verified"
REFERRAL_STATUS_DEPOSITED = "first_deposit_completed"
REFERRAL_STATUS_QUALIFIED = "qualified"


class ReferralQuerySet(models.QuerySet):
    """Queryset helpers for filtering by qualification status."""

    def with_status_flags(self):
        """
        Annotate each row with three booleans the API can pass through:
          • _is_verified  — invited_user.is_email_verified
          • _has_deposit  — invited_user has ≥1 completed deposit transaction
          • _is_qualified — has_deposit AND level==1 (only L1 counts toward rewards)
        """
        from transactions.models import Transaction

        completed_deposit = Transaction.objects.filter(
            user=OuterRef("invited_user"),
            type=Transaction.TYPE_DEPOSIT,
            status=Transaction.STATUS_COMPLETED,
        )
        return self.annotate(
            _has_deposit=Exists(completed_deposit),
            _is_verified=models.F("invited_user__is_email_verified"),
        )

    def qualified(self):
        """L1 referrals whose invited user has at least one completed deposit."""
        return self.with_status_flags().filter(level=1, _has_deposit=True)

    def qualified_for(self, inviter):
        """Convenience — qualified L1 referrals belonging to a given inviter."""
        return self.qualified().filter(inviter=inviter)


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

    # Custom queryset for qualification filters.
    objects = ReferralQuerySet.as_manager()

    # ── Per-instance status helpers ───────────────────────────────────
    def has_completed_deposit(self) -> bool:
        from transactions.models import Transaction
        return Transaction.objects.filter(
            user=self.invited_user,
            type=Transaction.TYPE_DEPOSIT,
            status=Transaction.STATUS_COMPLETED,
        ).exists()

    def is_qualified(self) -> bool:
        """Counts toward milestone rewards: L1 + ≥1 completed deposit."""
        return self.level == 1 and self.has_completed_deposit()

    def status_label(self) -> str:
        """The most-advanced status this referral has reached."""
        if self.is_qualified():
            return REFERRAL_STATUS_QUALIFIED
        if self.has_completed_deposit():
            return REFERRAL_STATUS_DEPOSITED
        if getattr(self.invited_user, "is_email_verified", False):
            return REFERRAL_STATUS_VERIFIED
        return REFERRAL_STATUS_REGISTERED

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


class ReferralMilestoneReward(models.Model):
    """
    Audit row for each milestone reward an inviter has been paid.

    `milestone` is the L1 referral count at which the reward was earned
    (5, 10, 15, ...). The unique_together constraint guarantees a user
    can never be paid twice for the same milestone, even under racing
    concurrent registrations.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_milestones",
    )
    milestone = models.PositiveIntegerField(
        help_text="L1 referral count this reward was earned at (5, 10, 15, ...)."
    )
    amount_hcoin = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="milestone_rewards",
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "milestone"],
                name="unique_user_milestone",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-awarded_at"]),
        ]

    def __str__(self):
        return f"{self.user} milestone {self.milestone} → {self.amount_hcoin} H"
