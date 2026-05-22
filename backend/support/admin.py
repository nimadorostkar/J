# === FILE: backend/support/admin.py ===
from django.contrib import admin

from .models import FAQ, Ticket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ("sender", "is_staff", "created_at")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "order", "is_published", "updated_at")
    list_filter = ("category", "is_published")
    search_fields = ("question", "answer")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "subject", "status", "category", "created_at")
    list_filter = ("status", "category")
    search_fields = ("user__email", "subject")
    inlines = [TicketMessageInline]


admin.site.register(TicketMessage)
