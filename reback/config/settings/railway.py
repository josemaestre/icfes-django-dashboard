# ruff: noqa: E501
"""
Production settings for Railway deployment.
Simplified version without AWS S3, using whitenoise for static files.
"""
import os

import dj_database_url
from whitenoise.storage import CompressedManifestStaticFilesStorage
from .base import *  # noqa: F403
from .base import env


class CompressedManifestStaticFilesStorageNoStrict(CompressedManifestStaticFilesStorage):
    """WhiteNoise storage that ignores missing sourcemap files referenced in vendor JS."""
    manifest_strict = False

# Error log directory
ERROR_LOG_DIR = env("ERROR_LOG_DIR", default="/app/logs")
os.makedirs(ERROR_LOG_DIR, exist_ok=True)

# GENERAL
# ------------------------------------------------------------------------------
DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=[".railway.app", "localhost", "icfes-analytics.com", "www.icfes-analytics.com"],
)

# MIDDLEWARE - Add auto-create admin middleware
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    # Normalize double slashes before anything else
    "reback.middleware.slash_normalize.SlashNormalizeMiddleware",
    # Compress responses (cost optimization)
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # Required by allauth
    "reback.users.middleware.AutoCreateAdminMiddleware",  # Auto-create admin
    "reback.middleware.error_logging.ErrorLoggingMiddleware",  # Log 4xx/5xx errors
]

# DATABASES
# ------------------------------------------------------------------------------
# Parse database URL from Railway
DATABASES["default"] = dj_database_url.config(
    default=env("DATABASE_URL"),
    conn_max_age=600,
    conn_health_checks=True,
)

# DuckDB path for Railway (using volume)
DATABASES["duckdb"] = {
    "ENGINE": "django_duckdb",
    "NAME": env("DUCKDB_PATH", default="/app/data/dev.duckdb"),
    "OPTIONS": {
        "read_only": True,
    }
}

# CACHES
# ------------------------------------------------------------------------------
# Use Redis for caching in production
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,  # Don't crash if Redis is down
        },
        "KEY_PREFIX": "icfes",
        "TIMEOUT": 60 * 15,  # 15 minutes default
    }
}

# SECURITY
# ------------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=True,
)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = env.bool(
    "DJANGO_SECURE_CONTENT_TYPE_NOSNIFF",
    default=True,
)

# STATIC FILES (whitenoise)
# ------------------------------------------------------------------------------
STATICFILES_STORAGE = "config.settings.railway.CompressedManifestStaticFilesStorageNoStrict"  # noqa: F405
STATIC_ROOT = str(BASE_DIR / "staticfiles")  # noqa: F405
STATIC_URL = "/static/"

# WhiteNoise optimization (cost reduction)
WHITENOISE_MAX_AGE = 31536000  # 1 year cache for hashed files
WHITENOISE_COMPRESS_OFFLINE = True  # Pre-compress gzip/brotli at collectstatic

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_ROOT = str(BASE_DIR / "media")  # noqa: F405
MEDIA_URL = "/media/"

# EMAIL
# ------------------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="ICFES Analytics <icfes@sabededatos.com>",
)
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = env(
    "DJANGO_EMAIL_SUBJECT_PREFIX",
    default="[ICFES Analytics] ",
)
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="mail.sabededatos.com")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=465)
EMAIL_USE_SSL = env.bool("DJANGO_EMAIL_USE_SSL", default=True)
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=False)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="icfes@sabededatos.com")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")

# ADMIN
# ------------------------------------------------------------------------------
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")

# LOGGING
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
        "error_detail": {
            "format": "%(asctime)s | %(levelname)s | %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "error_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(ERROR_LOG_DIR, "http_errors.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "error_detail",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": True,
        },
        "http_errors": {
            "handlers": ["console", "error_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# DuckDB Configuration
# ------------------------------------------------------------------------------
# Use S3 path if DUCKDB_S3_PATH is set, otherwise use local path (for dev)
ICFES_DUCKDB_PATH = env("DUCKDB_S3_PATH", default=env(
    "DUCKDB_PATH", default="/app/data/dev.duckdb"))
# ------------------------------------------------------------------------------

print("BOOT railway settings loaded", __file__)
