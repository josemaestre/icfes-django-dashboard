# Evaluación de Arquitectura y Producto — ICFES Analytics Platform
**Fecha:** 1 de marzo de 2026
**Autor:** José Maestre
**Tipo:** Evaluación técnica y de producto — documento vivo

---

## TL;DR

> Producto real, en producción, con datos únicos, pagos implementados y una arquitectura técnica que supera la mayoría de startups educativos de Colombia. El cuello de botella no es técnico: es comercial.

---

## 1. Arquitectura de Infraestructura — Estado Real

### Diagrama completo

```
┌─────────────────────────────────────────────────────────────────┐
│  EC2 r6i.2xlarge (ON-DEMAND — solo cuando hay datos nuevos)     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  dbt (Bronze → Silver → Gold)                           │   │
│  │  - 17.7M registros, 29 años (1995–2024)                 │   │
│  │  - 26+ tablas Gold optimizadas                          │   │
│  │  - 3 modelos ML embebidos                               │   │
│  └───────────────────────────────┬─────────────────────────┘   │
│  Costo: ~$0.50/hora | ~$1.50/mes │ (3h uso total, 2x/año)      │
└──────────────────────────────────┼──────────────────────────────┘
                                   ↓ Upload prod.duckdb (3.5GB)
                         ┌─────────────────────┐
                         │  AWS S3             │
                         │  - prod.duckdb      │
                         │  - Versionado ON    │
                         │  - Costo: ~$0.15/mes│
                         └──────────┬──────────┘
                                    ↓ Download al iniciar / actualizar
┌───────────────────────────────────────────────────────────────┐
│  Railway — icfes-analytics.com                                │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Django (Python 3.12 + Django 5.0)                      │ │
│  │  - 7 dashboards analíticos                              │ │
│  │  - ~10K páginas de colegios                             │ │
│  │  - Claude API (recomendaciones por colegio)             │ │
│  │  - Wompi + Stripe (pagos Colombia + internacional)      │ │
│  │  - Suscripciones: Free / Basic / Premium / Enterprise   │ │
│  └─────────┬──────────────┬──────────────┬─────────────────┘ │
│            │              │              │                     │
│   ┌────────▼──────┐ ┌─────▼──────┐ ┌───▼──────────────────┐ │
│   │  PostgreSQL   │ │   Redis    │ │  DuckDB (volume)     │ │
│   │  (auth +      │ │  (caché    │ │  prod.duckdb 3.5GB   │ │
│   │   sesiones +  │ │   HTML +   │ │  read-only           │ │
│   │   suscripcio- │ │   queries) │ │  analytics           │ │
│   │   nes + pagos)│ │  105+ keys │ │  <100ms queries      │ │
│   └───────────────┘ └────────────┘ └──────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### Separación OLTP / OLAP — por qué es la decisión correcta

| Base de datos | Propósito | Justificación |
|---------------|-----------|---------------|
| **PostgreSQL** | Auth, usuarios, suscripciones, pagos, sesiones | Escrituras frecuentes, integridad ACID, relaciones Django |
| **DuckDB** | Todas las queries analíticas de los dashboards | Read-only, columnar, 100x más rápido que PG para agregaciones |
| **Redis** | Caché de HTML y queries costosas | Elimina queries repetidas, escala sin cambiar infraestructura |

Esta separación es la que usan empresas como Metabase, Redash y la mayoría de plataformas analytics maduras. No es sobreingeniería — es la arquitectura correcta para este caso de uso.

---

## 2. Análisis de Cada Capa

### 2.1 Pipeline de Datos (EC2 + dbt + DuckDB)

**Calificación: 9/10**

**Lo que está bien:**
- Medallion architecture (Bronze/Silver/Gold) correctamente implementada
- Pre-cómputo agresivo: `fct_indicadores_desempeno` (335K filas) elimina scans de 17.7M filas
- `fact_icfes_analytics` como tabla maestra (17.7M filas, 90+ columnas)
- 3 modelos ML embebidos en la capa Gold:
  - `fct_riesgo_colegios` — predicción de declive (XGBoost)
  - `fct_potencial_ingles` — potencial en inglés por colegio
  - `fct_ml_clusters_transformadores` — clustering de colegios que mejoran
- EC2 on-demand: se prende solo cuando hay datos nuevos (~$1.50/mes, no $363)
- Política 0-views: todo materializado como table, no views

**Deuda técnica menor:**
- `views.py` tiene 3.300+ líneas (God File en progreso de refactor)
- `dbt test` ya optimizado (de 2h a 10-15 min)
- CI/CD no automatizado — deploy es manual por ahora (aceptable para 2x/año)

### 2.2 Capa Web (Django + Railway)

**Calificación: 8/10**

**Dashboards disponibles:**
1. Dashboard ICFES principal (KPIs nacionales, evolución histórica)
2. Brecha Educativa (análisis de inequidad)
3. Historia de la Educación (29 años)
4. Inteligencia Educativa (análisis profundo)
5. Resumen Ejecutivo
6. Bilingüismo/Inglés (dashboard especializado con ML)
7. Mi Colegio (personalización por sesión)

**Funcionalidades por colegio (~10K colegios):**
- Perfil completo con histórico de 29 años
- Comparación contextual (vs departamento, vs sector, vs cluster)
- Fortalezas y debilidades por materia
- Evolución de niveles de desempeño (stacked bar histórico)
- Indicadores de excelencia pre-calculados
- Predicción de riesgo (ML)
- Recomendaciones generadas con Claude API (Anthropic)
- Landing pages individuales por slug (`/colegio/<slug>/`)

**Autenticación y acceso:**
- `django-allauth` — login, registro, email verification
- 4 tiers de suscripción: Free / Basic / Premium / Enterprise
- Decoradores de paywall: `@subscription_required(tier='premium')`
- `QueryLog` para auditoría de uso por usuario

### 2.3 Redis — Caché en Producción

**Calificación: 9/10 — Sorpresa positiva**

Redis no está "desplegado sin usar" — está activo con 105+ páginas de keys:

```
icfes:1:html:school_landing_simple:v1:<slug>   → HTML cacheado por colegio
views.decorators.cache.cache_page..GET.<hash>  → Vistas Django cacheadas
```

TTLs entre 2.000s (~30 min) y 18.000s (~5 horas). Esto significa:
- Las páginas de colegios más consultadas se sirven desde RAM, no desde DuckDB
- El patrón de cache key incluye versión (`v1`) — invalidación controlada
- Escala transparente: más usuarios = más hits en caché, no más load en DuckDB

### 2.4 Pagos

**Calificación: 7/10 — Implementado, falta activar**

- **Wompi**: gateway colombiano (PSE, tarjetas, Nequi) — backend completo, pendiente cuenta
- **Stripe**: internacional — implementado
- Modelos Django de suscripción: `SubscriptionPlan`, `UserSubscription`, `QueryLog`
- Precios en COP definidos:

| Plan | Precio/mes | Límite queries | Años de datos |
|------|-----------|----------------|---------------|
| Free | $0 | 10/día | 3 |
| Basic | $39.900 | 100/día | 10 |
| Premium | $100.000 | Ilimitado | 29 |
| Enterprise | $500.000 | Ilimitado | 29 + soporte |

---

## 3. Costos de Infraestructura

| Componente | Costo/mes | Notas |
|------------|-----------|-------|
| EC2 r6i.2xlarge | ~$1.50 | On-demand, ~3h/mes uso total |
| EBS 100GB | ~$10.00 | Almacenamiento persistente |
| S3 Storage | ~$0.15 | 3.5GB prod.duckdb |
| Railway (Django + Postgres + Redis) | ~$20-25 | 3 servicios |
| **TOTAL** | **~$32-37/mes** | |

**Break-even con 1 cliente Premium** ($100.000 COP ≈ $25 USD/mes).
**Break-even cómodo con 2 clientes Basic** ($39.900 COP c/u).

---

## 4. Evaluación como Producto

### 4.1 ¿Qué tiene que nadie más tiene en Colombia?

1. **29 años de datos ICFES estructurados** (1995–2024) en un único modelo de datos consistente. El ICFES cambió formato varias veces — Bronze/Silver resuelve eso.
2. **ML sobre datos educativos colombianos**: riesgo de declive, potencial en inglés, clustering de colegios transformadores. No existe nada similar público.
3. **Perfil granular de ~10.000 colegios** con trayectoria, comparación contextual y recomendaciones IA.
4. **Datos de contacto**: 24.920 colegios únicos en DB con 82% emails, 84% teléfonos, 90% rectores.

### 4.2 Competencia directa

| Plataforma | Qué tiene | Qué le falta vs este producto |
|------------|-----------|-------------------------------|
| Portal ICFES oficial | Resultados por colegio/estudiante | Sin tendencias, sin comparaciones, sin ML |
| Tablero MEN (Tableau) | Vista regional básica | Sin perfil de colegio, sin predicciones |
| Consultoras educativas | Informes PDF personalizados | Sin acceso online, $5M-$15M COP por informe |
| Nadie más | — | — |

### 4.3 Segmentos de mercado

**Segmento A — Colegios privados** (12.208 en Colombia)
- Pain: justificar matrícula, competir por estudiantes, mejorar ranking
- WTP: $39.900–$100.000 COP/mes
- Ciclo de venta: 2-4 semanas, decisión del rector

**Segmento B — Secretarías de Educación** (~300 entidades)
- Pain: supervisar territorio, identificar colegios en riesgo, reportar al MEN
- WTP: $5M–$30M COP/mes (presupuesto público)
- Ciclo de venta: 3-12 meses, proceso contractual SECOP

**Segmento C — Fundaciones y ONG educativas**
- Pain: medir impacto de programas, identificar dónde intervenir
- WTP: $2M–$10M COP por acceso anual
- Ejemplos: Fundación Luker, Empresarios por la Educación

### 4.4 Proyección de ingresos (Año 1 — Escenario Conservador)

| Segmento | Clientes | Plan | MRR |
|----------|----------|------|-----|
| 12 colegios privados Tier 1 | 12 | Premium | $1.200.000 COP |
| 15 colegios privados Tier 2 | 15 | Basic | $599.000 COP |
| 10 colegios long tail | 10 | Basic | $399.000 COP |
| 2 secretarías | 2 | Enterprise | $1.000.000 COP |
| **Total MRR** | **39 clientes** | | **~$3.2M COP/mes** |
| **ARR** | | | **~$38M COP/año** |

---

## 5. Riesgos y Mitigaciones

### Riesgos técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| DuckDB file lock durante update | Muy baja (2x/año, horario nocturno) | Medio | `os.rename()` atómico al hacer swap del archivo |
| Railway volume loss | Baja | Alto | S3 como fuente de verdad — recovery en ~15 min |
| DuckDB concurrencia write | N/A | N/A | Read-only en producción — no aplica |
| Redis caída | Baja | Bajo | Caché opcional — Django hace fallback a DuckDB |

### Riesgos de producto

| Riesgo | Descripción | Mitigación |
|--------|-------------|------------|
| Datos públicos → competencia | El ICFES publica microdatos | Time to market + ML + red de colegios como moat |
| Datos 1x/año | Clientes sin acceso a datos nuevos 6-12 meses | Comunicar claro en onboarding, ofrecer alertas cuando publique |
| Colegios públicos no pagan | 70% del mercado no tiene presupuesto propio | Vía secretarías de educación, no directo al colegio |
| Ciclos largos B2B | Secretarías tardan 3-12 meses | Iniciar por colegios privados, Tier 1 Bogotá |

### Riesgos operativos

| Riesgo | Descripción | Estado |
|--------|-------------|--------|
| `DEBUG=True` en producción | Expone stack traces a usuarios | Pendiente fix — bajo pero real |
| Wompi sin cuenta activa | No se puede cobrar en Colombia | Pendiente crear cuenta en wompi.co |
| Celery no instalado | Cobros recurrentes manuales | Alternativa: links de pago mensuales por ahora |

---

## 6. Madurez por Dimensión

| Dimensión | Madurez | Estado |
|-----------|---------|--------|
| Pipeline de datos | 9/10 | Producción, 29 años, ML embebido |
| Web app (dashboards) | 8/10 | 7 dashboards, ~10K perfiles de colegio |
| Autenticación | 9/10 | django-allauth completo |
| Caché (Redis) | 9/10 | Funcionando en producción, 105+ keys |
| Pagos (Wompi) | 6/10 | Backend listo, falta activar cuenta |
| Suscripciones/Paywall | 8/10 | 4 tiers, decoradores activos |
| Monitoreo | 3/10 | Logs básicos Railway, sin Sentry |
| Tests automatizados | 2/10 | Mínimos |
| CI/CD | 3/10 | Deploy manual (aceptable hoy) |
| B2B features avanzadas | 4/10 | PDFs, multi-usuario pendiente |

**Promedio técnico: 8.2/10**
**Promedio producto + comercial: 6.5/10**

---

## 7. Qué Falta para el Primer Cliente Pagando

En orden de prioridad:

```
1. Activar cuenta Wompi             → 30 min
   └─ Sin esto no se puede cobrar en Colombia

