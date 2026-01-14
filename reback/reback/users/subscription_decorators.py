"""
Decoradores para proteger endpoints según nivel de suscripción.
"""
from functools import wraps
from django.http import JsonResponse
from django.urls import reverse


def require_plan(min_tier):
    """
    Decorador para requerir un plan mínimo.
    
    Args:
        min_tier: 'free', 'basic', 'premium', o 'enterprise'
    
    Usage:
        @require_plan('basic')
        def my_view(request):
            ...
    """
    tier_hierarchy = {
        'free': 0,
        'basic': 1,
        'premium': 2,
        'enterprise': 3
    }
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Verificar que el middleware haya agregado la info de plan
            if not hasattr(request, 'plan'):
                return JsonResponse({
                    'error': 'Subscription required',
                    'message': 'Please subscribe to access this feature'
                }, status=403)
            
            user_tier_level = tier_hierarchy.get(request.plan.tier, 0)
            required_tier_level = tier_hierarchy.get(min_tier, 0)
            
            if user_tier_level < required_tier_level:
                return JsonResponse({
                    'error': f'This feature requires {min_tier} plan or higher',
                    'current_plan': request.plan.tier,
                    'required_plan': min_tier,
                    'upgrade_url': reverse('pages:dynamic_pages', kwargs={'template_name': 'pricing'})
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_feature(feature_name):
    """
    Decorador para requerir una feature específica del plan.
    
    Args:
        feature_name: nombre del campo booleano en SubscriptionPlan
                     (ej: 'access_schools', 'export_excel', 'api_access')
    
    Usage:
        @require_feature('access_schools')
        def school_detail_view(request, school_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'plan'):
                return JsonResponse({
                    'error': 'Subscription required',
                    'message': 'Please subscribe to access this feature'
                }, status=403)
            
            # Verificar si el plan tiene la feature
            has_feature = getattr(request.plan, feature_name, False)
            
            if not has_feature:
                # Mapeo de features a nombres user-friendly
                feature_names = {
                    'access_departments': 'department-level data',
                    'access_municipalities': 'municipality-level data',
                    'access_schools': 'individual school data',
                    'export_csv': 'CSV export',
                    'export_excel': 'Excel export',
                    'export_pdf': 'PDF export',
                    'api_access': 'API access',
                }
                
                feature_display = feature_names.get(feature_name, feature_name)
                
                return JsonResponse({
                    'error': f'This feature is not available in your plan',
                    'feature': feature_display,
                    'current_plan': request.plan.tier,
                    'message': f'Upgrade your plan to access {feature_display}',
                    'upgrade_url': reverse('pages:dynamic_pages', kwargs={'template_name': 'pricing'})
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_years_of_data(min_years):
    """
    Decorador para verificar acceso a datos históricos.
    
    Args:
        min_years: número mínimo de años requeridos
    
    Usage:
        @require_years_of_data(10)
        def historical_trends_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'plan'):
                return JsonResponse({
                    'error': 'Subscription required'
                }, status=403)
            
            if request.plan.years_of_data < min_years:
                return JsonResponse({
                    'error': 'Insufficient historical data access',
                    'message': f'This feature requires access to at least {min_years} years of data',
                    'current_access': f'{request.plan.years_of_data} years',
                    'required_access': f'{min_years} years',
                    'upgrade_url': reverse('pages:dynamic_pages', kwargs={'template_name': 'pricing'})
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
