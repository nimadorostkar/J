# === FILE: backend/trade/tasks.py ===
"""Celery tasks for the trade bot lifecycle."""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("tokenvault")


@shared_task(bind=True, acks_late=True, max_retries=3, default_retry_delay=30)
def complete_bot_session(self, session_id):
    """
    Complete a single bot session by id. Scheduled via `apply_async(countdown=)`
    at activation time. Idempotent — a duplicate call (e.g. from the
    reconcile sweep) is a no-op when status != ACTIVE.
    """
    from .services import complete_bot_session_now
    try:
        complete_bot_session_now(session_id)
    except Exception as exc:
        logger.exception("complete_bot_session error for %s", session_id)
        raise self.retry(exc=exc)


@shared_task(acks_late=True)
def reconcile_overdue_bot_sessions():
    """
    Safety-net sweep: complete any ACTIVE session whose `completes_at`
    has passed. Catches sessions whose original scheduled task was lost
    (Redis restart, worker crash before processing, etc).

    Wire into celery_beat to run every minute or so. Cheap — indexed
    on (status, completes_at).
    """
    from .models import BotSession

    now = timezone.now()
    overdue = list(
        BotSession.objects.filter(
            status=BotSession.STATUS_ACTIVE,
            completes_at__lte=now,
        ).values_list("id", flat=True)
    )
    for sid in overdue:
        # Dispatch via the regular completion task so it runs through the
        # same retry/idempotency machinery instead of running inline.
        complete_bot_session.delay(str(sid))
    return len(overdue)
