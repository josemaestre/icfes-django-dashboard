# TODO Web - Dashboard de Logs Railway (Observabilidad + SEO)
**Fecha:** 2026-03-06  
**Estado:** Plan de implementacion aterrizado para ejecutar en el repo `www/reback` sin tocar `raw`.

---

## Objetivo
Evolucionar `/icfes/trafico/` de visor basico de logs a dashboard operativo que responda en minutos:

- que esta pasando ahora
- que cambio vs ayer
- que paginas estan fallando o lentas
- que bots estan entrando y como les va
- que rutas raras aparecieron hoy

**Restriccion clave:** mantener `RailwayTrafficLog` como base de ingesta existente, sin borrar ni romper lo ya desplegado.

---

## Alcance tecnico

### Datos
- Mantener tabla actual `icfes_dashboard_railwaytrafficlog` como fuente principal.
- Agregar capa curada por SQL/ORM para campos derivados (sin tocar pipeline raw existente).

### UI
- Reorganizar el dashboard en 4 tabs:
1. Executive
2. Performance
3. SEO/Crawlers
4. Errors/Investigation

### Operacion
- Agregar alertas simples (rojas y amarillas) dentro del panel y lista de anomalias del dia.

---

## Fase 0 - Baseline y guardrails (P0)

### Tareas
- [ ] Congelar baseline actual de metricas y consultas en `docs/TRAFFIC_LOG_ANALYTICS.md`.
- [ ] Confirmar que el endpoint actual `/icfes/trafico/` sigue operativo con `TRAFFIC_ANALYTICS_ENABLED=True`.
- [ ] Agregar tests de humo para evitar regresion del dashboard existente.

### Archivos a tocar
- `docs/TRAFFIC_LOG_ANALYTICS.md`
- `icfes_dashboard/tests/` (nuevo modulo de tests)

### Criterio de cierre
- Dashboard actual sigue renderizando y tests de humo pasan.

---

## Fase 1 - Capa curada de campos derivados (P0)

### Objetivo
Evitar reescribir logica en cada widget creando campos derivados reutilizables.

### Campos derivados minimos
- `event_date`
- `event_hour`
- `minute_bucket`
- `status_family` (`2xx`, `3xx`, `4xx`, `5xx`)
- `is_error`
- `is_slow`
- `is_bot`
- `bot_type` (Googlebot, AdsBot-Google, Bingbot, Amazonbot, Meta, Facebook, LinkedIn, Other bot, Human)
- `path_group` (home, colegio, municipio, departamento, rankings, social-card, email-graphs, sitemaps, robots, admin, trafico/dashboard, static/media, unknown)
- `path_depth`
- `slug`
- `department_slug`
- `municipality_slug`
- `is_social_card`
- `is_html_page`
- `is_sitemap`
- `is_suspicious_path`

### Implementacion sugerida
- Opcion A (rapida): anotaciones en queryset + utilidades de parseo en Python.
- Opcion B (escalable): vista SQL/materialized view en Postgres y lectura desde Django.

### Archivos a tocar
- `icfes_dashboard/traffic_utils.py`
- `icfes_dashboard/traffic_views.py`
- `icfes_dashboard/management/commands/` (si se crea comando de refresh)
- `icfes_dashboard/models.py` (solo si se define modelo para vista SQL)

### Criterio de cierre
- Existe una capa unica de derivacion usada por todas las secciones del dashboard.

---

## Fase 2 - Executive tab (P0)

### Widgets
- [ ] Requests totales (5 min, 1h, 24h)
- [ ] Error rate (%4xx y %5xx)
- [ ] p50, p95, p99 de `total_duration_ms`
- [ ] Top status codes
- [ ] Bots vs humanos
- [ ] Top endpoints por trafico
- [ ] Top endpoints por lentitud

### Semaforos (MVP)
- [ ] Verde/Amarillo/Rojo con reglas:
  - rojo: `5xx > 1%`
  - rojo: `p95 > 1500 ms`
  - amarillo: `404 > 3x` promedio reciente

### Archivos a tocar
- `icfes_dashboard/traffic_views.py`
- `icfes_dashboard/templates/icfes_dashboard/pages/dashboard-traffic.html`

### Criterio de cierre
- En 10 segundos se puede identificar estado general de salud.

---

## Fase 3 - Performance tab (P0)

### Graficos/tablas
- [ ] Requests por minuto
- [ ] p50/p95/p99 por minuto
- [ ] Duracion por `path_group`
- [ ] `txBytes` promedio por endpoint (si el dato existe en log)

### Cortes obligatorios
- `/`
- `/icfes/colegio/...`
- `/icfes/departamento/.../municipio/...`
- `/social-card/...`
- `/sitemap...`
- `/robots.txt`
- `/static/...`

### Criterio de cierre
- Se identifica rapidamente si la degradacion es HTML dinamico, social cards, estaticos o crawler burst.

---

## Fase 4 - SEO/Crawlers tab (P1)

