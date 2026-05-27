# === FILE: backend/transactions/admin.py ===
from decimal import Decimal

from django.contrib import admin, messages
from django.db import transaction as db_tx

from core.audit import log_audit

from .models import Transaction
from .tasks import process_withdrawal


@admin.action(description="Approve selected withdrawals (queue payout)")
def approve_withdrawals(modeladmin, request, queryset):
    n = 0
    for tx in queryset.filter(type=Transaction.TYPE_WITHDRAW,
                              status__in=[Transaction.STATUS_PENDING]):
        log_audit("withdraw_approve", user=request.user, tx_id=str(tx.id))
        process_withdrawal.delay(str(tx.id))
        n += 1
    messages.success(request, f"{n} withdrawal(s) queued for payout.")


@admin.action(description="Force-complete deposit (credit wallet)")
def force_complete_deposit(modeladmin, request, queryset):
    n = 0
    newly_qualified_users = []
    for tx in queryset.filter(type=Transaction.TYPE_DEPOSIT,
                              status__in=[Transaction.STATUS_PENDING,
                                          Transaction.STATUS_PROCESSING]):
        with db_tx.atomic():
            from wallet.models import Wallet
            wallet = Wallet.objects.select_for_update().get(pk=tx.wallet_id)
            is_first = not wallet.has_completed_deposit
            wallet.usdt_balance = wallet.usdt_balance + (tx.amount_usdt or Decimal(0))
            # Match verify_deposit + manual deposit: credit H Coins too.
            wallet.h_coin_balance = wallet.h_coin_balance + (tx.amount_hcoin or Decimal(0))
            if is_first:
                wallet.has_completed_deposit = True
            wallet.save()
            tx.status = Transaction.STATUS_COMPLETED
            tx.save(update_fields=["status", "updated_at"])
            log_audit("deposit_complete", user=request.user, tx_id=str(tx.id),
                      forced=True, amount=str(tx.amount_usdt))
            n += 1
        if is_first:
            newly_qualified_users.append(tx.user)

    # After all commits, recheck milestones for each inviter whose
    # referral just became qualified.
    if newly_qualified_users:
        from referrals.services import on_deposit_completed
        for u in newly_qualified_users:
            try:
                on_deposit_completed(u)
            except Exception:
                pass

    messages.success(request, f"{n} deposit(s) force-completed.")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "status", "network",
                    "amount_usdt", "amount_hcoin", "tx_hash", "created_at")
    list_filter = ("status", "type", "network", "created_at")
    search_fields = ("user__email", "tx_hash", "id")
    readonly_fields = ("id", "created_at", "updated_at", "idempotency_key")
    actions = [approve_withdrawals, force_complete_deposit]
    ordering = ("-created_at",)
