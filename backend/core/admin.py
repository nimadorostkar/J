# === FILE: backend/core/admin.py ===
from django.contrib import admin

from .audit import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "ip_address")
    list_filter = ("action", "created_at")
    search_fields = ("user__email", "action")
    readonly_fields = ("created_at", "user", "action", "meta", "ip_address")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
