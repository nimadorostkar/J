# === FILE: backend/tournaments/views.py ===
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class TournamentsRoot(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {"code": "COMING_SOON",
             "message": "Tournaments are coming soon."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    post = get
    put = get
    patch = get
    delete = get
