# Traffic Log Analytics (Railway -> Postgres -> Dashboard)

## Roadmap de evolucion

- Ver TODO operativo: docs/TODO_DASHBOARD_LOGS_RAILWAY_2026-03-06.md

---

## Objetivo

Construir observabilidad de tráfico web en producción para responder:

- cuánto tráfico humano vs bots está recibiendo el sitio
- qué rutas/colegios reciben más visitas
- qué campañas UTM están generando tráfico
- qué errores/404 y latencias están ocurriendo

Este módulo está separado del dominio ICFES analítico para no escribir en DuckDB.

---

## Arquitectura

Flujo principal:

1. Request entra a Django en Railway.
2. Middleware `TrafficIngestMiddleware` captura metadata de request/response.
3. Se clasifica bot y se extraen campos (`school_slug`, UTM).
4. Se inserta un registro en Postgres (`RailwayTrafficLog`).
5. Dashboard `/icfes/trafico/` consulta esa tabla y muestra métricas agregadas.

Opcional:

- Importación batch desde JSONL de Railway con `import_railway_logs` para histórico.

---

## Tabla principal

Nombre físico en Postgres:

- `icfes_dashboard_railwaytrafficlog`

Campos clave:

- `request_id` (unique)
- `timestamp`
- `method`, `path`, `host`, `http_status`
- `total_duration_ms`
- `client_ua`, `src_ip`
- `bot_category`
- `school_slug`
- `utm_source`, `utm_medium`, `utm_campaign`

Categorías de bot:

- `human_or_other`
- `seo_bot`
- `ai_bot`
- `social_bot`
- `other_bot`
- `unknown`

---

## Flags de configuración

En settings/env:

- `TRAFFIC_ANALYTICS_ENABLED`
- `TRAFFIC_ANALYTICS_DEBUG_LOGS`

Comportamiento recomendado:

- Local: `TRAFFIC_ANALYTICS_ENABLED=False`
- Producción: `TRAFFIC_ANALYTICS_ENABLED=True`
- Diagnóstico puntual: `TRAFFIC_ANALYTICS_DEBUG_LOGS=True`

Con debug activo, logs esperados:

- `traffic_ingest startup enabled=... debug=...`
- `traffic_ingest captured_count=... status=... path=... bot=...`

---

## Artefactos involucrados

Modelado y migraciones:

- `icfes_dashboard/models.py`
- `icfes_dashboard/migrations/0007_railwaytrafficlog.py`

Captura realtime:

- `reback/middleware/traffic_ingest.py`
- `icfes_dashboard/traffic_utils.py`
- `config/settings/base.py` (middleware + flags)

Dashboard:

- `icfes_dashboard/traffic_views.py`
- `icfes_dashboard/templates/icfes_dashboard/pages/dashboard-traffic.html`
- `icfes_dashboard/urls.py`
- `reback/templates/partials/main-nav.html`

Admin:

- `icfes_dashboard/admin.py`

Ingesta batch histórica:

- `icfes_dashboard/management/commands/import_railway_logs.py`

---

## Dashboard disponible

Ruta:

- `/icfes/trafico/`

Acceso:

- usuario autenticado + superuser
- requiere `TRAFFIC_ANALYTICS_ENABLED=True`

Métricas incluidas:

- requests totales
- 2xx/3xx/4xx/5xx
- avg y p95 de latencia
- top paths
- top slugs de colegios
- top 404
- top AI bots / SEO bots
- top campañas UTM
- rutas malformadas y placeholders sin reemplazar

---

## Operación en producción

1) Verificar variables en Railway:

- `TRAFFIC_ANALYTICS_ENABLED=True`
- `TRAFFIC_ANALYTICS_DEBUG_LOGS` según necesidad

2) Verificar migraciones:

```bash
uv run python manage.py showmigrations icfes_dashboard
```

3) Verificar conteo de tabla:

```bash
uv run python manage.py shell -c "from icfes_dashboard.models import RailwayTrafficLog as T; print(T.objects.count())"
```

4) Validar middleware cargado:

```bash
uv run python manage.py shell -c "from django.conf import settings; print([m for m in settings.MIDDLEWARE if 'traffic_ingest' in m])"
```

5) Revisar dashboard:

- `https://www.icfes-analytics.com/icfes/trafico/`

---

## Ingesta batch (histórico)

Si necesitas cargar histórico de logs exportados:

```bash
uv run python manage.py import_railway_logs --input /path/logs.jsonl
```

Para ejecutar aunque el flag esté en false:

```bash
uv run python manage.py import_railway_logs --input /path/logs.jsonl --allow-disabled
```

---

## Troubleshooting rápido

Caso: tabla vacía, hay tráfico en sitio

Checklist:

1. Confirmar nombre exacto del flag: `TRAFFIC_ANALYTICS_ENABLED`.
2. Confirmar deploy activo con commits de traffic ingest.
3. Buscar en logs línea de startup del middleware.
4. Confirmar middleware presente en `settings.MIDDLEWARE`.
5. Confirmar `count()` de `RailwayTrafficLog`.

Caso: warning "models have changes not reflected in migration"

- Se estabilizaron nombres de índices en `RailwayTrafficLog` para evitar drift.

---

## Decisiones de diseño

- DuckDB sigue read-only para analítica ICFES.
- Logs operativos van a Postgres (separación de responsabilidades).
- Middleware tolerante a fallas: no rompe requests si falla inserción.
- Instrumentación de debug controlada por flag.


