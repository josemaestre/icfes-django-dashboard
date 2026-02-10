"""
App configuration para reback.middleware
Inicializa logging de Redis al startup
"""
import logging
from django.apps import AppConfig

logger = logging.getLogger('redis_cache')


class MiddlewareConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reback.middleware'
    verbose_name = 'Reback Middleware'
    
    def ready(self):
        """
        Ejecutado cuando Django inicia.
        Verifica y loggea el estado de Redis.
        """
        logger.info("=" * 60)
        logger.info("🚀 Django Startup - Verificando Redis")
        logger.info("=" * 60)
        
        # Verificar configuración de Redis
        from django.conf import settings
        
        if hasattr(settings, 'CACHES'):
            cache_config = settings.CACHES.get('default', {})
            backend = cache_config.get('BACKEND', 'NOT CONFIGURED')
            location = cache_config.get('LOCATION', 'NOT CONFIGURED')
            
            logger.info(f"📦 Cache Backend: {backend}")
            logger.info(f"📍 Cache Location: {location}")
            
            if 'redis' in backend.lower():
                logger.info("✅ Redis backend configurado")
                logger.info("   (Test de conexión deshabilitado para evitar bloqueo en startup)")
                
                # NOTA: Test de conexión comentado porque puede bloquear el startup
                # Si Redis no está accesible, Django usará LocMemCache automáticamente
                # gracias a IGNORE_EXCEPTIONS=True en settings
                
                # try:
                #     from django.core.cache import cache
                #     test_key = '_django_startup_test'
                #     test_value = 'startup_ok'
                #     cache.set(test_key, test_value, 10)
                #     result = cache.get(test_key)
                #     if result == test_value:
                #         logger.info("✅ Redis conectado exitosamente")
                # except Exception as e:
                #     logger.warning(f"⚠️  Redis no accesible: {e}")
                
            else:
                logger.warning(f"⚠️  Backend no es Redis: {backend}")
        else:
            logger.error("❌ CACHES no configurado en settings")
        
        # Verificar Celery
        if hasattr(settings, 'CELERY_BROKER_URL'):
            broker_url = settings.CELERY_BROKER_URL
            logger.info(f"📨 Celery Broker: {broker_url[:40]}...")
            
            if 'redis' in broker_url.lower():
                logger.info("✅ Celery configurado con Redis")
            else:
                logger.warning(f"⚠️  Celery broker no es Redis")
        else:
            logger.warning("⚠️  CELERY_BROKER_URL no configurado")
        
        logger.info("=" * 60)
