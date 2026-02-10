# 🔧 Ejecutar Migraciones de django_celery_beat en Railway

## Problema
Las migraciones de `django_celery_beat` necesitan ejecutarse en Railway para crear las tablas necesarias.

---

## ✅ Solución 1: Forzar Redeploy (Más Fácil)

Railway ejecuta migraciones automáticamente en cada deploy. Solo necesitas forzar un nuevo deployment:

### Pasos:
1. **Railway Dashboard** → Tu proyecto
2. **Servicio Django** → Tab "Settings"
3. Scroll hasta **"Service"**
4. Click en **"Redeploy"** o **"Restart"**

Railway ejecutará automáticamente:
```bash
python manage.py migrate --settings=config.settings.railway
```

### Verificar en logs:
1. Tab "Deployments" → Deployment activo → "View Logs"
2. Buscar:
```
Running migrations:
  Applying django_celery_beat.0001_initial... OK
  Applying django_celery_beat.0002_auto_20161118_0346... OK
  ...
```

---

## ✅ Solución 2: Ejecutar Manualmente con Railway CLI

Si el redeploy no funciona, ejecuta las migraciones manualmente:

### Pasos:
```bash
# 1. Asegúrate de estar en el directorio del proyecto
cd c:\proyectos\www\reback

# 2. Ejecutar migraciones en Railway (sin usar settings locales)
railway run --service icfes-django-dashboard-production bash -c "python manage.py migrate"
```

**Nota:** Railway automáticamente usa `config.settings.railway` en producción.

---

## ✅ Solución 3: Desde Railway Dashboard (Sin CLI)

Si no tienes Railway CLI o prefieres no usarlo:

### Opción A: Agregar comando temporal
1. Railway Dashboard → Servicio Django → "Settings"
2. "Deploy" → "Start Command"
3. **Temporal** cambiar a:
```bash
python manage.py migrate --settings=config.settings.railway && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
```
4. Guardar (Railway redeploya automáticamente)
5. **Importante:** Después volver al comando original en `railway.json`

### Opción B: Usar Railway Shell (si está disponible)
1. Railway Dashboard → Servicio Django
2. Si hay opción "Shell" o "Console"
3. Ejecutar:
```bash
python manage.py migrate
```

---

## 🔍 Verificación

Después de ejecutar las migraciones, verifica que funcionaron:

### En los logs deberías ver:
```
Running migrations:
  Applying django_celery_beat.0001_initial... OK
  Applying django_celery_beat.0002_auto_20161118_0346... OK
  Applying django_celery_beat.0003_auto_20161209_0049... OK
  ...
  Applying django_celery_beat.0018_improve_crontab_helptext... OK
```

### O si ya estaban aplicadas:
```
Running migrations:
  No migrations to apply.
```

---

## ⚠️ Importante

Las migraciones de `django_celery_beat` crean estas tablas:
- `django_celery_beat_periodictask`
- `django_celery_beat_intervalschedule`
- `django_celery_beat_crontabschedule`
- `django_celery_beat_solarschedule`
- `django_celery_beat_clockedschedule`

Estas tablas son necesarias para que Celery Beat funcione correctamente.

---

## 📋 Recomendación

**Usa Solución 1** (Redeploy) - Es la más simple y segura.

1. Railway Dashboard → Servicio Django → Settings → "Redeploy"
2. Esperar 2-3 minutos
3. Ver logs para confirmar migraciones

**Tiempo estimado:** 3-5 minutos
