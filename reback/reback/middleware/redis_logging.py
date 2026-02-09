"""
Middleware para loggear interacciones con Redis Cache.
Ayuda a diagnosticar problemas de caché en producción.
"""
import logging
import time

logger = logging.getLogger('redis_cache')


class RedisCacheLoggingMiddleware:
    """
    Middleware que loggea todas las interacciones con el cache de Redis.
    Útil para debugging en producción.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("🔧 RedisCacheLoggingMiddleware initialized")
    
    def __call__(self, request):
        # Log antes del request
        path = request.path
        method = request.method
        
        # Solo loggear endpoints de API (evitar ruido de static files)
        if path.startswith('/api/') or path.startswith('/dashboard/'):
            logger.info(f"📥 Request: {method} {path}")
            start_time = time.time()
        
        response = self.get_response(request)
        
        # Log después del response
        if path.startswith('/api/') or path.startswith('/dashboard/'):
            duration = (time.time() - start_time) * 1000  # ms
            status = response.status_code
            
            # Detectar si fue cache hit (response muy rápido)
            cache_status = "🟢 CACHE HIT" if duration < 10 else "🔴 CACHE MISS"
            
            logger.info(
                f"📤 Response: {method} {path} → {status} "
                f"({duration:.2f}ms) {cache_status}"
            )
        
        return response
