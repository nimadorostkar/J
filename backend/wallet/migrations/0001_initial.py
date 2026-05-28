# === FILE: backend/wallet/migrations/0001_initial.py ===
"""Initial schema for the Wallet + DepositAddress models.

Format mirrors Django's autogen output so docker-entrypoint's
`makemigrations` step is a no-op against this file.
"""
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Wallet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("h_coin_balance", models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=18)),
                ("usdt_balance", models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=18)),
                ("reward_active", models.BooleanField(default=False)),
                ("reward_end_time", models.DateTimeField(blank=True, null=True)),
                ("reward_duration_hours", models.IntegerField(default=12)),
                ("has_completed_deposit", models.BooleanField(default=False)),
                ("has_referral", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="wallet",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        check=models.Q(("h_coin_balance__gte", 0)),
                        name="wallet_hcoin_nonneg",
                    ),
                    models.CheckConstraint(
                        check=models.Q(("usdt_balance__gte", 0)),
                        name="wallet_usdt_nonneg",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DepositAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("network", models.CharField(choices=[("TRC20", "TRC20"), ("ERC20", "ERC20")], max_length=10)),
                ("address", models.CharField(max_length=128)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="deposit_addresses",
                    to=settings.AUTH_USER_MODEL,
                    help_text="Null for global shared addresses.",
                )),
            ],
            options={
                "indexes": [
                    models.Index(fields=["network", "is_active"], name="wallet_depo_network_23ca7e_idx"),
                ],
            },
        ),
    ]
