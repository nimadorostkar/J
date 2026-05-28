# === FILE: backend/payments/migrations/0001_initial.py ===
"""Initial schema for the payments gateway models."""
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="GatewayCursor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("network", models.CharField(choices=[("TRC20", "TRC20"), ("ERC20", "ERC20")], max_length=10, unique=True)),
                ("last_block", models.BigIntegerField(default=0)),
                ("last_tx_hash", models.CharField(blank=True, default="", max_length=128)),
                ("last_scanned_at", models.DateTimeField(blank=True, null=True)),
                ("error_count", models.IntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Gateway cursor",
                "verbose_name_plural": "Gateway cursors",
            },
        ),
        migrations.CreateModel(
            name="GatewayEventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("network", models.CharField(choices=[("TRC20", "TRC20"), ("ERC20", "ERC20")], max_length=10)),
                ("tx_hash", models.CharField(db_index=True, max_length=128)),
                ("log_index", models.IntegerField(default=0)),
                ("block_number", models.BigIntegerField()),
                ("from_address", models.CharField(max_length=128)),
                ("to_address", models.CharField(db_index=True, max_length=128)),
                ("amount_usdt", models.DecimalField(decimal_places=8, max_digits=30)),
                ("confirmations_at_ingest", models.IntegerField(default=0)),
                ("matched_user_id", models.CharField(blank=True, default="", max_length=64)),
                ("matched_transaction_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["network", "to_address"], name="payments_ga_network_5a8eef_idx"),
                    models.Index(fields=["matched_user_id"], name="payments_ga_matched_61c1a3_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("network", "tx_hash", "log_index"),
                        name="gateway_event_unique",
                    ),
                ],
            },
        ),
    ]
