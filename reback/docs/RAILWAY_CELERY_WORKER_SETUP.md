# 🚀 Guía Paso a Paso: Crear Celery Worker en Railway

## ✅ Pre-requisitos (Ya tienes esto)
- ✅ Redis configurado en Railway
- ✅ Código commiteado (commit 5257f85)
- ✅ Código pusheado a GitHub

---

## 📋 Paso 1: Crear Nuevo Servicio en Railway

### 1.1 Acceder a tu proyecto
1. Ve a https://railway.app/
2. Inicia sesión
3. Selecciona tu proyecto: **icfes-django-dashboard-production**

### 1.2 Crear nuevo servicio
1. Click en el botón **"+ New"** (esquina superior derecha)
2. Selecciona **"GitHub Repo"**
3. Busca y selecciona: **josemaestre/icfes-django-dashboard**
4. Railway te mostrará una vista previa del servicio

### 1.3 Nombrar el servicio
1. En la parte superior, donde dice "Service Name"
2. Cámbiale el nombre a: **`icfes-celery-worker`**
3. Click en cualquier lugar para guardar el nombre

---

## 📋 Paso 2: Configurar Variables de Entorno

### 2.1 Ir a la pestaña Variables
1. Click en el servicio **icfes-celery-worker** que acabas de crear
2. Click en la pestaña **"Variables"**

### 2.2 Copiar variables del servicio Django

**Necesitas copiar TODAS estas variables del servicio Django:**

```bash
# Variables críticas (OBLIGATORIAS):
DJANGO_SETTINGS_MODULE=config.settings.railway
DJANGO_SECRET_KEY=<copiar del servicio Django>
DJANGO_ALLOWED_HOSTS=<copiar del servicio Django>

# Database
DATABASE_URL=${DATABASE_URL}  # Railway lo resuelve automáticamente

# Redis (CRÍTICO para Celery)
REDIS_URL=${REDIS_URL}  # Railway lo resuelve automáticamente
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}

# Wompi (para tareas de cobros)
WOMPI_PUBLIC_KEY=<copiar del servicio Django>
WOMPI_PRIVATE_KEY=<copiar del servicio Django>
WOMPI_EVENTS_SECRET=<copiar del servicio Django>
WOMPI_INTEGRITY_SECRET=<copiar del servicio Django>
WOMPI_BASE_URL=https://production.wompi.co/v1

# Otras variables del servicio Django
# (copiar todas las demás que veas)
```

### 2.3 Cómo copiar variables del servicio Django

**Opción A: Copiar una por una**
1. Abre el servicio Django en otra pestaña
2. Ve a "Variables"
3. Copia cada variable manualmente

**Opción B: Usar Railway CLI (más rápido)**
```bash
# Instalar Railway CLI
npm i -g @railway/cli

# Login
railway login

# Listar variables del servicio Django
railway variables --service icfes-django-dashboard-production

# Copiar output y agregar al nuevo servicio
```

---

## 📋 Paso 3: Configurar Start Command

### 3.1 Ir a Settings
1. En el servicio **icfes-celery-worker**
2. Click en la pestaña **"Settings"**
3. Scroll hasta la sección **"Deploy"**

### 3.2 Configurar Start Command
1. Busca el campo **"Start Command"**
2. Ingresa exactamente:
```bash
celery -A config worker -l info --concurrency=2
```

### 3.3 Explicación del comando
- `celery -A config` → Usa la app Celery de config/celery.py
- `worker` → Modo worker (procesa tareas)
- `-l info` → Log level INFO
- `--concurrency=2` → 2 workers concurrentes (ajustar según plan Railway)

---

## 📋 Paso 4: Configurar Build (Opcional)

### 4.1 Custom Build Command (si es necesario)
1. En la misma sección "Deploy"
2. Busca **"Build Command"**
3. Si no está configurado, agregar:
```bash
pip install -r requirements/production.txt
```

**Nota:** Railway normalmente detecta esto automáticamente, pero si falla, agrégalo manualmente.

---

## 📋 Paso 5: Deploy del Worker

### 5.1 Trigger Deploy
1. Railway debería hacer deploy automáticamente
2. Si no, click en **"Deploy"** en la parte superior

### 5.2 Ver logs del deployment
1. Click en la pestaña **"Deployments"**
2. Click en el deployment activo (el que está corriendo)
3. Click en **"View Logs"**

### 5.3 Logs esperados (ÉXITO)
Busca estos mensajes en los logs:

