# Arquitectura de Seguridad — ICFES Analytics

**Última actualización**: 2026-03-26
**Entorno**: Django 5.1 + Railway + Redis

---

## 1. Stack de Middleware (orden de ejecución)

El middleware corre en el orden definido en `config/settings/railway.py`. Cada capa intercepta
antes de llegar a las vistas. El orden importa: las capas de seguridad van primero.

```
Request entrante
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. CanonicalHostMiddleware       → 301 *.railway.app → dominio │
│  2. SlashNormalizeMiddleware      → normaliza // dobles         │
│  3. ScannerBlockMiddleware        → bloquea probes de scanners  │
│  4. BotBanMiddleware              → honeypot + ban dinámico     │
│  5. RateLimitMiddleware           → 40 req/min por IP           │
│  6. GZipMiddleware                → compresión                  │
│  7. SecurityMiddleware (Django)   → HSTS, headers               │
│  8. WhiteNoiseMiddleware          → archivos estáticos          │
│  9. PublicCacheMiddleware         → Cache-Control para CDN      │
│ 10. SessionMiddleware             → sesiones                    │
│ 11. CommonMiddleware              → trailing slash              │
│ 12. CsrfViewMiddleware            → CSRF tokens                 │
│ 13. AuthenticationMiddleware      → user.is_authenticated       │
│ 14. MessagesMiddleware            │                             │
│ 15. XFrameOptionsMiddleware       → X-Frame-Options             │
│ 16. AccountMiddleware (allauth)   │                             │
│ 17. AutoCreateAdminMiddleware     │                             │
│ 18. ErrorLoggingMiddleware        → log 4xx/5xx a archivo       │
│ 19. PerfLoggingMiddleware         → log path/ms/cache           │
│ 20. CacheDebugHeaderMiddleware    → header X-Cache-Status       │
│ 21. TrafficIngestMiddleware       → graba tráfico a PostgreSQL  │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
    View / URL resolver
```

Archivos: `reback/middleware/`

---

## 2. Capas de Defensa

### 2.1 Canonical Host Redirect
**Archivo**: `reback/middleware/canonical_host.py`

Railway expone dos URLs: la interna `*.up.railway.app` y el dominio custom. Crawlers y bots
que golpean la URL interna generan contenido duplicado y tráfico de egreso innecesario.

- Redirige **301** cualquier host distinto a `www.icfes-analytics.com` → dominio canónico
- Excepción: `/health/` — Railway hace health probe contra IP interna, no el dominio

```python
CANONICAL_HOST = "www.icfes-analytics.com"  # config/settings/railway.py
```

---

### 2.2 Scanner Block
**Archivo**: `reback/middleware/security.py`

Bloquea probes de vulnerability scanners antes de que toquen ninguna vista ni la DB.
Responde **404** (no 403) para no confirmar que el servidor existe y tiene Django.

**Patrones bloqueados** (regex):
| Patrón | Amenaza |
|--------|---------|
| `*.php`, `*.asp`, `*.jsp` | Probes de CMS/servidor incorrecto |
| `/.env`, `/.aws` | Robo de credenciales |
| `/.git/` | Exposición de código fuente |
| `/wp-admin`, `/wp-login` | WordPress exploitation |
| `/phpmyadmin` | MySQL admin exposure |
| `/xmlrpc.php` | WordPress brute force |
| `/cgi-bin/` | CGI injection |
| `/etc/passwd` | Unix credential probe |

---

### 2.3 Bot Ban (Honeypot + Señales)
**Archivo**: `reback/middleware/bot_ban.py`

Sistema de dos capas respaldado por Redis.

#### Capa 0 — Crawlers legítimos (exentos)
Los crawlers que alimentan SEO y redes sociales **nunca** son baneados. Se identifican por
User-Agent y pasan directo a la vista sin ninguna verificación adicional.

Whitelisted: `googlebot`, `bingbot`, `bingpreview`, `meta-externalagent`,
`facebookexternalhit`, `twitterbot`, `linkedinbot`, `whatsapp`, `telegrambot`,
`applebot`, `duckduckbot`, `yandexbot`, `baiduspider`, `slurp`, `ia_archiver`,
`google-inspectiontool`, `google-safety`, `adsbot-google`

#### Capa 1 — Honeypot
Una URL oculta (`/icfes/data-export/`) está embebida en todas las páginas públicas con
`display:none`. Los humanos nunca la ven ni la hacen clic. Un bot que parsea HTML la sigue.

```html
<!-- en base.html y 9 templates standalone -->
<span style="display:none" aria-hidden="true">
  <a href="/icfes/data-export/" tabindex="-1"></a>
</span>
```

- Visita al honeypot → ban **inmediato** de 24 horas
- Redis key: `botban:{ip}` → valor: `"honeypot"`

#### Capa 2 — Señales de mal comportamiento
Las respuestas **404** en rutas no-assets acumulan señales por IP en Redis.

```
6 señales en 60 segundos → ban automático de 24 horas
Redis key: botsig:{ip} → counter (TTL: 60s rolling)
```

Rutas excluidas de señales: `/static/`, `/media/`, `/favicon`, `/robots.txt`, `/sitemap`

#### Parámetros configurables

