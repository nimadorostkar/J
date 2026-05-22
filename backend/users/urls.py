# === FILE: backend/users/urls.py ===
from django.urls import path

from .views import AvatarUploadView, MeView, PasswordChangeView, StatusView

urlpatterns = [
    path("me/", MeView.as_view(), name="users-me"),
    path("me/avatar/", AvatarUploadView.as_view(), name="users-me-avatar"),
    path("me/password/", PasswordChangeView.as_view(), name="users-me-password"),
    path("me/status/", StatusView.as_view(), name="users-me-status"),
]