2. Fix DEBUG=True en producción     → 5 min
   └─ Riesgo de seguridad, fácil de resolver

3. Testing del flujo de pago        → 2-3 horas
   └─ Wompi sandbox → producción

4. Primer outreach Tier 1           → Esta semana
   └─ 10 emails personalizados a top colegios Bogotá
   └─ Template y SQL para exportar lista ya documentados
```

Lo que NO es bloqueante para el primer cliente:
- CI/CD automatizado
- Tests automatizados
- PDF export
- Multi-usuario Enterprise
- Monitoreo Sentry

---

## 8. Veredicto de Arquitectura

**Nota global: 8.5/10 — Comparable a startups Serie A en educación**

### Por qué esta nota

**Lo que se hizo bien (y no es obvio):**
- Separar OLTP (Postgres) de OLAP (DuckDB) en lugar de meter todo en Postgres
- Pre-computar en dbt en lugar de calcular en runtime (los endpoints lentos ya corregidos)
- EC2 on-demand para procesamiento: $1.50/mes en lugar de $363/mes con EC2 24/7
- Redis funcionando con invalidación versionada (`v1`) — no se ve en proyectos junior
- Claude API integrada para valor diferencial en recomendaciones
- Estrategia de ventas B2B documentada con 24.920 colegios en base de datos

**Lo que falta (deuda manejable, no deuda crítica):**
- DEBUG=True en prod (5 min de fix)
- Wompi sin activar (bloqueante comercial, no técnico)
- `views.py` muy largo (refactor en progreso)
- Sin monitoreo de errores (Sentry en un día)

---

## 9. Recomendación Final

El producto está listo para generar ingresos. La arquitectura aguanta el crecimiento de los próximos 12-18 meses sin cambios mayores (hasta ~500 clientes concurrentes).

**El siguiente paso no es construir más — es vender.**

```
Semana 1: Activar Wompi + fix DEBUG=True
Semana 2: 10 emails personalizados Tier 1 (top privados Bogotá)
Semana 3: Demos en vivo con SU colegio pre-cargado
Semana 4: Primer cliente pagando
```

El mayor riesgo de este producto no es técnico. Es que siga siendo construido indefinidamente sin llegar al primer cliente.

---

*Última actualización: 2026-03-01*
*Basado en: revisión de código, Railway dashboard, Redis key browser, docs existentes*
