# === FILE: backend/transactions/migrations/0001_initial.py ===
"""Initial schema for the Transaction model.

Format mirrors what Django's makemigrations autogen would produce so
the docker-entrypoint's boot-time `makemigrations --noinput` step is a
no-op against this file (no spurious rename / re-add migrations).
"""
import uuid

import django.db.models.deletion
import encrypted_model_fields.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("wallet", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type", models.CharField(choices=[
                    ("deposit", "Deposit"),
                    ("withdraw", "Withdraw"),
                    ("reward", "Reward"),
                    ("commission", "Commission"),
                    ("referral_milestone", "Referral milestone"),
                    ("bot_fee", "Bot fee"),
                    ("bot_profit", "Bot profit"),
                ], max_length=24)),
                ("network", models.CharField(blank=True, choices=[
                    ("TRC20", "TRC20"),
                    ("ERC20", "ERC20"),
                    ("internal", "Internal"),
                ], max_length=12, null=True)),
                ("amount_usdt", models.DecimalField(blank=True, decimal_places=8, max_digits=18, null=True)),
                ("amount_hcoin", models.DecimalField(decimal_places=8, max_digits=18)),
                ("wallet_address", encrypted_model_fields.fields.EncryptedCharField(blank=True, null=True)),
                ("tx_hash", models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ("status", models.CharField(choices=[
                    ("pending", "Pending"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ], default="pending", max_length=16)),
                ("idempotency_key", models.UUIDField(blank=True, null=True)),
                ("commission_level", models.IntegerField(blank=True, null=True)),
                ("commission_rate", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("commission_from_user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="commissions_generated",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("wallet", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions",
                    to="wallet.wallet",
                )),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="transaction_user_id_386a11_idx"),
                    models.Index(fields=["status", "type"], name="transaction_status_ea0d93_idx"),
                    models.Index(fields=["tx_hash"], name="transaction_tx_hash_2e17d1_idx"),
                    models.Index(fields=["type", "commission_from_user"], name="transaction_type_13400f_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(
                            models.Q(("tx_hash", None), _negated=True),
                            models.Q(("tx_hash", ""), _negated=True),
                        ),
                        fields=("tx_hash",),
                        name="tx_unique_hash_when_set",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("idempotency_key", None), _negated=True),
                        fields=("user", "idempotency_key"),
                        name="tx_idempotency_unique_per_user",
                    ),
                ],
            },
        ),
    ]
