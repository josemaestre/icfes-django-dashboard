"""
Middleware para controlar acceso basado en suscripción.
"""
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from .subscription_models import UserSubscription, SubscriptionPlan, QueryLog
from datetime import date
import time


class SubscriptionMiddleware:
    """
    Middleware para verificar permisos de suscripción antes de cada request.
    Solo se aplica a endpoints de ICFES API.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    
    def __call__(self, request):
        # Endpoints exentos de límites (visualizaciones básicas)
        EXEMPT_ENDPOINTS = [
            '/icfes/api/mapa-estudiantes-heatmap/',
            '/icfes/api/mapa-departamentos/',
            '/icfes/api/mapa-municipios/',
            '/icfes/api/estadisticas/',
            '/icfes/api/anos/',
            '/icfes/api/charts/',
            '/icfes/api/hierarchy/',
            '/icfes/api/search/colegios/',  # Búsqueda de colegios
            '/icfes/api/generate-ai-analysis/',  # Análisis de IA
            '/icfes/api/colegios/destacados/',  # Colegios destacados
            '/icfes/api/colegio/',  # Detalles de colegio (incluye AI recommendations)
        ]
        
        # Solo aplicar a endpoints de ICFES API
        if request.path.startswith('/icfes/api/'):
            # Verificar si es un endpoint exento
            is_exempt = any(request.path.startswith(endpoint) for endpoint in EXEMPT_ENDPOINTS)
            
            # Verificar autenticación (solo para endpoints no exentos)
            if not is_exempt and not request.user.is_authenticated:
                return JsonResponse({
                    'error': 'Authentication required',
                    'message': 'Please log in to access ICFES Analytics',
                    'login_url': reverse('account_login')
                }, status=401)
            
            # Para usuarios autenticados, obtener o crear suscripción
            if request.user.is_authenticated:
                try:
                    subscription = UserSubscription.objects.select_related('plan').get(
                        user=request.user,
                        is_active=True
                    )
                except UserSubscription.DoesNotExist:
                    # Asignar plan Free por defecto
                    subscription = self._create_free_subscription(request.user)
                
                # Verificar límite de queries diarias (solo para endpoints no exentos)
                if not is_exempt and not subscription.can_make_query():
                    return JsonResponse({
                        'error': 'Daily query limit exceeded',
                        'message': f'You have reached your daily limit of {subscription.plan.max_queries_per_day} queries',
                        'current_plan': subscription.plan.tier,
                        'queries_used': subscription.queries_today,
                        'queries_limit': subscription.plan.max_queries_per_day,
                        'upgrade_url': reverse('pages:dynamic_pages', kwargs={'template_name': 'pages-pricing'})
                    }, status=429)
                
                # Agregar info de suscripción al request
                request.subscription = subscription
                request.plan = subscription.plan
            
            # Marcar inicio de request para logging
            request._start_time = time.time()
        
        # Procesar request
        response = self.get_response(request)
        
        # Post-processing: registrar query si es API de ICFES
        if request.path.startswith('/icfes/api/') and hasattr(request, 'subscription'):
            # Incrementar contador solo si la respuesta fue exitosa y no es endpoint exento
            is_exempt = any(request.path.startswith(endpoint) for endpoint in [
                '/icfes/api/mapa-estudiantes-heatmap/',
                '/icfes/api/mapa-departamentos/',
                '/icfes/api/mapa-municipios/',
                '/icfes/api/estadisticas/',
                '/icfes/api/anos/',
                '/icfes/api/charts/',
                '/icfes/api/hierarchy/',
                '/icfes/api/search/colegios/',
                '/icfes/api/generate-ai-analysis/',
                '/icfes/api/colegios/destacados/',
                '/icfes/api/colegio/',
            ])
            
            if 200 <= response.status_code < 300 and not is_exempt:
                request.subscription.increment_query_count()
                
                # Registrar en log
                response_time = int((time.time() - request._start_time) * 1000)
                QueryLog.objects.create(
                    user=request.user,
                    endpoint=request.path,
                    query_params=dict(request.GET),
                    response_time_ms=response_time,
                    status_code=response.status_code
                )
        
        return response

    
    def _create_free_subscription(self, user):
        """Crea una suscripción Free para un nuevo usuario."""
        try:
            free_plan = SubscriptionPlan.objects.get(tier='free')
        except SubscriptionPlan.DoesNotExist:
            # Si no existe el plan Free, crearlo con valores por defecto
            free_plan = SubscriptionPlan.objects.create(
                tier='free',
                name='Free Plan',
                description='Basic access to ICFES Analytics',
                price_monthly=0.00,
                max_queries_per_day=10,
                access_regions=True,
                access_departments=False,
                access_municipalities=False,
                access_schools=False,
                years_of_data=3,
                export_csv=False,
                api_access=False,
            )
        
        subscription = UserSubscription.objects.create(
            user=user,
            plan=free_plan
        )
        return subscription
