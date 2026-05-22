# === FILE: backend/notifications/models.py ===
"""In-app notifications."""
from django.conf import settings
from django.db import models


class Notification(models.Model):
    TYPE_CHOICES = [
        ("deposit", "Deposit"),
        ("withdraw", "Withdraw"),
        ("reward", "Reward"),
        ("commission", "Commission"),
        ("system", "System"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default="system")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.user})"
