# === FILE: backend/trade/urls.py ===
from django.urls import path

from .views import (
    ActivateBotView,
    BotSessionDetailView,
    BotSessionListView,
    TradeRootView,
)

urlpatterns = [
    path("", TradeRootView.as_view(), name="trade-root"),
    path("activate/", ActivateBotView.as_view(), name="trade-activate"),
    path("sessions/", BotSessionListView.as_view(), name="trade-sessions"),
    path("sessions/<uuid:pk>/", BotSessionDetailView.as_view(), name="trade-session-detail"),
]
