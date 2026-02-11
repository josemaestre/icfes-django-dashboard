"""
Template tags for subscription-based feature access control.

Usage in templates:
    {% load subscription_tags %}
    
    {% has_plan 'basic' as has_basic %}
    {% if has_basic %}
        <!-- Show basic features -->
    {% endif %}
    
    {% if user|can_access_feature:"school_comparison" %}
        <!-- Show comparison feature -->
    {% endif %}
"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def has_plan(context, tier):
    """
    Check if user has specific plan tier or higher.
    
    Args:
        context: Template context
        tier: Plan tier to check ('free', 'basic', 'premium', 'enterprise')
    
    Returns:
        bool: True if user has the tier or higher
    
    Example:
        {% has_plan 'basic' as has_basic %}
        {% if has_basic %}
            <p>You have Basic plan or higher</p>
        {% endif %}
    """
    request = context.get('request')
    if not request:
        return False
    
    user = request.user
    if not user.is_authenticated:
        return False
    
    # Superusers have access to everything
    if user.is_superuser:
        return True
    
    # Check if user has subscription
    if not hasattr(user, 'subscription') or not user.subscription:
        # No subscription = free tier
        return tier == 'free'
    
    # Check if subscription is active
    if not user.subscription.is_active:
        return tier == 'free'
    
    # Define tier hierarchy
    tier_order = {
        'free': 0,
        'basic': 1,
        'premium': 2,
        'enterprise': 3
    }
    
    user_tier = user.subscription.plan.tier if user.subscription.plan else 'free'
    user_tier_level = tier_order.get(user_tier, 0)
    required_tier_level = tier_order.get(tier, 0)
    
    return user_tier_level >= required_tier_level


@register.filter
def can_access_feature(user, feature):
    """
    Check if user can access a specific feature based on their plan.
    
    Args:
        user: User object
        feature: Feature name (string)
    
    Returns:
        bool: True if user can access the feature
    
    Example:
        {% if user|can_access_feature:"school_comparison" %}
            <button>Compare Schools</button>
        {% endif %}
    """
    if not user.is_authenticated:
        return False
    
    # Superusers have access to everything
    if user.is_superuser:
        return True
    
    # Define feature requirements
    feature_requirements = {
        # Free features
        'national_view': 'free',
        'basic_search': 'free',
        'national_charts': 'free',
        
        # Basic plan features
        'department_analysis': 'basic',
        'municipality_analysis': 'basic',
        'school_details': 'basic',
        'export_csv': 'basic',
        'unlimited_search': 'basic',
        
        # Premium plan features
        'school_comparison': 'premium',
        'custom_rankings': 'premium',
        'clustering': 'premium',
        'export_excel': 'premium',
        'export_pdf': 'premium',
        'advanced_analytics': 'premium',
        
        # Enterprise plan features
        'api_access': 'enterprise',
        'custom_dashboards': 'enterprise',
        'dedicated_support': 'enterprise',
        'real_time_data': 'enterprise',
    }
    
    required_tier = feature_requirements.get(feature, 'free')
    
    # Check if user has subscription
    if not hasattr(user, 'subscription') or not user.subscription:
        return required_tier == 'free'
    
    # Check if subscription is active
    if not user.subscription.is_active:
        return required_tier == 'free'
    
    # Define tier hierarchy
    tier_order = {
        'free': 0,
        'basic': 1,
        'premium': 2,
        'enterprise': 3
    }
    
    user_tier = user.subscription.plan.tier if user.subscription.plan else 'free'
    user_tier_level = tier_order.get(user_tier, 0)
    required_tier_level = tier_order.get(required_tier, 0)
    
    return user_tier_level >= required_tier_level


@register.simple_tag
def get_plan_badge(tier):
    """
    Get HTML badge for a plan tier.
    
    Args:
        tier: Plan tier ('free', 'basic', 'premium', 'enterprise')
    
    Returns:
        str: HTML badge element
    
    Example:
        {{ 'premium'|get_plan_badge }}
        <!-- Returns: <span class="badge bg-primary-subtle text-primary">Premium</span> -->
    """
    badge_config = {
        'free': {
            'class': 'bg-secondary-subtle text-secondary',
            'label': 'Gratuito'
        },
        'basic': {
            'class': 'bg-info-subtle text-info',
            'label': 'Básico'
        },
        'premium': {
            'class': 'bg-primary-subtle text-primary',
            'label': 'Premium'
        },
        'enterprise': {
            'class': 'bg-success-subtle text-success',
            'label': 'Enterprise'
        }
    }
    
    config = badge_config.get(tier, badge_config['free'])
    return f'<span class="badge {config["class"]}">{config["label"]}</span>'


@register.simple_tag(takes_context=True)
def get_user_plan(context):
    """
    Get current user's plan tier.
    
    Returns:
        str: Plan tier ('free', 'basic', 'premium', 'enterprise')
    
    Example:
        {% get_user_plan as user_plan %}
        <p>Your plan: {{ user_plan }}</p>
    """
    request = context.get('request')
    if not request:
        return 'free'
    
    user = request.user
    if not user.is_authenticated:
        return 'free'
    
    if not hasattr(user, 'subscription') or not user.subscription:
        return 'free'
    
    if not user.subscription.is_active:
        return 'free'
    
    return user.subscription.plan.tier if user.subscription.plan else 'free'


@register.simple_tag
def get_required_plan(feature):
    """
    Get the minimum required plan tier for a feature.
    
    Args:
        feature: Feature name
    
    Returns:
        str: Required plan tier
    
    Example:
        {% get_required_plan 'school_comparison' as required %}
        <!-- required = 'premium' -->
    """
    feature_requirements = {
        'national_view': 'free',
        'basic_search': 'free',
        'department_analysis': 'basic',
        'municipality_analysis': 'basic',
        'school_details': 'basic',
        'export_csv': 'basic',
        'school_comparison': 'premium',
        'custom_rankings': 'premium',
        'export_excel': 'premium',
        'export_pdf': 'premium',
        'api_access': 'enterprise',
        'custom_dashboards': 'enterprise',
    }
    
    return feature_requirements.get(feature, 'free')
