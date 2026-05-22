# === FILE: backend/reference/serializers.py ===
from rest_framework import serializers

from .models import Country, DialCode, PlatformConfig


class CountrySerializer(serializers.ModelSerializer):
    flagEmoji = serializers.CharField(source="flag_emoji")

    class Meta:
        model = Country
        fields = ("code", "name", "flagEmoji")


class DialCodeSerializer(serializers.ModelSerializer):
    country = serializers.CharField(source="country.code")
    countryName = serializers.CharField(source="country.name", read_only=True)
    flagEmoji = serializers.CharField(source="country.flag_emoji", read_only=True)

    class Meta:
        model = DialCode
        fields = ("country", "countryName", "flagEmoji", "code")


class PlatformConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformConfig
        fields = ("key", "value", "description")
