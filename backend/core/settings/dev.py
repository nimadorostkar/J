# === FILE: backend/core/settings/dev.py ===
from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Looser throttling for dev
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa
    "user": "10000/min",
    "anon": "1000/min",
}
