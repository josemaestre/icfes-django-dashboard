"""
Decoradores para proteger endpoints según nivel de suscripción.
Tier hierarchy: free (0) < pro (1) < institutional (2)
"""
from functools import wraps
from django.http import JsonResponse
from django.urls import reverse


# ── Tier hierarchy ─────────────────────────────────────────────────────────────
_TIER_HIERARCHY = {
    'free':          0,
    'pro':           1,
    'institutional': 2,
    # Legacy aliases
    'basic':         1,
    'premium':       1,
    'enterprise':    2,
}


def require_plan(min_tier):
    """
    Decorador para requerir un plan mínimo en endpoints API (retorna JSON 403).

    Args:
        min_tier: 'free', 'pro' o 'institutional'
                  Legacy values 'basic', 'premium', 'enterprise' también aceptados.

    Usage::

        @require_plan('pro')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Superusers bypass restrictions
            if hasattr(request, 'user') and request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Verificar que el middleware haya agregado la info de plan
            if not hasattr(request, 'plan'):
                return JsonResponse({
                    'error': 'Subscription required',
                    'message': 'Inicia sesión para acceder a esta función.',
                    'login_url': reverse('account_login'),
                }, status=403)

            user_level = _TIER_HIERARCHY.get(request.plan.tier, 0)
            required_level = _TIER_HIERARCHY.get(min_tier, 0)

            if user_level < required_level:
                _tier_label = {
                    'pro':           'Pro Estratégico',
                    'institutional': 'Institucional',
                    'basic':         'Pro Estratégico',
                    'premium':       'Pro Estratégico',
                    'enterprise':    'Institucional',
                }.get(min_tier, min_tier.capitalize())

                return JsonResponse({
                    'error': f'Se requiere el plan {_tier_label} o superior.',
                    'current_plan': request.plan.tier,
                    'required_plan': min_tier,
                    'upgrade_url': reverse('pages:pricing'),
                }, status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_feature(feature_name):
    """
    Decorador para requerir una feature específica del plan (retorna JSON 403).

    Args:
        feature_name: nombre del campo booleano en SubscriptionPlan
                     (ej: 'access_schools', 'export_excel', 'api_access')

    Usage::

        @require_feature('access_schools')
        def school_detail_view(request, school_id):
            ...
    """
    _FEATURE_LABELS = {
        'access_departments':  'análisis departamental',
        'access_municipalities': 'análisis municipal',
        'access_schools':      'datos de colegios individuales',
        'export_csv':          'exportación CSV',
        'export_excel':        'exportación Excel',
        'export_pdf':          'exportación PDF',
        'api_access':          'acceso a API',
    }

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if hasattr(request, 'user') and request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if not hasattr(request, 'plan'):
                return JsonResponse({
                    'error': 'Subscription required',
                    'message': 'Inicia sesión para acceder a esta función.',
                }, status=403)

            has_feature = getattr(request.plan, feature_name, False)

            if not has_feature:
                label = _FEATURE_LABELS.get(feature_name, feature_name.replace('_', ' '))
                return JsonResponse({
                    'error': f'Tu plan actual no incluye {label}.',
                    'feature': label,
                    'current_plan': request.plan.tier,
                    'upgrade_url': reverse('pages:pricing'),
                }, status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_years_of_data(min_years):
    """
    Decorador para verificar acceso a datos históricos.

    Args:
        min_years: número mínimo de años requeridos

    Usage::

        @require_years_of_data(14)
        def historical_trends_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if hasattr(request, 'user') and request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if not hasattr(request, 'plan'):
                return JsonResponse({'error': 'Subscription required'}, status=403)

            if request.plan.years_of_data < min_years:
                return JsonResponse({
                    'error': 'Acceso histórico insuficiente.',
                    'message': f'Esta función requiere acceso a al menos {min_years} años de datos.',
                    'current_access': f'{request.plan.years_of_data} años',
                    'required_access': f'{min_years} años',
                    'upgrade_url': reverse('pages:pricing'),
                }, status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