| Parámetro | Valor | Significado |
|-----------|-------|-------------|
| `SIGNAL_THRESHOLD` | 6 | Señales antes del ban automático |
| `SIGNAL_WINDOW` | 60 s | Ventana deslizante |
| `BAN_DURATION` | 86400 s | Duración del ban (24 h) |

---

### 2.4 Rate Limiting
**Archivo**: `reback/middleware/rate_limit.py`

Limita requests por IP en rutas atractivas para scrapers. Responde **429 Too Many Requests**.
Implementado con `cache.add()` atómico en Redis (fail-open si Redis cae).

**Rutas limitadas**:
- `/icfes/colegio/`
- `/icfes/cuadrante/`
- `/icfes/dashboard/`
- `/api/`

**Umbral**: 40 requests por IP en 60 segundos.

Existe también `_public_api_rate_limit()` como decorator en algunos endpoints específicos
(`/icfes/api/colegios/`, `/icfes/api/estadisticas/`, `/icfes/api/colegios/destacados/`) con
límites propios (60–120 req/min).

---

### 2.5 IP Source — Anti-Spoofing
**Archivo**: `reback/middleware/traffic_ingest.py`

Railway agrega el IP real del cliente como el **último** entry en `X-Forwarded-For`. Los
clientes pueden falsificar las entradas anteriores (enviar `XFF: 127.0.0.1`). La extracción
correcta usa el entry más a la **derecha**:

```python
# CORRECTO — rightmost entry, agregado por Railway (no falsificable)
xff.split(",")[-1].strip()

# INCORRECTO — leftmost entry, controlado por el cliente
xff.split(",")[0].strip()
```

Todos los middlewares de seguridad (`bot_ban.py`, `rate_limit.py`) usan el mismo patrón.

---

## 3. Configuración Django Security (HTTPS)

Definido en `config/settings/railway.py`:

| Setting | Valor | Efecto |
|---------|-------|--------|
| `DEBUG` | `False` (default) | Sin stack traces en producción |
| `SECURE_PROXY_SSL_HEADER` | `HTTP_X_FORWARDED_PROTO: https` | Django detecta HTTPS detrás de proxy |
| `SECURE_SSL_REDIRECT` | `True` | Redirect HTTP → HTTPS (excepto `/health/`) |
| `SESSION_COOKIE_SECURE` | `True` | Cookie de sesión solo por HTTPS |
| `CSRF_COOKIE_SECURE` | `True` | Cookie CSRF solo por HTTPS |
| `SECURE_HSTS_SECONDS` | `60` | HSTS header (conservador, escalar a 31536000) |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | HSTS aplica a subdominios |
| `SECURE_HSTS_PRELOAD` | `True` | Permite inclusión en listas HSTS preload |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | `X-Content-Type-Options: nosniff` |
| `X_FRAME_OPTIONS` | `DENY` (Django default) | Previene clickjacking |

---

## 4. Autenticación de Endpoints

La mayoría de la API es **pública** (datos educativos de libre acceso). Los endpoints que
requieren login son los de funcionalidades premium y ML avanzado:

| Grupo | Auth | Ejemplos |
|-------|------|---------|
| Datos públicos ICFES | Sin auth | `/icfes/api/colegio/*/historico/`, `/icfes/api/brechas/` |
| Dashboard social | `@login_required` | `/icfes/api/social/*` |
| ML avanzado | `@login_required` | `/icfes/api/ml/*` (riesgo, SHAP, palancas) |
| Exportaciones | `@login_required` | `/icfes/export/*/pdf/`, `/icfes/export/*/csv/` |

Ver inventario completo en `docs/INVENTARIO_ENDPOINTS_Y_CONTROLES.md`.

---

## 5. Deudas Técnicas de Seguridad

| # | Severidad | Problema | Archivo | Fix estimado |
|---|-----------|---------|---------|-------------|
| 1 | 🟠 ALTA | SQL f-strings en endpoints legacy | `views_school_endpoints.py` | Auditar + params-safe (4 h) |
| 2 | 🟡 MEDIA | `SECURE_HSTS_SECONDS = 60` muy bajo | `settings/railway.py:110` | Escalar a 31536000 después de validar |
| 3 | 🟡 MEDIA | Sin alertas automáticas de bans | `bot_ban.py` | Integrar con Slack/email on ban threshold |
| 4 | 🟡 MEDIA | Rate limit solo por middleware, no por user | `rate_limit.py` | Agregar rate limit por usuario autenticado |
| 5 | 🟢 BAJA | Admin URL expuesta en default | `settings/railway.py:160` | Cambiar a UUID aleatorio |

---

## 6. Historial de Cambios

| Fecha | Cambio | Commit |
|-------|--------|--------|
| 2026-03-26 | Whitelist crawlers legítimos en BotBan | `7c286dd` |
| 2026-03-26 | BotBanMiddleware: honeypot + ban dinámico por señales 404 | `e4e9f02` |
| 2026-03-26 | RateLimitMiddleware: 40 req/min en rutas scrapeables | `fdfe3ad` |
| 2026-03-26 | ScannerBlockMiddleware: bloquea probes de scanners | `e4af4db` |
| 2026-03-26 | Fix IP spoofing: usar rightmost XFF entry | `e4af4db` |
