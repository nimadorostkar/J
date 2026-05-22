# === FILE: backend/lucky_spin/views.py ===
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class LuckySpinRoot(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {"code": "COMING_SOON",
             "message": "Lucky Spin is coming soon."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    post = get
    put = get
    patch = get
    delete = get
