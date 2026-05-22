# === FILE: backend/support/views.py ===
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FAQ, Ticket, TicketMessage
from .serializers import CreateTicketSerializer, FAQSerializer, TicketMessageSerializer, TicketSerializer


class FAQListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = FAQ.objects.filter(is_published=True).order_by("category", "order", "id")
        return Response(FAQSerializer(qs, many=True).data)


class TicketListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Ticket.objects.filter(user=request.user).prefetch_related("messages")
        return Response(TicketSerializer(qs, many=True).data)

    def post(self, request):
        ser = CreateTicketSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ticket = Ticket.objects.create(
            user=request.user,
            subject=ser.validated_data["subject"],
            category=ser.validated_data.get("category", ""),
        )
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            is_staff=False,
            body=ser.validated_data["body"],
        )
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class TicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        ticket = Ticket.objects.filter(user=request.user, pk=pk).prefetch_related("messages").first()
        if not ticket:
            return Response({"code": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)
        return Response(TicketSerializer(ticket).data)

    def post(self, request, pk):
        """Reply to a ticket."""
        ticket = Ticket.objects.filter(user=request.user, pk=pk).first()
        if not ticket:
            return Response({"code": "NOT_FOUND"}, status=status.HTTP_404_NOT_FOUND)
        body = request.data.get("body", "").strip()
        if not body:
            return Response({"code": "EMPTY_BODY"}, status=status.HTTP_400_BAD_REQUEST)
        msg = TicketMessage.objects.create(ticket=ticket, sender=request.user,
                                           is_staff=False, body=body)
        if ticket.status == Ticket.STATUS_RESOLVED:
            ticket.status = Ticket.STATUS_OPEN
            ticket.save(update_fields=["status"])
        return Response(TicketMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class LiveChatSessionView(APIView):
    """Stub — returns a session token suitable for a future live-chat provider."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({
            "sessionToken": f"chat-stub-{request.user.id}",
            "provider": "stub",
            "wsUrl": None,
        })
