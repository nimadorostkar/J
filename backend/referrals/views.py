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

from .models import Referral, ReferralMilestoneReward
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
        # with_status_flags adds _has_deposit + _is_verified annotations,
        # avoiding N+1 queries when the serializer renders status badges.
        l1 = (
            Referral.objects.filter(inviter=request.user, level=1)
            .with_status_flags()
            .select_related("invited_user")
        )
        l2 = (
            Referral.objects.filter(inviter=request.user, level=2)
            .with_status_flags()
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

        # === Milestone progress ===
        # Milestones are now driven by QUALIFIED referrals only — L1
        # signups whose invited user has completed at least one deposit.
        # Raw signups (l1Count) are kept in the response for context.
        size = max(1, int(settings.REFERRAL_MILESTONE_SIZE or 1))
        reward = Decimal(settings.REFERRAL_MILESTONE_REWARD_HCOIN or 0)
        l1_count = l1_qs.count()
        qualified_count = Referral.objects.qualified_for(request.user).count()
        pending_count = max(0, l1_count - qualified_count)  # signed up but no deposit yet

        milestones_qs = ReferralMilestoneReward.objects.filter(user=request.user)
        milestones_paid = milestones_qs.count()
        total_milestone_paid = (
            milestones_qs.aggregate(s=Sum("amount_hcoin"))["s"] or Decimal(0)
        )

        # Next milestone is computed against the QUALIFIED count so the
        # progress bar advances only when invited users actually deposit.
        next_milestone = ((qualified_count // size) + 1) * size
        toward_next = qualified_count - (next_milestone - size)  # 0..size-1
        progress_pct = round((toward_next / size) * 100, 2)

        return Response({
            "l1Count": l1_count,
            "l2Count": l2_qs.count(),
            "qualifiedCount": qualified_count,
            "pendingDepositCount": pending_count,
            "totalCommissionEarnedHcoin": str(total),
            # Milestone block ────────────────────────────────────
            "milestone": {
                "size": size,
                "rewardHcoin": str(reward),
                "milestonesPaid": milestones_paid,
                "totalRewardEarnedHcoin": str(total_milestone_paid),
                "nextMilestoneAt": next_milestone,
                "qualifiedCount": qualified_count,
                "qualifiedUntilNext": max(0, next_milestone - qualified_count),
                # Kept for backwards-compat with the existing UI key,
                # but it's now the qualified count, not raw.
                "referralsUntilNext": max(0, next_milestone - qualified_count),
                "progressPercent": progress_pct,
                "qualifyingRule": (
                    "Only invited users with at least one completed deposit "
                    "count toward milestone rewards."
                ),
            },
        })


class MilestoneHistoryView(APIView):
    """List the milestone rewards this user has earned (for audit / UI)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = ReferralMilestoneReward.objects.filter(user=request.user)
        data = [
            {
                "id": r.id,
                "milestone": r.milestone,
                "amountHcoin": str(r.amount_hcoin),
                "transactionId": str(r.transaction_id) if r.transaction_id else None,
                "awardedAt": r.awarded_at,
            }
            for r in rows
        ]
        return Response(data)


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
