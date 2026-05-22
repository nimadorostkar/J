# === FILE: backend/lucky_spin/urls.py ===
from django.urls import path

from .views import LuckySpinRoot

urlpatterns = [path("", LuckySpinRoot.as_view(), name="lucky-spin-root")]
