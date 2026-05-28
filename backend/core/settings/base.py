# === FILE: backend/core/settings/base.py ===
"""Base Django settings for TokenVault."""
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Core
SECRET_KEY = config("SECRET_KEY", default="insecure-dev-secret-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "channels",
    "storages",
    "drf_yasg",
    "encrypted_model_fields",
    # Local apps
    "core.apps.CoreConfig",
    "users",
    "wallet",
    "transactions",
    "payments",
    "referrals",
    "rewards",
    "notifications",
    "support",
    "reference",
    "tournaments",
    "lucky_spin",
    "trade",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "db.sqlite3")),
        conn_max_age=600,
    )
}

# Auth
AUTH_USER_MODEL = "users.User"
AUTHENTICATION_BACKENDS = ["users.backends.EmailBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# I18N
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static / Media
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise — serve static files via Django/Gunicorn so admin CSS works
# on :8000 (bypassing nginx). If the package isn't installed yet (image
# hasn't been rebuilt with the new requirements.txt), gracefully fall back
# to Django's default storage so the container still boots.
try:
    import whitenoise  # noqa: F401
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
        "whitenoise.middleware.WhiteNoiseMiddleware",
    )
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
except Exception:
    # whitenoise not installed yet — admin CSS will only work via nginx.
    pass

# S3 storage
USE_S3 = config("USE_S3", default=False, cast=bool)
if USE_S3:
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="us-east-1")
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": "300/min",
        "anon": "60/min",
    },
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TTL_MINUTES", default=15, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("JWT_REFRESH_TTL_DAYS", default=7, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# CORS
CORS_ALLOWED_ORIGINS = config("ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())
CORS_ALLOW_CREDENTIALS = True
# Make sure media / static paths are CORS-enabled too so <img src> works
# when the SPA is hosted on a different origin than Django.
CORS_URLS_REGEX = r"^/(api|media|static)/.*$"

# Redis / Channels / Celery
REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_DEFAULT_RETRY_DELAY = 30
CELERY_TIMEZONE = TIME_ZONE
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CHANNEL_LAYERS_URL = config("CHANNEL_LAYERS_URL", default="redis://redis:6379/3")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [CHANNEL_LAYERS_URL]},
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Encrypted field key. Must be a 32-byte url-safe base64 Fernet key.
# Generate one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# An empty env value is treated as "unset" — we fall back to a dev key so
# `docker compose up` works out of the box. NEVER ship to prod without setting
# FIELD_ENCRYPTION_KEY to a freshly generated key.
_DEV_FERNET_KEY = "kBwy_DKvJjAfHRr3wnPHHfRz0wYwAtAVgmJxhJOyZc4="
FIELD_ENCRYPTION_KEY = config("FIELD_ENCRYPTION_KEY", default="") or _DEV_FERNET_KEY

# Economics
USDT_PER_HCOIN = config("USDT_PER_HCOIN", default=10, cast=int)
MIN_DEPOSIT_USDT = config("MIN_DEPOSIT_USDT", default=10, cast=int)
WITHDRAWAL_FEE_USDT = config("WITHDRAWAL_FEE_USDT", default=1, cast=int)
WITHDRAWAL_AUTO_APPROVE = config("WITHDRAWAL_AUTO_APPROVE", default=False, cast=bool)
REWARD_DURATION_HOURS = config("REWARD_DURATION_HOURS", default=12, cast=int)
REWARD_AMOUNT_HCOIN = config("REWARD_AMOUNT_HCOIN", default=5, cast=int)
GLOBAL_CYCLE_DAYS = config("GLOBAL_CYCLE_DAYS", default=30, cast=int)
# Fixed end date for the global "season" countdown shown on the Home tab.
# Format: YYYY-MM-DD (UTC). Leave blank to fall back to GLOBAL_CYCLE_DAYS
# rolling from "now".
GLOBAL_CYCLE_END_DATE = config("GLOBAL_CYCLE_END_DATE", default="2026-10-01")

