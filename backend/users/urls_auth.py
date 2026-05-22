# === FILE: backend/users/urls_auth.py ===
from django.urls import path

from .views import (
    ForgotPasswordView,
    LoginView,
    LogoutView,
    RefreshTokenView,
    RegisterView,
    ResetPasswordView,
    VerifyEmailView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot"),
    path("reset-password/", ResetPasswordView.as_view(), name="auth-reset"),
    path("verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),
]
