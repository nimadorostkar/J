# === FILE: backend/core/celery.py ===
"""Celery application entry-point."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.prod")

app = Celery("tokenvault")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Beat schedule
app.conf.beat_schedule = {
    "check-reward-cycles-every-minute": {
        "task": "rewards.tasks.check_reward_cycles",
        "schedule": 60.0,
    },
    "expire-stale-deposits-hourly": {
        "task": "transactions.tasks.expire_stale_deposits",
        "schedule": crontab(minute=0),
    },
    "rotate-global-cycle-daily": {
        "task": "rewards.tasks.rotate_global_cycle",
        "schedule": crontab(hour=0, minute=5),
    },
}
