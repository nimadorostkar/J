# === FILE: backend/transactions/urls_webhooks.py ===
from django.urls import path

from .views import BlockchainWebhookView

urlpatterns = [
    path("blockchain/", BlockchainWebhookView.as_view(), name="webhook-blockchain"),
]
