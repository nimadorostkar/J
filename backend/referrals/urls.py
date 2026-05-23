# === FILE: backend/referrals/urls.py ===
from django.urls import path

from .views import (
    CodeView,
    MilestoneHistoryView,
    NetworkView,
    StatsView,
    ValidateInviteView,
)

urlpatterns = [
    path("code/", CodeView.as_view(), name="referrals-code"),
    path("network/", NetworkView.as_view(), name="referrals-network"),
    path("stats/", StatsView.as_view(), name="referrals-stats"),
    path("milestones/", MilestoneHistoryView.as_view(), name="referrals-milestones"),
    path("validate/", ValidateInviteView.as_view(), name="referrals-validate"),
]
