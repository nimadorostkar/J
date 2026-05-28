# === FILE: backend/core/urls.py ===
"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="TokenVault API",
        default_version="v1",
        description="Gamified USDT / H Coin wallet platform — backend API.",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

api_v1 = [
    path("auth/", include("users.urls_auth")),
    path("users/", include("users.urls")),
    path("wallet/", include("wallet.urls")),
    path("payments/", include("payments.urls")),
    path("referrals/", include("referrals.urls")),
    path("reward/", include("rewards.urls")),
    path("notifications/", include("notifications.urls")),
    path("support/", include("support.urls")),
    path("reference/", include("reference.urls")),
    path("tournaments/", include("tournaments.urls")),
    path("lucky-spin/", include("lucky_spin.urls")),
    path("trade/", include("trade.urls")),
    path("health/", include("core.health_urls")),
    path("webhooks/", include("transactions.urls_webhooks")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/docs/", schema_view.with_ui("swagger", cache_timeout=0), name="swagger-ui"),
    path("api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="redoc"),
    path("api/schema.json", schema_view.without_ui(cache_timeout=0), name="schema-json"),
]

# Always serve user-uploaded media (avatars, etc.) from Django so the SPA
# can render them. `static()` is a no-op when DEBUG=False, so we wire the
# underlying serve view directly. In a real prod deployment you'd put this
# behind nginx or a CDN, but for local docker-compose this is fine.
_media_url = settings.MEDIA_URL.lstrip("/").rstrip("/")
urlpatterns += [
    re_path(
        rf"^{_media_url}/(?P<path>.*)$",
        static_serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
