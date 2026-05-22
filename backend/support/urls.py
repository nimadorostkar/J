# === FILE: backend/support/urls.py ===
from django.urls import path

from .views import FAQListView, LiveChatSessionView, TicketDetailView, TicketListCreateView

urlpatterns = [
    path("faqs/", FAQListView.as_view(), name="support-faqs"),
    path("tickets/", TicketListCreateView.as_view(), name="support-tickets"),
    path("tickets/<int:pk>/", TicketDetailView.as_view(), name="support-ticket-detail"),
    path("chat/session/", LiveChatSessionView.as_view(), name="support-chat-session"),
]
