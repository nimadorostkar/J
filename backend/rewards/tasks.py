# === FILE: backend/rewards/tasks.py ===
"""Beat-driven tasks: mark cycles claimable, rotate global cycle."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import GlobalCycle, RewardCycle

logger = logging.getLogger("tokenvault")


@shared_task(acks_late=True)
def check_reward_cycles():
    """Promote ACTIVE cycles to CLAIMABLE when their end-time passes."""
    now = timezone.now()
    qs = RewardCycle.objects.filter(
        status=RewardCycle.STATUS_ACTIVE, ends_at__lte=now
    )
    user_ids = list(qs.values_list("user_id", flat=True))
    n = qs.update(status=RewardCycle.STATUS_CLAIMABLE)
    logger.info("Marked %s reward cycles claimable", n)

    # WS notifications
    if user_ids:
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            layer = get_channel_layer()
            if layer:
                for uid in user_ids:
                    async_to_sync(layer.group_send)(
                        f"wallet_{uid}", {"type": "reward_claimable"},
                    )
        except Exception:
            logger.exception("WS push failed in check_reward_cycles")
    return n


@shared_task(acks_late=True)
def rotate_global_cycle():
    """If no active GlobalCycle exists or current one expired, start a new one."""
    now = timezone.now()
    active = GlobalCycle.objects.filter(is_active=True).first()
    if active and active.end_time > now:
        return "still-active"
    if active:
        active.is_active = False
        active.save(update_fields=["is_active"])
    GlobalCycle.objects.create(
        label="Season",
        start_time=now,
        end_time=now + timedelta(days=settings.GLOBAL_CYCLE_DAYS),
        is_active=True,
    )
    return "rotated"