# Per-user reward cycle: lasts REWARD_DURATION_DAYS, pays out REWARD_PERCENT
# of the user's H Coin balance at activation time (with REWARD_MIN_HCOIN as
# a floor so brand-new users still get something when they first activate).
REWARD_DURATION_DAYS = config("REWARD_DURATION_DAYS", default=15, cast=int)
REWARD_PERCENT = config("REWARD_PERCENT", default=20, cast=int)
REWARD_MIN_HCOIN = config("REWARD_MIN_HCOIN", default=1, cast=int)

REFERRAL_L1_COMMISSION_PCT = config("REFERRAL_L1_COMMISSION_PCT", default=5, cast=int)
REFERRAL_L2_COMMISSION_PCT = config("REFERRAL_L2_COMMISSION_PCT", default=3, cast=int)

# Per-endpoint throttle rates (DRF format: "N/period", e.g. "5/min", "100/hour").
# Tune up during dev when bulk-testing referral milestones, etc.
THROTTLE_REGISTER_RATE = config("THROTTLE_REGISTER_RATE", default="5/min")
THROTTLE_LOGIN_RATE = config("THROTTLE_LOGIN_RATE", default="10/min")
THROTTLE_FORGOT_PASSWORD_RATE = config("THROTTLE_FORGOT_PASSWORD_RATE", default="3/min")

# ─── Trade Bots ────────────────────────────────────────────────────────
# Two flavours: "basic" (24h, 3% fee, 2-4% profit) and "expert"
# (48h, 5% fee, 6-9% profit). Durations are seconds so they can be
# shortened in dev/test (e.g. BOT_BASIC_DURATION_SECONDS=60).
BOT_BASIC_FEE_PCT          = config("BOT_BASIC_FEE_PCT",          default=3,     cast=float)
BOT_BASIC_DURATION_SECONDS = config("BOT_BASIC_DURATION_SECONDS", default=86400, cast=int)
BOT_BASIC_PROFIT_MIN_PCT   = config("BOT_BASIC_PROFIT_MIN_PCT",   default=2,     cast=float)
BOT_BASIC_PROFIT_MAX_PCT   = config("BOT_BASIC_PROFIT_MAX_PCT",   default=4,     cast=float)

BOT_EXPERT_FEE_PCT          = config("BOT_EXPERT_FEE_PCT",          default=5,      cast=float)
BOT_EXPERT_DURATION_SECONDS = config("BOT_EXPERT_DURATION_SECONDS", default=172800, cast=int)
BOT_EXPERT_PROFIT_MIN_PCT   = config("BOT_EXPERT_PROFIT_MIN_PCT",   default=6,      cast=float)
BOT_EXPERT_PROFIT_MAX_PCT   = config("BOT_EXPERT_PROFIT_MAX_PCT",   default=9,      cast=float)

# Referral milestone rewards: every Nth successful L1 referral earns the
# inviter a flat coin payout. (5 referrals → 1 H Coin, 10 → 1 more, …)
REFERRAL_MILESTONE_SIZE = config("REFERRAL_MILESTONE_SIZE", default=5, cast=int)
REFERRAL_MILESTONE_REWARD_HCOIN = config(
    "REFERRAL_MILESTONE_REWARD_HCOIN", default=1, cast=int
)

# ─── Blockchain / Crypto Payment Gateway ────────────────────────────
# A "master hot wallet" is one address per network the platform owns.
# Inbound: customers send USDT to that address (DepositAddressView
# surfaces it). Outbound: the same private key signs withdrawals.
#
# All keys MUST be set via env in production — the defaults below let
# `docker compose up` start in dev mode with GATEWAY_DRY_RUN=True so no
# real chain calls happen until ops opts in.

# Master hot-wallet ADDRESSES (public — fine to commit per environment).
USDT_TRC20_WALLET = config("USDT_TRC20_WALLET", default="")
USDT_ERC20_WALLET = config("USDT_ERC20_WALLET", default="")

