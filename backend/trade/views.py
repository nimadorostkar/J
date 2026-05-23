# === FILE: backend/trade/views.py ===
"""Trade-bot HTTP endpoints."""
from django.conf import settings
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BotSession
from .serializers import ActivateBotSerializer, BotSessionSerializer
from .services import BotActivationError, activate_bot, bot_config


def _bot_config_payload():
    """Public-facing bot config dict consumed by the Trade page."""
    return {
        "basic": {
            "type": BotSession.BOT_BASIC,
            "label": "Basic Bot Trader",
            "feePercent": settings.BOT_BASIC_FEE_PCT,
            "durationSeconds": settings.BOT_BASIC_DURATION_SECONDS,
            "profitMinPercent": settings.BOT_BASIC_PROFIT_MIN_PCT,
            "profitMaxPercent": settings.BOT_BASIC_PROFIT_MAX_PCT,
        },
        "expert": {
            "type": BotSession.BOT_EXPERT,
            "label": "Expert Bot Trader",
            "feePercent": settings.BOT_EXPERT_FEE_PCT,
            "durationSeconds": settings.BOT_EXPERT_DURATION_SECONDS,
            "profitMinPercent": settings.BOT_EXPERT_PROFIT_MIN_PCT,
            "profitMaxPercent": settings.BOT_EXPERT_PROFIT_MAX_PCT,
        },
    }


class TradeRootView(APIView):
    """Single GET that gives the UI everything it needs in one round-trip."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        active = (
            BotSession.objects.filter(
                user=request.user, status=BotSession.STATUS_ACTIVE,
            )
            .order_by("-started_at")
            .first()
        )
        return Response({
            "bots": _bot_config_payload(),
            "active": BotSessionSerializer(active).data if active else None,
        })


class ActivateBotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ActivateBotSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        bot_type = ser.validated_data["botType"]
        try:
            session = activate_bot(request.user, bot_type)
        except BotActivationError as e:
            return Response(
                {"code": e.code, "message": e.message},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return Response(BotSessionSerializer(session).data,
                        status=http_status.HTTP_201_CREATED)


class BotSessionListView(APIView):
    """Paginated history of the user's bot sessions (most recent first)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.pagination import CursorPagination
        qs = BotSession.objects.filter(user=request.user).order_by("-started_at")
        paginator = CursorPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            BotSessionSerializer(page, many=True).data,
        )


class BotSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        s = BotSession.objects.filter(user=request.user, pk=pk).first()
        if not s:
            return Response({"code": "NOT_FOUND"}, status=http_status.HTTP_404_NOT_FOUND)
        return Response(BotSessionSerializer(s).data)
