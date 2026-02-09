"""
Script de verificación: Redis en Railway
Ejecutar desde Railway Shell para diagnosticar problemas
"""

print("=" * 60)
print("🔍 DIAGNÓSTICO: Redis en Railway")
print("=" * 60)

# 1. Verificar imports
print("\n1️⃣ Verificando imports...")
try:
    import redis
    print("   ✅ redis instalado:", redis.__version__)
except ImportError as e:
    print("   ❌ redis NO instalado:", e)

try:
    import django_redis
    print("   ✅ django-redis instalado")
except ImportError as e:
    print("   ❌ django-redis NO instalado:", e)

try:
    import celery
    print("   ✅ celery instalado:", celery.__version__)
except ImportError as e:
    print("   ❌ celery NO instalado:", e)

# 2. Verificar configuración Django
print("\n2️⃣ Verificando configuración Django...")
try:
    from django.conf import settings
    
    # CACHES
    if hasattr(settings, 'CACHES'):
        cache_backend = settings.CACHES.get('default', {}).get('BACKEND')
        cache_location = settings.CACHES.get('default', {}).get('LOCATION')
        print(f"   ✅ CACHES configurado")
        print(f"      Backend: {cache_backend}")
        print(f"      Location: {cache_location}")
    else:
        print("   ❌ CACHES no configurado")
    
    # CELERY
    if hasattr(settings, 'CELERY_BROKER_URL'):
        print(f"   ✅ CELERY_BROKER_URL: {settings.CELERY_BROKER_URL[:30]}...")
    else:
        print("   ❌ CELERY_BROKER_URL no configurado")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# 3. Probar conexión a Redis
print("\n3️⃣ Probando conexión a Redis...")
try:
    from django.core.cache import cache
    
    # Test básico
    test_key = 'railway_test_key'
    test_value = 'railway_test_value_12345'
    
    cache.set(test_key, test_value, 60)
    result = cache.get(test_key)
    
    if result == test_value:
        print(f"   ✅ Redis funcionando correctamente")
        print(f"      Set: {test_key} = {test_value}")
        print(f"      Get: {result}")
    else:
        print(f"   ❌ Redis no retorna valor correcto")
        print(f"      Esperado: {test_value}")
        print(f"      Obtenido: {result}")
        
except Exception as e:
    print(f"   ❌ Error conectando a Redis: {e}")
    print(f"      Tipo: {type(e).__name__}")

# 4. Verificar Celery
print("\n4️⃣ Verificando Celery...")
try:
    from config.celery import app as celery_app
    print(f"   ✅ Celery app importado")
    print(f"      Broker: {celery_app.conf.broker_url[:30]}...")
    print(f"      Backend: {celery_app.conf.result_backend[:30]}...")
except Exception as e:
    print(f"   ❌ Error importando Celery: {e}")

# 5. Listar tareas registradas
print("\n5️⃣ Tareas Celery registradas...")
try:
    from config.celery import app as celery_app
    tasks = list(celery_app.tasks.keys())
    user_tasks = [t for t in tasks if not t.startswith('celery.')]
    
    if user_tasks:
        print(f"   ✅ {len(user_tasks)} tareas encontradas:")
        for task in user_tasks:
            print(f"      - {task}")
    else:
        print("   ⚠️  No hay tareas de usuario registradas")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# 6. Variables de entorno
print("\n6️⃣ Variables de entorno...")
import os
redis_url = os.getenv('REDIS_URL', 'NO CONFIGURADO')
celery_broker = os.getenv('CELERY_BROKER_URL', 'NO CONFIGURADO')

if redis_url != 'NO CONFIGURADO':
    print(f"   ✅ REDIS_URL: {redis_url[:40]}...")
else:
    print(f"   ❌ REDIS_URL no configurado")

if celery_broker != 'NO CONFIGURADO':
    print(f"   ✅ CELERY_BROKER_URL: {celery_broker[:40]}...")
else:
    print(f"   ❌ CELERY_BROKER_URL no configurado")

print("\n" + "=" * 60)
print("✅ Diagnóstico completado")
print("=" * 60)
