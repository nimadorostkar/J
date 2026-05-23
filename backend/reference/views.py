# === FILE: backend/reference/views.py ===
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Country, DialCode, PlatformConfig
from .serializers import CountrySerializer, DialCodeSerializer


class CountryListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(CountrySerializer(Country.objects.all(), many=True).data)


class DialCodeListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = DialCode.objects.select_related("country").all()
        return Response(DialCodeSerializer(qs, many=True).data)


class PlatformConfigView(APIView):
    """Public platform config (conversion rate, minimums, etc.)."""

    permission_classes = [AllowAny]

    def get(self, request):
        # Defaults sourced from environment (single source of truth)
        base = {
            "usdtPerHcoin": settings.USDT_PER_HCOIN,
            "minDepositUsdt": settings.MIN_DEPOSIT_USDT,
            "withdrawalFeeUsdt": settings.WITHDRAWAL_FEE_USDT,
            "rewardDurationHours": settings.REWARD_DURATION_HOURS,
            "rewardDurationDays": settings.REWARD_DURATION_DAYS,
            "rewardPercent": settings.REWARD_PERCENT,
            "rewardMinHcoin": settings.REWARD_MIN_HCOIN,
            "rewardAmountHcoin": settings.REWARD_AMOUNT_HCOIN,
            "referralCommission": {
                "l1Percent": settings.REFERRAL_L1_COMMISSION_PCT,
                "l2Percent": settings.REFERRAL_L2_COMMISSION_PCT,
            },
            "referralMilestone": {
                "size": settings.REFERRAL_MILESTONE_SIZE,
                "rewardHcoin": settings.REFERRAL_MILESTONE_REWARD_HCOIN,
            },
            "bots": {
                "basic": {
                    "feePercent": settings.BOT_BASIC_FEE_PCT,
                    "durationSeconds": settings.BOT_BASIC_DURATION_SECONDS,
                    "profitMinPercent": settings.BOT_BASIC_PROFIT_MIN_PCT,
                    "profitMaxPercent": settings.BOT_BASIC_PROFIT_MAX_PCT,
                },
                "expert": {
                    "feePercent": settings.BOT_EXPERT_FEE_PCT,
                    "durationSeconds": settings.BOT_EXPERT_DURATION_SECONDS,
                    "profitMinPercent": settings.BOT_EXPERT_PROFIT_MIN_PCT,
                    "profitMaxPercent": settings.BOT_EXPERT_PROFIT_MAX_PCT,
                },
            },
            "globalCycleDays": settings.GLOBAL_CYCLE_DAYS,
        }
        # Allow ops to override individual keys from DB
        for cfg in PlatformConfig.objects.all():
            base[cfg.key] = cfg.value
        return Response(base)
