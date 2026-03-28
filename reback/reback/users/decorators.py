"""
Subscription decorators for paywall enforcement.
Tier hierarchy: free (0) < pro (1) < institutional (2)

Backward-compatible aliases:
  'basic'  → mapped to 'pro'    (level 1)
  'premium' → mapped to 'pro'   (level 1)
  'enterprise' → mapped to 'institutional' (level 2)
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from reback.users.subscription_models import UserSubscription


# ── Tier hierarchy (higher number = more access) ──────────────────────────────
TIER_HIERARCHY = {
    # New canonical tiers
    'free':          0,
    'pro':           1,
    'institutional': 2,
    # Legacy aliases — kept for backward compatibility with existing data/code
    'basic':         1,   # treated as 'pro'
    'premium':       1,   # treated as 'pro'
    'enterprise':    2,   # treated as 'institutional'
}

# Human-readable names for each tier
TIER_DISPLAY_NAMES = {
    'free':          'Freemium',
    'pro':           'Pro Estratégico',
    'institutional': 'Institucional',
    'basic':         'Pro Estratégico',
    'premium':       'Pro Estratégico',
    'enterprise':    'Institucional',
}


def _tier_level(tier: str) -> int:
    """Return the numeric level for a tier string."""
    return TIER_HIERARCHY.get(tier, 0)


def subscription_required(tier='pro'):
    """
    Decorator to require a minimum subscription tier before accessing a view.

    Args:
        tier: Minimum tier required. Use 'pro' or 'institutional'.
              Legacy values 'basic', 'premium', 'enterprise' are still accepted.

    Usage::

        @login_required
        @subscription_required(tier='pro')
        def my_pro_view(request):
            ...

        @login_required
        @subscription_required(tier='institutional')
        def my_institutional_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Superusers bypass all restrictions
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            try:
                user_subscription = UserSubscription.objects.select_related('plan').get(
                    user=request.user
                )
            except UserSubscription.DoesNotExist:
                # Auto-create Free subscription and redirect to pricing if needed
                from reback.users.subscription_models import SubscriptionPlan
                try:
                    free_plan = SubscriptionPlan.objects.get(tier='free')
                except SubscriptionPlan.DoesNotExist:
                    messages.error(request, 'Error al cargar tu suscripción. Contacta soporte.')
                    return redirect('pages:pricing')

                UserSubscription.objects.create(user=request.user, plan=free_plan, is_active=True)

                if _tier_level(tier) == 0:
                    return view_func(request, *args, **kwargs)

                _redirect_with_message(request, tier)
                return redirect('pages:pricing')

            # Check subscription active
            if not user_subscription.is_active:
                messages.warning(
                    request,
                    'Tu suscripción ha expirado. Por favor renueva tu plan para continuar.'
                )
                return redirect('pages:pricing')

            # Check tier level
            user_tier = user_subscription.plan.tier
            if _tier_level(user_tier) < _tier_level(tier):
                _redirect_with_message(request, tier, user_tier)
                return redirect('pages:pricing')

            # Check daily query limit (only for non-free views)
            if _tier_level(tier) > 0 and not user_subscription.can_make_query():
                messages.warning(
                    request,
                    f'Has alcanzado el límite de {user_subscription.plan.max_queries_per_day} '
                    'consultas diarias. Actualiza tu plan para obtener más consultas.'
                )
                return redirect('pages:pricing')

            # Increment query count and proceed
            if _tier_level(tier) > 0:
                user_subscription.increment_query_count()

            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator


def _redirect_with_message(request, required_tier: str, user_tier: str = 'free'):
    """Helper: add a contextual warning message before redirecting."""
    required_name = TIER_DISPLAY_NAMES.get(required_tier, required_tier.capitalize())
    user_name = TIER_DISPLAY_NAMES.get(user_tier, user_tier.capitalize())

    if required_tier in ('institutional', 'enterprise'):
        messages.warning(
            request,
            f'Esta sección es exclusiva del Plan Institucional. '
            f'Actualmente tienes el plan {user_name}. '
            'Contacta a nuestro equipo de ventas para acceso institucional.'
        )
    else:
        messages.warning(
            request,
            f'Esta función requiere el Plan {required_name}. '
            f'Actualmente tienes el plan {user_name}.'
        )


def feature_required(feature_name):
    """
    Decorator to require a specific boolean feature flag on the user's plan
    (e.g., 'export_pdf', 'api_access').

    Usage::

        @feature_required('export_pdf')
        def export_pdf_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            try:
                user_subscription = UserSubscription.objects.select_related('plan').get(
                    user=request.user
                )
                has_feature = getattr(user_subscription.plan, feature_name, False)

                if not has_feature:
                    messages.warning(
                        request,
                        f'"{feature_name.replace("_", " ").title()}" no está disponible '
                        'en tu plan actual. Actualiza para desbloquear esta función.'
                    )
                    return redirect('pages:pricing')

                return view_func(request, *args, **kwargs)

            except UserSubscription.DoesNotExist:
                messages.info(request, 'Necesitas una suscripción para acceder a esta función.')
                return redirect('pages:pricing')

        return _wrapped_view
    return decorator
