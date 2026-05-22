# === FILE: backend/notifications/tasks.py ===
"""Celery task: persist a Notification row and push it via Channels."""
import logging

from celery import shared_task

logger = logging.getLogger("tokenvault")


@shared_task(acks_late=True)
def send_notification(user_id, title, body, notification_type="system"):
    from .models import Notification
    try:
        notif = Notification.objects.create(
            user_id=user_id,
            title=title,
            body=body,
            type=notification_type,
        )
    except Exception:
        logger.exception("Failed to create notification")
        return None

    # Push via Channels
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f"wallet_{user_id}",
                {
                    "type": "notification",
                    "id": notif.id,
                    "title": title,
                    "body": body,
                    "notification_type": notification_type,
                },
            )
    except Exception:
        logger.exception("Failed to push WS notification")
    return notif.id
