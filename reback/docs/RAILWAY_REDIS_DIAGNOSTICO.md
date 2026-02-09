# 🔍 Diagnóstico: Verificar Redis en Railway

## Cómo verificar si Redis está funcionando

### 1. Verificar que el servicio Redis existe

**En Railway Dashboard:**
1. Ve a tu proyecto
2. Busca un servicio llamado **"Redis"** o **"redis"**
3. Verifica que el estado sea **"Active"** (verde)

**Si NO ves el servicio Redis:**
- Necesitas crearlo: "+ New" → "Database" → "Add Redis"

---

### 2. Verificar que REDIS_URL está configurado

**En el servicio Django:**
1. Click en el servicio Django principal
2. Tab "Variables"
3. Busca la variable **REDIS_URL**

**Debería verse así:**
```
REDIS_URL=redis://default:xxxxx@redis.railway.internal:6379
```

**Si NO existe:**
- Railway crea automáticamente `REDIS_URL` cuando agregas Redis
- Si no está, necesitas agregar el servicio Redis primero

---

### 3. Verificar logs del servicio Django

**Buscar en logs:**
1. Servicio Django → "Deployments" → Deployment activo → "View Logs"
2. Buscar estos mensajes:

**✅ Redis funcionando:**
```
Connected to redis://redis.railway.internal:6379
Cache backend initialized successfully
```

**❌ Redis NO funcionando:**
```
Error connecting to Redis
Connection refused
redis.exceptions.ConnectionError
CACHES backend not configured
```

---

### 4. Verificar que el código está desplegado

**Verificar último commit:**
```bash
# En Railway logs, buscar:
"Building commit: 5257f85"
"feat: Implementar Redis para Celery y Django Cache"
```

**Si ves un commit anterior:**
- El código nuevo no se ha desplegado
- Necesitas hacer redeploy

---

## 🔧 Soluciones según el problema

### Problema 1: No existe servicio Redis

**Solución:**
1. Railway Dashboard → "+ New"
2. "Database" → "Add Redis"
3. Railway crea automáticamente el servicio
4. Esperar 1-2 minutos a que esté "Active"
5. Redeploy del servicio Django

---

### Problema 2: REDIS_URL no está configurado

**Solución:**
1. Verificar que servicio Redis existe
2. En servicio Django → "Variables"
3. Agregar manualmente:
```bash
REDIS_URL=${REDIS_URL}
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```
4. Redeploy

---

### Problema 3: Código antiguo desplegado

**Solución:**
```bash
# Verificar que el push se hizo
git log --oneline -1
# Debe mostrar: 5257f85 feat: Implementar Redis para Celery y Django Cache

# Si no, hacer push:
git push origin main

# En Railway, forzar redeploy:
# Settings → "Redeploy"
```

---

### Problema 4: Redis existe pero Django no conecta

**Posibles causas:**
- REDIS_URL mal configurado
- Servicio Redis no está en la misma red
- django-redis no instalado

**Solución:**
1. Verificar que `django-redis==5.4.0` está en requirements
2. Verificar logs de Redis (si hay errores)
3. Verificar que REDIS_URL apunta a `redis.railway.internal`

---

## 🧪 Test Rápido: Verificar Redis desde Railway Shell

**Usando Railway CLI:**
```bash
# Conectar a Railway
railway link

# Abrir shell en el servicio Django
railway run python manage.py shell

# Probar Redis
from django.core.cache import cache
cache.set('test_key', 'test_value', 60)
result = cache.get('test_key')
print(f"Cache test: {result}")  # Debe imprimir: Cache test: test_value
```

**Si falla:**
- Redis no está conectado
- Revisar REDIS_URL
- Revisar logs de Django

---

## 📊 Checklist de Diagnóstico

- [ ] Servicio Redis existe en Railway
- [ ] Servicio Redis está "Active" (verde)
- [ ] Variable REDIS_URL existe en servicio Django
- [ ] Código 5257f85 está desplegado
- [ ] Logs de Django muestran "Connected to redis"
- [ ] No hay errores de conexión en logs
- [ ] Test de caché funciona en shell

---

## 🚨 Si nada funciona

**Última opción: Recrear Redis**
1. Eliminar servicio Redis actual
2. Crear nuevo servicio Redis
3. Copiar nueva REDIS_URL
4. Actualizar variables en Django
5. Redeploy

---

## 💡 Próximo paso

**Dime qué ves en Railway:**
1. ¿Existe el servicio Redis? (Sí/No)
2. ¿Está "Active"? (Sí/No)
3. ¿Qué commit está desplegado? (número de commit)
4. ¿Qué errores ves en los logs? (copiar mensaje de error)

Con esa info te puedo ayudar específicamente.
