"""
Subscription decorators for paywall enforcement.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from reback.users.subscription_models import UserSubscription


# Tier hierarchy (higher number = more access)
TIER_HIERARCHY = {
    'free': 0,
    'basic': 1,
    'premium': 2,
    'enterprise': 3,
}


def subscription_required(tier='basic'):
    """
    Decorator to require a specific subscription tier.
    
    Usage:
        @subscription_required(tier='premium')
        def my_premium_view(request):
            ...
    
    Args:
        tier: Minimum tier required ('basic', 'premium', 'enterprise')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            try:
                # Get user's subscription
                user_subscription = UserSubscription.objects.get(user=request.user)
                
                # Check if subscription is active
                if not user_subscription.is_active:
                    messages.warning(
                        request,
                        'Tu suscripción ha expirado. Por favor renueva tu plan para continuar.'
                    )
                    return redirect('pages:pricing')
                
                # Check tier level
                user_tier = user_subscription.plan.tier
                required_tier_level = TIER_HIERARCHY.get(tier, 0)
                user_tier_level = TIER_HIERARCHY.get(user_tier, 0)
                
                if user_tier_level < required_tier_level:
                    messages.warning(
                        request,
                        f'Esta función requiere un plan {tier.capitalize()} o superior. '
                        f'Actualmente tienes el plan {user_tier.capitalize()}.'
                    )
                    return redirect('pages:pricing')
                
                # Check daily query limit
                if not user_subscription.can_make_query():
                    messages.warning(
                        request,
                        f'Has alcanzado el límite de {user_subscription.plan.max_queries_per_day} consultas diarias. '
                        'Actualiza tu plan para obtener más consultas.'
                    )
                    return redirect('pages:pricing')
                
                # Increment query count
                user_subscription.increment_query_count()
                
                # All checks passed, execute view
                return view_func(request, *args, **kwargs)
                
            except UserSubscription.DoesNotExist:
                # User doesn't have a subscription, create Free plan
                from reback.users.subscription_models import SubscriptionPlan
                free_plan = SubscriptionPlan.objects.get(tier='free')
                UserSubscription.objects.create(
                    user=request.user,
                    plan=free_plan,
                    is_active=True
                )
                
                # If Free tier is sufficient, allow access
                if tier == 'free':
                    return view_func(request, *args, **kwargs)
                else:
                    messages.info(
                        request,
                        f'Esta función requiere un plan {tier.capitalize()}. '
                        'Actualmente tienes el plan Free.'
                    )
                    return redirect('pages:pricing')
        
        return _wrapped_view
    return decorator


def feature_required(feature_name):
    """
    Decorator to require a specific feature (e.g., 'export_pdf', 'api_access').
    
    Usage:
        @feature_required('export_pdf')
        def export_pdf_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            try:
                user_subscription = UserSubscription.objects.get(user=request.user)
                
                # Check if plan has the required feature
                has_feature = getattr(user_subscription.plan, feature_name, False)
                
                if not has_feature:
                    messages.warning(
                        request,
                        f'Esta función no está disponible en tu plan actual. '
                        f'Actualiza a un plan superior para acceder a {feature_name.replace("_", " ")}.'
                    )
                    return redirect('pages:pricing')
                
                return view_func(request, *args, **kwargs)
                
            except UserSubscription.DoesNotExist:
                messages.info(request, 'Necesitas una suscripción para acceder a esta función.')
                return redirect('pages:pricing')
        
        return _wrapped_view
    return decorator
