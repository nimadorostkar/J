# === FILE: backend/referrals/views.py ===
"""Referral endpoints — code, network graph, stats, validation."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import Referral
from .serializers import ReferralRowSerializer, ValidateInviteSerializer

User = get_user_model()


class CodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.user.referral_code
        share_url = f"{settings.FRONTEND_BASE_URL}/register?code={code}"
        return Response({"code": code, "shareUrl": share_url})


class NetworkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        l1 = (
            Referral.objects.filter(inviter=request.user, level=1)
            .select_related("invited_user")
        )
        l2 = (
            Referral.objects.filter(inviter=request.user, level=2)
            .select_related("invited_user")
        )
        return Response({
            "level1": ReferralRowSerializer(l1, many=True).data,
            "level2": ReferralRowSerializer(l2, many=True).data,
        })


class StatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        l1_qs = Referral.objects.filter(inviter=request.user, level=1)
        l2_qs = Referral.objects.filter(inviter=request.user, level=2)
        total = (
            l1_qs.aggregate(s=Sum("total_commission_earned_hcoin"))["s"] or Decimal(0)
        ) + (
            l2_qs.aggregate(s=Sum("total_commission_earned_hcoin"))["s"] or Decimal(0)
        )
        return Response({
            "l1Count": l1_qs.count(),
            "l2Count": l2_qs.count(),
            "totalCommissionEarnedHcoin": str(total),
        })


class ValidateInviteThrottle(AnonRateThrottle):
    rate = "20/min"


class ValidateInviteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ValidateInviteThrottle]

    def post(self, request):
        ser = ValidateInviteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code = ser.validated_data["code"].strip().upper()
        u = User.objects.filter(referral_code=code).first()
        if not u:
            return Response({"valid": False})
        return Response({
            "valid": True,
            "inviterName": (u.first_name or u.email.split("@")[0]),
        })
