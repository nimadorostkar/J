# === FILE: backend/notifications/urls.py ===
from django.urls import path

from .views import MarkAllReadView, MarkReadView, NotificationListView, UnreadCountView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications-list"),
    path("unread-count/", UnreadCountView.as_view(), name="notifications-unread-count"),
    path("<int:pk>/read/", MarkReadView.as_view(), name="notifications-mark-read"),
    path("read-all/", MarkAllReadView.as_view(), name="notifications-read-all"),
]
