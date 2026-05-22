# === FILE: backend/core/settings/__init__.py ===
import os

_env = os.environ.get("DJANGO_ENV", "dev").lower()
if _env == "prod":
    from .prod import *  # noqa
else:
    from .dev import *  # noqa
