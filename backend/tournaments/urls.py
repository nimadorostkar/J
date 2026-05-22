# === FILE: backend/tournaments/urls.py ===
from django.urls import path

from .views import TournamentsRoot

urlpatterns = [path("", TournamentsRoot.as_view(), name="tournaments-root")]