# Master hot-wallet PRIVATE KEYS (env-only — never commit).
# Tron: hex string without 0x prefix. Ethereum: hex string with or without 0x.
TRON_HOT_WALLET_PRIVATE_KEY = config("TRON_HOT_WALLET_PRIVATE_KEY", default="")
ETHEREUM_HOT_WALLET_PRIVATE_KEY = config("ETHEREUM_HOT_WALLET_PRIVATE_KEY", default="")

# Network selection: 'mainnet' | 'shasta' | 'nile' for Tron,
# 'mainnet' | 'sepolia' | 'goerli' for Ethereum.
TRON_NETWORK = config("TRON_NETWORK", default="mainnet")
ETHEREUM_NETWORK = config("ETHEREUM_NETWORK", default="mainnet")

# RPC / API endpoints.
TRON_FULLNODE_URL = config(
    "TRON_FULLNODE_URL",
    default="https://api.trongrid.io",
)
ETHEREUM_RPC_URL = config(
    "ETHEREUM_RPC_URL",
    default="https://eth-mainnet.public.blastapi.io",
)
TRON_API_KEY = config("TRON_API_KEY", default="")
ETHEREUM_API_KEY = config("ETHEREUM_API_KEY", default="")  # Etherscan, used for tx-listing.
ETHERSCAN_API_URL = config("ETHERSCAN_API_URL", default="https://api.etherscan.io/api")

# USDT contract addresses. Tron USDT is TRC20; Ethereum USDT is ERC20.
USDT_TRC20_CONTRACT = config(
    "USDT_TRC20_CONTRACT",
    default="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # mainnet USDT-TRC20
)
USDT_ERC20_CONTRACT = config(
    "USDT_ERC20_CONTRACT",
    default="0xdAC17F958D2ee523a2206206994597C13D831ec7",  # mainnet USDT-ERC20
)
USDT_DECIMALS_TRC20 = config("USDT_DECIMALS_TRC20", default=6, cast=int)
USDT_DECIMALS_ERC20 = config("USDT_DECIMALS_ERC20", default=6, cast=int)

# Confirmation thresholds before a deposit is credited.
MIN_CONFIRMATIONS_TRC20 = config("MIN_CONFIRMATIONS_TRC20", default=19, cast=int)
MIN_CONFIRMATIONS_ERC20 = config("MIN_CONFIRMATIONS_ERC20", default=12, cast=int)

# Withdrawal safety rails.
MIN_WITHDRAWAL_USDT = config("MIN_WITHDRAWAL_USDT", default=5, cast=int)
MAX_WITHDRAWAL_USDT = config("MAX_WITHDRAWAL_USDT", default=10000, cast=int)
DAILY_WITHDRAWAL_LIMIT_USDT = config(
    "DAILY_WITHDRAWAL_LIMIT_USDT", default=50000, cast=int
)
# Any withdrawal at or above this amount needs manual admin approval even
# if WITHDRAWAL_AUTO_APPROVE is on.
WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT = config(
    "WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT", default=1000, cast=int
)

# Scanner / poller knobs.
GATEWAY_SCAN_BATCH_SIZE = config("GATEWAY_SCAN_BATCH_SIZE", default=50, cast=int)
GATEWAY_RPC_TIMEOUT_SECONDS = config(
    "GATEWAY_RPC_TIMEOUT_SECONDS", default=15, cast=int
)

# Master kill-switch. When True, NO real on-chain calls are made:
# `verify_deposit` accepts any tx_hash, `process_withdrawal` simulates a
# transfer. Set to False in production. Defaults True so the project
# boots safely without leaking keys or burning gas.
GATEWAY_DRY_RUN = config("GATEWAY_DRY_RUN", default=True, cast=bool)

# Webhook HMAC secret (used by BlockchainWebhookView).
BLOCKCHAIN_WEBHOOK_SECRET = config("BLOCKCHAIN_WEBHOOK_SECRET", default="change-me")

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="no-reply@tokenvault.io")

FRONTEND_BASE_URL = config("FRONTEND_BASE_URL", default="http://localhost:3000")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "tokenvault": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
