# === FILE: backend/rewards/urls.py ===
from django.urls import path

from .views import ActivateCycleView, ClaimCycleView, GlobalCycleView, RewardCycleView

urlpatterns = [
    path("cycle/", RewardCycleView.as_view(), name="reward-cycle"),
    path("cycle/activate/", ActivateCycleView.as_view(), name="reward-cycle-activate"),
    path("cycle/claim/", ClaimCycleView.as_view(), name="reward-cycle-claim"),
    path("global-cycle/", GlobalCycleView.as_view(), name="reward-global-cycle"),
]
