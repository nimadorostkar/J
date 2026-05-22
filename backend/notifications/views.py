# === FILE: backend/notifications/views.py ===
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import CursorPagination

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user).order_by("-created_at")
        paginator = CursorPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(NotificationSerializer(page, many=True).data)


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        n = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread": n})


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        obj = Notification.objects.filter(user=request.user, pk=pk).first()
        if not obj:
            return Response({"code": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)
        if not obj.is_read:
            obj.is_read = True
            obj.save(update_fields=["is_read"])
        return Response(NotificationSerializer(obj).data)


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "All marked read."})
