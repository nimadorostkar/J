# === FILE: backend/users/views.py ===
"""Auth, profile, password, status endpoints."""
import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.audit import log_audit

from .models import EmailVerificationToken, PasswordResetToken
from .serializers import (
    AvatarUploadSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    TokenPairSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)

logger = logging.getLogger("tokenvault")
User = get_user_model()


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class RegisterThrottle(AnonRateThrottle):
    rate = "5/min"


class LoginThrottle(AnonRateThrottle):
    rate = "10/min"


class ForgotPasswordThrottle(AnonRateThrottle):
    rate = "3/min"


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
        log_audit("registration", user=user, ip=_client_ip(request),
                  inviter=user.referred_by_id and str(user.referred_by_id))

        # send verification email
        tok = EmailVerificationToken.objects.create(user=user)
        verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={tok.token}"
        try:
            send_mail(
                subject="Verify your TokenVault email",
                message=f"Welcome to TokenVault!\n\nVerify your email: {verify_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Failed to send verification email")

        tokens = TokenPairSerializer.for_user(user)
        return Response(
            {"user": UserSerializer(user).data, **tokens},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(request,
                            username=ser.validated_data["email"],
                            password=ser.validated_data["password"])
        if not user:
            return Response(
                {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user.last_login = timezone.now()
        user.last_login_ip = _client_ip(request)
        user.save(update_fields=["last_login", "last_login_ip"])
        log_audit("login", user=user, ip=_client_ip(request))
        tokens = TokenPairSerializer.for_user(user)
        return Response({"user": UserSerializer(user).data, **tokens})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("refreshToken") or request.data.get("refresh")
        try:
            if token:
                RefreshToken(token).blacklist()
        except TokenError:
            pass
        return Response({"detail": "Logged out."})


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("refreshToken") or request.data.get("refresh")
        if not token:
            return Response(
                {"code": "MISSING_REFRESH_TOKEN", "message": "refreshToken is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = RefreshToken(token)
            access = str(refresh.access_token)
            # rotate: blacklist old, return new pair
            try:
                refresh.blacklist()
            except Exception:
                pass
            user_id = refresh["user_id"]
            user = User.objects.get(pk=user_id)
            new_refresh = RefreshToken.for_user(user)
            return Response({
                "accessToken": access,
                "refreshToken": str(new_refresh),
            })
        except TokenError as e:
            return Response(
                {"code": "INVALID_REFRESH_TOKEN", "message": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ForgotPasswordThrottle]

    def post(self, request):
        ser = ForgotPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            tok = PasswordResetToken.objects.create(user=user)
            reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={tok.token}"
            try:
                send_mail(
                    subject="Reset your TokenVault password",
                    message=f"Click to reset: {reset_url}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                logger.exception("Failed to send reset email")
        # Always 200 so we don't leak account existence
        return Response({"detail": "If that email exists, a reset link was sent."})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = ResetPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tok = PasswordResetToken.objects.filter(
            token=ser.validated_data["token"], consumed_at__isnull=True
        ).first()
        if not tok:
            return Response(
                {"code": "INVALID_TOKEN", "message": "Reset token invalid or already used."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (timezone.now() - tok.created_at).total_seconds() > 60 * 60:
            return Response(
                {"code": "EXPIRED_TOKEN", "message": "Reset token expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = tok.user
        user.set_password(ser.validated_data["newPassword"])
        user.save(update_fields=["password"])
        tok.consumed_at = timezone.now()
        tok.save(update_fields=["consumed_at"])
        log_audit("password_change", user=user, ip=_client_ip(request))
        return Response({"detail": "Password reset successful."})


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = VerifyEmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tok = EmailVerificationToken.objects.filter(
            token=ser.validated_data["token"], consumed_at__isnull=True
        ).first()
        if not tok:
            return Response(
                {"code": "INVALID_TOKEN", "message": "Verification token invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tok.user.is_email_verified = True
        tok.user.save(update_fields=["is_email_verified"])
        tok.consumed_at = timezone.now()
        tok.save(update_fields=["consumed_at"])
        return Response({"detail": "Email verified."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = UserSerializer(request.user).data
        from wallet.models import Wallet
        wallet = Wallet.objects.filter(user=request.user).first()
        data["status"] = {
            "hasDeposit": bool(wallet and wallet.has_completed_deposit),
            "hasReferral": bool(wallet and wallet.has_referral),
        }
        return Response(data)

    def patch(self, request):
        ser = UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class AvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        ser = AvatarUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        request.user.avatar = ser.validated_data["avatar"]
        request.user.save(update_fields=["avatar"])
        return Response({"avatarUrl": request.user.avatar.url})


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PasswordChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not request.user.check_password(ser.validated_data["currentPassword"]):
            return Response(
                {"code": "INVALID_PASSWORD", "message": "Current password incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(ser.validated_data["newPassword"])
        request.user.save(update_fields=["password"])
        log_audit("password_change", user=request.user, ip=_client_ip(request))
        return Response({"detail": "Password updated."})


class StatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from wallet.models import Wallet
        wallet = Wallet.objects.filter(user=request.user).first()
        return Response({
            "hasDeposit": bool(wallet and wallet.has_completed_deposit),
            "hasReferral": bool(wallet and wallet.has_referral),
        })
