# === FILE: backend/reference/models.py ===
"""Static reference data: countries, dial codes, platform config."""
from django.db import models


class Country(models.Model):
    code = models.CharField(max_length=2, primary_key=True, help_text="ISO 3166-1 alpha-2")
    name = models.CharField(max_length=120)
    flag_emoji = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Countries"

    def __str__(self):
        return f"{self.flag_emoji} {self.name}"


class DialCode(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="dial_codes")
    code = models.CharField(max_length=8, help_text="e.g. +98")

    class Meta:
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.country.code} {self.code}"


class PlatformConfig(models.Model):
    """Key/value store of platform-wide config tunables."""

    key = models.CharField(max_length=64, primary_key=True)
    value = models.JSONField()
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
