# === FILE: backend/core/audit.py ===
"""AuditLog model + helpers for tracking financial actions."""
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("deposit_init", "Deposit initiated"),
        ("deposit_complete", "Deposit completed"),
        ("withdraw_init", "Withdrawal initiated"),
        ("withdraw_approve", "Withdrawal approved"),
        ("withdraw_complete", "Withdrawal completed"),
        ("reward_claim", "Reward claimed"),
        ("commission_pay", "Commission paid"),
        ("registration", "User registered"),
        ("login", "User login"),
        ("password_change", "Password change"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    meta = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


def log_audit(action, user=None, ip=None, **meta):
    """Convenience helper to write an audit row."""
    AuditLog.objects.create(user=user, action=action, ip_address=ip, meta=meta)