### Bloques
- [ ] Requests por bot
- [ ] Top URLs rastreadas por bot
- [ ] Status codes por bot
- [ ] p95 por bot
- [ ] Paginas nuevas descubiertas por bot
- [ ] Profundidad de crawl (home -> departamento -> municipio -> colegio)

### Detectores clave
- [ ] Caida brusca de crawl en paginas de municipio/colegio
- [ ] Meta/Facebook disparando social previews
- [ ] Bot especifico con mala experiencia (p95 alto o 4xx/5xx altos)

### Criterio de cierre
- Panel muestra comportamiento de Google-family, Bing y social bots con comparativo diario.

---

## Fase 5 - Errors/Investigation tab (P0)

### Tablas minimas
- [ ] Top 404
- [ ] Top 500
- [ ] Endpoints mas lentos
- [ ] Paths sospechosos
- [ ] `upstream_errors` no vacios (si existe el campo)
- [ ] Spikes por IP y User-Agent

### Reglas de rareza
- [ ] `path` contiene `{{` o `}}`
- [ ] hits a `/.well-known/*`
- [ ] hits a `wp-admin`, `phpmyadmin`, `.env`, `xmlrpc.php`
- [ ] rutas nuevas del dia
- [ ] user agents nuevos del dia

### Filtro de investigacion
- [ ] rango de tiempo
- [ ] status code
- [ ] bot/humano
- [ ] categoria de path
- [ ] slug/colegio
- [ ] municipio/departamento
- [ ] latencia minima
- [ ] IP

### Criterio de cierre
- El panel permite responder preguntas de incidente sin ir al raw log.

---

## Fase 6 - Alertas operativas (P0)

### Rojas
- [ ] cualquier 500 en paginas SEO criticas
- [ ] `p95 > 2s` en `/icfes/colegio/`
- [ ] `p95 > 2.5s` en `/social-card/`
- [ ] 404 en `sitemap.xml` o `robots.txt`

### Amarillas
- [ ] subida 404 por URL > 3x
- [ ] subida abrupta en endpoint no esperado
- [ ] diferencia grande entre `total_duration` y `upstream` (si aplica)

### Entrega
- [ ] Banner/seccion de alertas dentro del dashboard
- [ ] (opcional) notificacion por correo/Slack en segunda iteracion

### Criterio de cierre
- Alertas visibles en dashboard con timestamp y razon de disparo.

---

## Fase 7 - Hardening tecnico (P1)

### Tareas
- [ ] Optimizar queries pesadas (indices por `timestamp`, `path`, `http_status`, `bot_category`).
- [ ] Evitar `count()` repetidos con agregaciones unificadas.
- [ ] Limitar scans para p95/p99 (sampling controlado o SQL percentile).
- [ ] Paginacion para tabla raw filtrable.

### Criterio de cierre
- Dashboard carga en tiempo aceptable aun con crecimiento de logs.

---

## MVP recomendado (orden de ejecucion)
1. [ ] Executive: requests, p95, status, bots/humanos
2. [ ] Performance: requests por minuto + top lentos
3. [ ] Errors: top 404, top 500, paths sospechosos
4. [ ] SEO: bots por hora + top URLs crawl
5. [ ] Investigation: tabla filtrable basica

**Objetivo MVP:** visibilidad operativa real en una sola pantalla util para daily ops.

---

## Mapa de implementacion por archivo
- [ ] `icfes_dashboard/traffic_views.py`: nuevas consultas agregadas por tab + filtros
- [ ] `icfes_dashboard/traffic_utils.py`: clasificacion bot/path y parseo de slugs
- [ ] `icfes_dashboard/templates/icfes_dashboard/pages/dashboard-traffic.html`: tabs + tarjetas + tablas
- [ ] `icfes_dashboard/urls.py`: soportar query params por tab/filtro
- [ ] `icfes_dashboard/tests/test_traffic_dashboard.py` (nuevo): smoke + reglas de clasificacion + anomalias
- [ ] `docs/TRAFFIC_LOG_ANALYTICS.md`: actualizar con arquitectura final de tabs y alertas

---

## Riesgos y mitigacion
- Riesgo: consultas lentas por volumen de logs.
  - Mitigacion: agregaciones por ventana de tiempo e indices.
- Riesgo: clasificacion incompleta de bots.
  - Mitigacion: tabla/mapeo de UA versionable + categoria `other_bot`.
- Riesgo: ruido por alertas excesivas.
  - Mitigacion: umbrales iniciales conservadores y ajuste semanal.

---

## Definicion de Done
- [ ] Dashboard dividido en 4 tabs funcionales.
- [ ] KPIs clave visibles (requests, p95, 4xx/5xx, bots/humanos).
- [ ] Seccion de anomalias (paths nuevos/sospechosos, placeholders, top 404/500).
- [ ] Alertas rojas/amarillas con reglas documentadas.
- [ ] Tests basicos del dashboard y utilidades de clasificacion.
- [ ] Documentacion actualizada en `docs/TRAFFIC_LOG_ANALYTICS.md`.
