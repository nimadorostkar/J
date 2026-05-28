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
    # ── Crypto payment gateway ──────────────────────────────────────
    # Poll the master hot wallet on each chain for inbound USDT.
    "scan-master-wallet-every-2m": {
        "task": "payments.tasks.scan_master_wallet",
        "schedule": 120.0,
    },
    # Re-check confirmation depth on pending deposits / processing
    # withdrawals more frequently than the scanner so credits/payouts
    # finalize quickly.
    "poll-pending-deposits-every-1m": {
        "task": "payments.tasks.poll_pending_deposits",
        "schedule": 60.0,
    },
    "poll-pending-withdrawals-every-1m": {
        "task": "payments.tasks.poll_pending_withdrawals",
        "schedule": 60.0,
    },
}
