# === FILE: backend/reference/admin.py ===
from django.contrib import admin

from .models import Country, DialCode, PlatformConfig


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "flag_emoji")
    search_fields = ("code", "name")


@admin.register(DialCode)
class DialCodeAdmin(admin.ModelAdmin):
    list_display = ("country", "code")
    search_fields = ("country__name", "country__code", "code")


@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description", "updated_at")
    search_fields = ("key", "description")
