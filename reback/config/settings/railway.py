# ruff: noqa: E501
"""
Production settings for Railway deployment.
Simplified version without AWS S3, using whitenoise for static files.
"""
import dj_database_url
from .base import *  # noqa: F403
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# TEMPORARY: DEBUG=True to serve static files directly
# TODO: Fix static files deployment and set back to False
DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=[".railway.app", "localhost", "icfes-analytics.com", "www.icfes-analytics.com"],
)

# MIDDLEWARE - Add auto-create admin middleware
# ------------------------------------------------------------------------------
MIDDLEWARE = [
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
# Use simple cache for Railway (no Redis required initially)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
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
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
# Override Django default to avoid manifest storage
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
STATIC_ROOT = str(BASE_DIR / "staticfiles")  # noqa: F405
STATIC_URL = "/static/"

# WhiteNoise optimization (cost reduction)
WHITENOISE_MAX_AGE = 31536000  # 1 year cache
WHITENOISE_COMPRESS_OFFLINE = True  # Pre-compress files

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_ROOT = str(BASE_DIR / "media")  # noqa: F405
MEDIA_URL = "/media/"

# EMAIL
# ------------------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="ICFES Analytics <noreply@icfes-analytics.railway.app>",
)
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = env(
    "DJANGO_EMAIL_SUBJECT_PREFIX",
    default="[ICFES Analytics] ",
)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

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
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
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
    },
}

# DuckDB Configuration
# ------------------------------------------------------------------------------
# Use S3 path if DUCKDB_S3_PATH is set, otherwise use local path (for dev)
ICFES_DUCKDB_PATH = env("DUCKDB_S3_PATH", default=env(
    "DUCKDB_PATH", default="/app/data/dev.duckdb"))
# ------------------------------------------------------------------------------

print("BOOT railway settings loaded", __file__)
