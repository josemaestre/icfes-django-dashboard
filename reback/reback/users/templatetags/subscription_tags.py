"""
Template tags for subscription-based feature access control.

Tier hierarchy: free (0) < pro (1) < institutional (2)

Usage in templates:
    {% load subscription_tags %}

    {% has_plan 'pro' as has_pro %}
    {% if has_pro %}
        <!-- Show pro features -->
    {% endif %}

    {% has_plan 'institutional' as has_institutional %}
    {% if has_institutional %}
        <!-- Show institutional features -->
    {% endif %}
"""
from django import template

register = template.Library()


# ── Canonical tier order ───────────────────────────────────────────────────────
_TIER_ORDER = {
    'free':          0,
    'pro':           1,
    'institutional': 2,
    # Legacy aliases (backward-compat)
    'basic':         1,
    'premium':       1,
    'enterprise':    2,
}

_TIER_DISPLAY = {
    'free':          'Freemium',
    'pro':           'Pro Estratégico',
    'institutional': 'Institucional',
    'basic':         'Pro Estratégico',
    'premium':       'Pro Estratégico',
    'enterprise':    'Institucional',
}

_BADGE_CONFIG = {
    'free':          {'class': 'bg-secondary-subtle text-secondary', 'label': 'Gratis'},
    'pro':           {'class': 'bg-primary-subtle text-primary',     'label': 'Pro'},
    'institutional': {'class': 'bg-success-subtle text-success',     'label': 'Institucional'},
    # Legacy aliases
    'basic':         {'class': 'bg-primary-subtle text-primary',     'label': 'Pro'},
    'premium':       {'class': 'bg-primary-subtle text-primary',     'label': 'Pro'},
    'enterprise':    {'class': 'bg-success-subtle text-success',     'label': 'Institucional'},
}

# Feature → minimum tier required
_FEATURE_REQUIREMENTS = {
    # ── FREE ──────────────────────────────────────────────────────
    'national_view':        'free',
    'basic_search':         'free',
    'national_charts':      'free',
    'top10_colegios':       'free',
    'tendencias_basicas':   'free',

    # ── PRO ───────────────────────────────────────────────────────
    'department_analysis':  'pro',
    'municipality_analysis':'pro',
    'school_details':       'pro',
    'school_comparison':    'pro',
    'clustering':           'pro',
    'mapa_geografico':      'pro',
    'explorador_jerarquico':'pro',
    'export_csv':           'pro',
    'export_excel':         'pro',
    'historico_completo':   'pro',
    'brecha_educativa':     'pro',
    'resumen_ejecutivo':    'pro',
    'ingles_avanzado':      'pro',
    'historia_avanzada':    'pro',
    'inteligencia_educativa':'pro',
    'social_dashboard':     'pro',
    'mi_colegio':           'pro',

    # ── INSTITUCIONAL ─────────────────────────────────────────────
    'motivacional':         'institutional',
    'ml_ia':                'institutional',
    'trafico':              'institutional',
    'export_pdf':           'institutional',
    'api_access':           'institutional',
    'multi_user':           'institutional',
    'riesgo_ml_detallado':  'institutional',
}


def _get_user_tier(request) -> str:
    """Return the active tier string for the current user."""
    if not request:
        return 'free'
    user = request.user
    if not user.is_authenticated:
        return 'free'
    if user.is_superuser:
        return 'institutional'  # superusers have full access

    subscription = getattr(user, 'subscription', None)
    if not subscription or not subscription.is_active:
        return 'free'

    plan = getattr(subscription, 'plan', None)
    return plan.tier if plan else 'free'


@register.simple_tag(takes_context=True)
def has_plan(context, tier):
    """
    Check if the current user has the specified plan tier or higher.

    Args:
        tier: 'free', 'pro', or 'institutional'
              Legacy values 'basic', 'premium', 'enterprise' also accepted.

    Returns:
        bool: True if user has the tier or higher.

    Example::

        {% has_plan 'pro' as has_pro %}
        {% if has_pro %}
            <p>You have Pro plan or higher</p>
        {% endif %}
    """
    user_tier = _get_user_tier(context.get('request'))
    user_level = _TIER_ORDER.get(user_tier, 0)
    required_level = _TIER_ORDER.get(tier, 0)
    return user_level >= required_level


@register.filter
def can_access_feature(user, feature):
    """
    Check if a user can access a specific feature.

    Example::

        {% if user|can_access_feature:"mapa_geografico" %}
            <button>Ver Mapa</button>
        {% endif %}
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    subscription = getattr(user, 'subscription', None)
    user_tier = 'free'
    if subscription and subscription.is_active:
        plan = getattr(subscription, 'plan', None)
        user_tier = plan.tier if plan else 'free'

    required_tier = _FEATURE_REQUIREMENTS.get(feature, 'free')
    return _TIER_ORDER.get(user_tier, 0) >= _TIER_ORDER.get(required_tier, 0)


@register.simple_tag
def get_plan_badge(tier):
    """
    Return an HTML badge element for a plan tier.

    Example::

        {% get_plan_badge 'pro' %}
        <!-- Returns: <span class="badge bg-primary-subtle text-primary">Pro</span> -->
    """
    config = _BADGE_CONFIG.get(tier, _BADGE_CONFIG['free'])
    return f'<span class="badge {config["class"]}">{config["label"]}</span>'


@register.simple_tag(takes_context=True)
def get_user_plan(context):
    """
    Return the current user's canonical plan tier string.

    Example::

        {% get_user_plan as user_plan %}
        <p>Your plan: {{ user_plan }}</p>
    """
    return _get_user_tier(context.get('request'))


@register.simple_tag
def get_required_plan(feature):
    """
    Return the minimum required tier for a feature.

    Example::

        {% get_required_plan 'mapa_geografico' as required %}
        <!-- required = 'pro' -->
    """
    return _FEATURE_REQUIREMENTS.get(feature, 'free')


@register.simple_tag
def tier_display_name(tier):
    """Return the human-readable display name for a tier."""
    return _TIER_DISPLAY.get(tier, tier.capitalize())
