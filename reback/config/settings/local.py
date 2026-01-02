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
# Ver ANTHROPIC_SETUP.md para instrucciones de configuración
# Si no está configurada, Django no iniciará (fail-fast)
try:
    ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
except Exception:
    import sys
    print("\n" + "="*80)
    print("⚠️  ERROR: ANTHROPIC_API_KEY no está configurada")
    print("="*80)
    print("\nPara configurarla:")
    print("1. Obtén tu API key en: https://console.anthropic.com/")
    print("2. En PowerShell, ejecuta:")
    print('   $env:ANTHROPIC_API_KEY = "sk-ant-api03-TU-KEY-AQUI"')
    print("3. Reinicia el servidor Django")
    print("\nO configúrala como variable de entorno permanente en Windows.")
    print("Ver documentación completa en: setup_api_key.md")
    print("="*80 + "\n")
    
    # En desarrollo, permitir continuar sin API key
    if 'runserver' in sys.argv or 'shell' in sys.argv:
        print("⚠️  Continuando en modo desarrollo SIN IA...")
        ANTHROPIC_API_KEY = None
    else:
        # En producción, fallar
        raise Exception("ANTHROPIC_API_KEY es requerida")

