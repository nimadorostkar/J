# === FILE: backend/transactions/migrations/0004_transaction_tx_unique_hash_when_set_and_more.py ===
"""No-op migration. See 0003 for context."""
from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0003_remove_transaction_tx_unique_hash_when_set_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = []
