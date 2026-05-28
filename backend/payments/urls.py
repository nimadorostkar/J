# === FILE: backend/payments/urls.py ===
from django.urls import path

from .views import (
    ApproveWithdrawalView,
    GatewayStatusView,
    PendingWithdrawalsView,
    RejectWithdrawalView,
)

urlpatterns = [
    path(
        "admin/withdrawals/pending/",
        PendingWithdrawalsView.as_view(),
        name="payments-admin-pending-withdrawals",
    ),
    path(
        "admin/withdrawals/<uuid:tx_id>/approve/",
        ApproveWithdrawalView.as_view(),
        name="payments-admin-approve-withdrawal",
    ),
    path(
        "admin/withdrawals/<uuid:tx_id>/reject/",
        RejectWithdrawalView.as_view(),
        name="payments-admin-reject-withdrawal",
    ),
    path(
        "admin/gateway/status/",
        GatewayStatusView.as_view(),
        name="payments-admin-gateway-status",
    ),
]
