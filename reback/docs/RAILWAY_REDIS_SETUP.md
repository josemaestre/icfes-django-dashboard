# 🚀 Guía de Configuración: Redis en Railway

## Paso 1: Agregar Servicio Redis en Railway

### 1.1 Acceder al Dashboard de Railway
1. Ve a https://railway.app/
2. Selecciona tu proyecto: `icfes-django-dashboard-production`

### 1.2 Agregar Redis
1. Click en "New" → "Database" → "Add Redis"
2. Railway creará automáticamente:
   - ✅ Servicio Redis
   - ✅ Variable `REDIS_URL` (formato: `redis://default:password@redis.railway.internal:6379`)

### 1.3 Conectar Redis al Servicio Django

**En el servicio Django, agregar estas variables:**

```bash
# Railway ya tiene REDIS_URL automáticamente
# Solo necesitas agregar estas dos:
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

**Cómo agregar variables:**
1. Click en tu servicio Django
2. Tab "Variables"
3. Click "New Variable"
4. Agregar cada variable (nombre y valor)

---

## Paso 2: Crear Servicio Celery Worker

### 2.1 Duplicar Servicio Django
1. En Railway Dashboard, click "New Service"
2. Seleccionar "GitHub Repo"
3. Elegir el mismo repositorio: `josemaestre/icfes-django-dashboard`
4. Nombre del servicio: `icfes-celery-worker`

### 2.2 Configurar Variables de Entorno

**Copiar TODAS las variables del servicio Django:**
- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `WOMPI_PUBLIC_KEY`
- `WOMPI_PRIVATE_KEY`
- `WOMPI_EVENTS_SECRET`
- `WOMPI_INTEGRITY_SECRET`
- `WOMPI_BASE_URL`
- Todas las demás variables del servicio Django

### 2.3 Configurar Start Command

**En el servicio Celery Worker:**
1. Tab "Settings"
2. Sección "Deploy"
3. "Start Command": 
```bash
celery -A config worker -l info --concurrency=2
```

### 2.4 Configurar Build Command (opcional)

Si necesitas instalar dependencias:
```bash
pip install -r requirements/production.txt
```

---

## Paso 3: (Opcional) Crear Servicio Celery Beat

**Solo si quieres cobros recurrentes automáticos**

### 3.1 Crear Nuevo Servicio
1. Railway Dashboard → "New Service"
2. Mismo repositorio
3. Nombre: `icfes-celery-beat`

### 3.2 Configurar Variables
Copiar las mismas variables del servicio Django

### 3.3 Start Command
```bash
celery -A config beat -l info
```

---

## Paso 4: Migrar Base de Datos (django_celery_beat)

**Después de hacer push de los cambios:**

1. Ir al servicio Django en Railway
2. Tab "Deployments" → Click en el deployment activo
3. Tab "Logs"
4. Buscar el mensaje de migración:
```
Operations to perform:
  Apply all migrations: django_celery_beat
```

**Si no se ejecuta automáticamente:**
1. Railway Dashboard → Servicio Django
2. Tab "Settings" → "Deploy"
3. Agregar a "Start Command" (antes de gunicorn):
```bash
python manage.py migrate && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 4
```

---

## Paso 5: Verificar Deployment

### 5.1 Verificar Redis Conectado

**Logs del servicio Django:**
```bash
# Buscar en logs:
✅ "Connected to redis://..."
✅ "Cache backend initialized"
```

### 5.2 Verificar Celery Worker

**Logs del servicio Celery Worker:**
```bash
# Buscar:
✅ "celery@worker ready"
✅ "Connected to redis://..."
✅ "mingle: searching for neighbors"
```

### 5.3 Verificar Celery Beat (si lo creaste)

**Logs del servicio Celery Beat:**
```bash
# Buscar:
✅ "beat: Starting..."
✅ "Scheduler: Sending due task charge-monthly-subscriptions"
```

---

## Paso 6: Testing en Producción

### 6.1 Probar Caché

**Desde tu navegador:**
1. Abrir DevTools (F12)
2. Tab "Network"
3. Visitar: `https://tu-app.railway.app/api/charts/tendencias/`
4. Primera request: ~20-30ms (cache miss)
5. Segunda request: ~5-10ms (cache hit) ✅

### 6.2 Probar Celery (desde Railway Shell)

**Opción 1: Desde Railway CLI**
```bash
railway run python manage.py shell

# En el shell:
from reback.users.tasks import charge_monthly_subscriptions
result = charge_monthly_subscriptions.delay()
print(result.id)  # Debe retornar task ID
```

**Opción 2: Desde logs**
Ejecutar una acción que dispare una tarea (ej: crear suscripción) y ver logs del worker

---

## 📊 Arquitectura Final en Railway

```
┌─────────────────────────────────────────────────────────────┐
│                      Railway Project                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Django     │◄────►│    Redis     │◄────►│  Celery   │ │
│  │   Web App    │      │   (Cache +   │      │  Worker   │ │
│  │  (Gunicorn)  │      │    Broker)   │      │           │ │
│  │  PORT: 8000  │      │  PORT: 6379  │      │           │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                                           │        │
│         │                                           │        │
│         ▼                                           ▼        │
│  ┌──────────────┐                          ┌──────────────┐ │
│  │  PostgreSQL  │                          │ Celery Beat  │ │
│  │   (Django    │                          │  (Periodic)  │ │
│  │   Metadata)  │                          │              │ │
│  └──────────────┘                          └──────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Troubleshooting

### Error: "Connection refused to Redis"

**Solución:**
1. Verificar que Redis service está "Active"
2. Verificar que `REDIS_URL` existe en variables
3. Verificar formato: `redis://default:password@redis.railway.internal:6379`

### Error: "Celery worker not starting"

**Solución:**
1. Verificar que `config/celery.py` existe
2. Verificar que `config/__init__.py` importa `celery_app`
3. Verificar que `CELERY_BROKER_URL` está configurado
4. Ver logs completos del worker para más detalles

### Error: "django_celery_beat not found"

**Solución:**
1. Verificar que `django_celery_beat` está en `INSTALLED_APPS`
2. Ejecutar migraciones: `python manage.py migrate`
3. Redeploy el servicio Django

### Caché no funciona

**Solución:**
1. Verificar que `django-redis` está instalado
2. Verificar que `CACHES` está configurado en settings
3. Probar en shell:
```python
from django.core.cache import cache
cache.set('test', 'value', 60)
print(cache.get('test'))  # Debe retornar 'value'
```

---

## 📈 Métricas Esperadas

### Performance
- **Antes:** 15-25ms por query
- **Después (cache hit):** 5-10ms
- **Mejora:** 50-60%

### Capacidad
- **Antes:** ~100 usuarios concurrentes
- **Después:** ~300-500 usuarios concurrentes

### Features Desbloqueadas
- ✅ Cobros recurrentes automáticos (Celery Beat)
- ✅ Emails transaccionales (Celery Worker)
- ✅ Tareas en background
- ✅ Caché de queries costosas

---

## 🎯 Próximos Pasos

1. ✅ Configurar Redis en Railway
2. ✅ Crear Celery Worker service
3. ✅ (Opcional) Crear Celery Beat service
4. ✅ Verificar logs y testing
5. ⏳ Monitorear performance con Railway Metrics
6. ⏳ Implementar más endpoints con caché
7. ⏳ Configurar Sentry para error tracking

---

**Tiempo estimado:** 30-45 minutos  
**Costo adicional:** $0 (Redis incluido en plan Railway)
