# === FILE: backend/users/signals.py ===
"""Auto-provision a Wallet whenever a User is created."""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_wallet_for_user(sender, instance, created, **kwargs):
    if not created:
        return
    from wallet.models import Wallet
    Wallet.objects.get_or_create(user=instance)
