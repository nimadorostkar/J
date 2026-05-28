# === FILE: backend/payments/admin.py ===
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect

from .models import GatewayCursor, GatewayEventLog
from .tasks import (
    poll_pending_deposits,
    poll_pending_withdrawals,
    scan_master_wallet,
)


@admin.register(GatewayCursor)
class GatewayCursorAdmin(admin.ModelAdmin):
    list_display = ("network", "last_block", "last_tx_hash", "last_scanned_at", "error_count")
    readonly_fields = ("last_scanned_at", "updated_at", "error_count", "last_error")
    actions = ["rescan_now"]

    @admin.action(description="Scan now (queue Celery task)")
    def rescan_now(self, request, queryset):
        for cur in queryset:
            scan_master_wallet.delay(cur.network)
        self.message_user(
            request, f"Queued scan for {queryset.count()} network(s).", level=messages.SUCCESS
        )

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "tools/scan-now/",
                self.admin_site.admin_view(self._scan_now_view),
                name="payments_scan_now",
            ),
            path(
                "tools/poll-deposits/",
                self.admin_site.admin_view(self._poll_deposits_view),
                name="payments_poll_deposits",
            ),
            path(
                "tools/poll-withdrawals/",
                self.admin_site.admin_view(self._poll_withdrawals_view),
                name="payments_poll_withdrawals",
            ),
        ]
        return extra + urls

    def _scan_now_view(self, request):
        scan_master_wallet.delay(None)
        messages.success(request, "Master wallet scan queued.")
        return redirect("admin:payments_gatewaycursor_changelist")

    def _poll_deposits_view(self, request):
        poll_pending_deposits.delay()
        messages.success(request, "Pending-deposit confirmation poll queued.")
        return redirect("admin:payments_gatewaycursor_changelist")

    def _poll_withdrawals_view(self, request):
        poll_pending_withdrawals.delay()
        messages.success(request, "Pending-withdrawal confirmation poll queued.")
        return redirect("admin:payments_gatewaycursor_changelist")


@admin.register(GatewayEventLog)
class GatewayEventLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "network", "tx_hash", "from_address", "to_address",
        "amount_usdt", "confirmations_at_ingest", "matched_user_id",
        "matched_transaction_id",
    )
    list_filter = ("network",)
    search_fields = ("tx_hash", "from_address", "to_address", "matched_user_id")
    readonly_fields = tuple(f.name for f in GatewayEventLog._meta.fields)
