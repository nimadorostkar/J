# === FILE: backend/reference/urls.py ===
from django.urls import path

from .views import CountryListView, DialCodeListView, PlatformConfigView

urlpatterns = [
    path("countries/", CountryListView.as_view(), name="reference-countries"),
    path("dial-codes/", DialCodeListView.as_view(), name="reference-dial-codes"),
    path("config/", PlatformConfigView.as_view(), name="reference-config"),
]
