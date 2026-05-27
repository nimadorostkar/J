# === FILE: backend/wallet/urls.py ===
from django.urls import path

from .views import (
    AdminManualDepositView,
    DepositAddressQRView,
    DepositAddressView,
    DepositInitView,
    DepositStatusView,
    NetworksView,
    TransactionsListView,
    WalletView,
    WithdrawEligibilityView,
    WithdrawInitView,
    WithdrawStatusView,
)

urlpatterns = [
    path("", WalletView.as_view(), name="wallet-detail"),
    path("transactions/", TransactionsListView.as_view(), name="wallet-transactions"),
    path("networks/", NetworksView.as_view(), name="wallet-networks"),
    path("deposit-address/", DepositAddressView.as_view(), name="wallet-deposit-address"),
    path("deposit-address/qr/", DepositAddressQRView.as_view(), name="wallet-deposit-qr"),
    path("deposit/", DepositInitView.as_view(), name="wallet-deposit"),
    path("deposit/<uuid:tx_id>/", DepositStatusView.as_view(), name="wallet-deposit-status"),
    path("withdraw/", WithdrawInitView.as_view(), name="wallet-withdraw"),
    path("withdraw/eligibility/", WithdrawEligibilityView.as_view(), name="wallet-withdraw-eligibility"),
    path("withdraw/<uuid:tx_id>/", WithdrawStatusView.as_view(), name="wallet-withdraw-status"),

    # Admin-only — caller must be authenticated AND `is_staff`.
    path(
        "admin/manual-deposit/",
        AdminManualDepositView.as_view(),
        name="wallet-admin-manual-deposit",
    ),
]