```bash
✅ "Connected to redis://..."
✅ "celery@worker ready"
✅ "mingle: searching for neighbors"
✅ "mingle: all alone"
✅ "celery@worker ready."

# Tareas registradas:
✅ "reback.users.tasks.charge_monthly_subscriptions"
✅ "reback.users.tasks.send_email_notification"
```

---

## 📋 Paso 6: Verificar que Funciona

### 6.1 Verificar en logs del servicio Django
1. Ve al servicio **Django** (el principal)
2. Tab "Deployments" → Deployment activo → "View Logs"
3. Busca:
```bash
✅ "Connected to redis://..."
✅ "Cache backend initialized"
```

### 6.2 Probar una tarea Celery (desde Railway Shell)

**Opción 1: Railway CLI**
```bash
railway run python manage.py shell

# En el shell:
from reback.users.tasks import charge_monthly_subscriptions
result = charge_monthly_subscriptions.delay()
print(f"Task ID: {result.id}")
```

**Opción 2: Desde código**
Ejecuta una acción que dispare una tarea (ej: crear suscripción) y mira los logs del worker

### 6.3 Ver logs del worker procesando la tarea
1. Ve al servicio **icfes-celery-worker**
2. Tab "Deployments" → "View Logs"
3. Deberías ver:
```bash
✅ "Received task: reback.users.tasks.charge_monthly_subscriptions[...]"
✅ "Task reback.users.tasks.charge_monthly_subscriptions[...] succeeded"
```

---

## 📋 Paso 7: (Opcional) Crear Celery Beat

**Solo si quieres cobros recurrentes automáticos**

### 7.1 Crear otro servicio
1. Repetir Paso 1, pero nombrar: **`icfes-celery-beat`**

### 7.2 Copiar las mismas variables
Copiar todas las variables del servicio Django (igual que el worker)

### 7.3 Start Command diferente
```bash
celery -A config beat -l info
```

### 7.4 Logs esperados
```bash
✅ "beat: Starting..."
✅ "Scheduler: Sending due task charge-monthly-subscriptions"
```

---

## 🎯 Resumen de Servicios en Railway

Después de completar todo, deberías tener:

```
┌─────────────────────────────────────────────────┐
│         Railway Project: icfes-analytics         │
├─────────────────────────────────────────────────┤
│                                                  │
│  1. icfes-django-dashboard-production (Django)  │
│     - Web app principal                          │
│     - Gunicorn                                   │
│                                                  │
│  2. Redis                                        │
│     - Cache + Celery broker                      │
│                                                  │
│  3. icfes-celery-worker (NUEVO)                 │
│     - Procesa tareas asíncronas                  │
│                                                  │
│  4. icfes-celery-beat (OPCIONAL)                │
│     - Tareas periódicas (cobros recurrentes)     │
│                                                  │
│  5. PostgreSQL                                   │
│     - Metadata de Django                         │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## ⚠️ Troubleshooting

### Error: "ModuleNotFoundError: No module named 'celery'"
**Solución:**
- Verificar que `requirements/production.txt` tiene `celery==5.3.6`
- Forzar rebuild: Settings → "Redeploy"

### Error: "Connection refused to Redis"
**Solución:**
- Verificar que `REDIS_URL` está configurado en variables
- Verificar que servicio Redis está "Active"
- Verificar que `CELERY_BROKER_URL=${REDIS_URL}`

### Error: "No module named 'config.celery'"
**Solución:**
- Verificar que `config/celery.py` existe en el repo
- Verificar que `config/__init__.py` importa `celery_app`
- Hacer git pull y redeploy

### Worker no procesa tareas
**Solución:**
- Verificar logs del worker: ¿está "ready"?
- Verificar que Django y Worker usan el mismo `REDIS_URL`
- Probar crear tarea manualmente desde shell

---

## 📊 Métricas de Éxito

### Después de configurar todo:
- ✅ Worker logs muestran "celery@worker ready"
- ✅ Django logs muestran "Connected to redis"
- ✅ Tareas se procesan (ver logs del worker)
- ✅ Endpoints cacheados responden más rápido (5-10ms vs 20-30ms)

---

## 🎉 ¡Listo!

**Tiempo estimado:** 15-20 minutos

**Próximos pasos:**
1. ✅ Monitorear logs por 24 horas
2. ✅ Probar cobros recurrentes (si creaste Beat)
3. ✅ Implementar más endpoints con caché
4. ✅ Configurar Sentry para error tracking

---

**¿Necesitas ayuda?** Revisa los logs y busca los mensajes de ✅ éxito listados arriba.
