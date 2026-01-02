# ruff: noqa: E501
from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="zOjAOi7FfFTLiX60dOORIZQziMlDM3rplUZzCYc5zhmjVpLTuvqYYkTfNedSlKUM",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]  # noqa: S104

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend",
)

# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
INSTALLED_APPS += ["debug_toolbar"]
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
        # Disable profiling panel due to an issue with Python 3.12:
        # https://github.com/jazzband/django-debug-toolbar/issues/1875
        "debug_toolbar.panels.profiling.ProfilingPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
}
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]


# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]

# Your stuff...
# ------------------------------------------------------------------------------

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "reback" / "static",  # para archivos globales (logo, vendors, etc.)
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Anthropic Claude API Configuration
# ------------------------------------------------------------------------------
# La API key DEBE configurarse como variable de entorno ANTHROPIC_API_KEY
# Ver setup_api_key.md para instrucciones de configuración
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")

# Mostrar warning si no está configurada (pero permitir continuar)
if not ANTHROPIC_API_KEY:
    import sys
    print("\n" + "="*80)
    print("WARNING: ANTHROPIC_API_KEY no esta configurada")
    print("="*80)
    print("\nLas recomendaciones de IA no estaran disponibles.")
    print("\nPara configurarla:")
    print("1. Obten tu API key en: https://console.anthropic.com/")
    print("2. En PowerShell, ejecuta:")
    print('   $env:ANTHROPIC_API_KEY = "sk-ant-api03-TU-KEY-AQUI"')
    print("3. Reinicia el servidor Django")
    print("\nVer documentacion completa en: setup_api_key.md")
    print("="*80 + "\n")

