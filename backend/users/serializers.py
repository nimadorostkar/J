# === FILE: backend/users/serializers.py ===
"""Serializers for auth, profile, password, status."""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from referrals.models import Referral

User = get_user_model()

INVITE_CODE_RE = re.compile(r"^[A-Z0-9]{8}$", re.IGNORECASE)


class RegisterSerializer(serializers.Serializer):
    firstName = serializers.CharField(max_length=80, source="first_name")
    lastName = serializers.CharField(max_length=80, source="last_name")
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    inviteCode = serializers.CharField(max_length=8)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value.lower()

    def validate_inviteCode(self, value):
        value = (value or "").strip().upper()
        if not value or not INVITE_CODE_RE.match(value):
            raise serializers.ValidationError({
                "code": "INVALID_INVITE_CODE",
                "message": "Invite code must be 8 alphanumeric characters.",
            })
        if not User.objects.filter(referral_code=value).exists():
            raise serializers.ValidationError({
                "code": "INVALID_INVITE_CODE",
                "message": "Invite code not found.",
            })
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated):
        invite_code = validated.pop("inviteCode")
        password = validated.pop("password")
        inviter = User.objects.select_for_update().get(referral_code=invite_code)

        user = User(
            email=validated["email"],
            first_name=validated.get("first_name", ""),
            last_name=validated.get("last_name", ""),
            referred_by=inviter,
        )
        user.set_password(password)
        user.save()

        # Level 1 referral
        Referral.objects.create(inviter=inviter, invited_user=user, level=1)
        # Level 2 referral (if inviter was itself referred)
        if inviter.referred_by_id:
            Referral.objects.create(
                inviter=inviter.referred_by,
                invited_user=user,
                level=2,
            )

        # Mark inviter as having at least one referral (cached on Wallet)
        from wallet.models import Wallet
        Wallet.objects.filter(user=inviter).update(has_referral=True)
        if inviter.referred_by_id:
            Wallet.objects.filter(user=inviter.referred_by).update(has_referral=True)

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenPairSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    refreshToken = serializers.CharField()

    @classmethod
    def for_user(cls, user):
        refresh = RefreshToken.for_user(user)
        return {
            "accessToken": str(refresh.access_token),
            "refreshToken": str(refresh),
        }


class UserSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", required=False, allow_blank=True)
    lastName = serializers.CharField(source="last_name", required=False, allow_blank=True)
    countryCode = serializers.CharField(source="country_code", required=False, allow_blank=True)
    mobile = serializers.CharField(source="phone", required=False, allow_blank=True)
    avatarUrl = serializers.SerializerMethodField()
    referralCode = serializers.CharField(source="referral_code", read_only=True)
    isEmailVerified = serializers.BooleanField(source="is_email_verified", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "email", "firstName", "lastName", "mobile",
            "countryCode", "country", "avatarUrl",
            "referralCode", "isEmailVerified", "createdAt",
        )
        read_only_fields = ("id", "email", "avatarUrl", "referralCode", "isEmailVerified", "createdAt")

    def get_avatarUrl(self, obj):
        try:
            return obj.avatar.url if obj.avatar else None
        except Exception:
            return None


class AvatarUploadSerializer(serializers.Serializer):
    avatar = serializers.FileField()


class PasswordChangeSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(write_only=True)
    newPassword = serializers.CharField(write_only=True)

    def validate_newPassword(self, value):
        validate_password(value)
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    newPassword = serializers.CharField(write_only=True)

    def validate_newPassword(self, value):
        validate_password(value)
        return value


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()
