# === FILE: backend/transactions/migrations/0002_gateway_fields.py ===
"""Crypto payment gateway fields on Transaction.

Adds: from_address, block_number, confirmations, network_fee_usdt,
requires_admin_review, admin_approved_by, admin_approved_at,
failure_reason.

All nullable / defaulted so the migration is safe to apply against a
live database.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("transactions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="from_address",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="block_number",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="confirmations",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="transaction",
            name="network_fee_usdt",
            field=models.DecimalField(blank=True, decimal_places=8, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="requires_admin_review",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="transaction",
            name="admin_approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="admin_approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="failure_reason",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
