# === FILE: backend/core/settings/dev.py ===
from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# In dev, accept any origin so the Vite dev server / curl / Postman
# all just work without per-port allowlists.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Looser throttling for dev
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa
    "user": "10000/min",
    "anon": "1000/min",
}
