# === FILE: backend/core/models.py ===
"""Re-exports core models so Django's app loader discovers them."""
from .audit import AuditLog  # noqa: F401
