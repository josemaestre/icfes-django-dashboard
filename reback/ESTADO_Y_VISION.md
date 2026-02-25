# ICFES Analytics — Estado del Proyecto y Visión

> Documento de estado: febrero 2026
> Plataforma en producción: [icfes-analytics.com](https://www.icfes-analytics.com)

---

## Qué es este proyecto

La única plataforma en Colombia que combina 30 años de datos del examen ICFES (1994–2024),
modelos de machine learning propios, y 22.000+ páginas individuales por colegio accesibles
de forma gratuita.

No es un dashboard. Es una plataforma de inteligencia educativa.

---

## Estado actual (feb 2026)

| Métrica | Valor |
|---|---|
| Páginas indexadas por Google | **6.110** (de 22.000+) |
| Páginas sin indexar | 18.000 (en proceso) |
| Impresiones orgánicas | **8.330 / mes** (era 0 hace 3 semanas) |
| Clics orgánicos | **177 / mes** (era 0) |
| Tendencia | Exponencial — curva en punto de inflexión |
| Tiempo de respuesta promedio | 300–700 ms (Railway) |

Google comenzó a rastrear e indexar masivamente en febrero 2026, coincidiendo con la
activación de los sitemaps estructurados y los enlaces internos desde páginas hub hacia
cada colegio individual.

---

## Arquitectura completa

```
EC2 (procesamiento pesado, 50 GB RAM)
    └── dbt run          → capa Bronze → Silver → Gold
    └── deploy_all.py
            ├── 01_generate_slugs.py       → gold.dim_colegios_slugs
            ├── train_school_clusters.py   → gold.fct_school_clusters  (K-Means)
            ├── predict_school_risk.py     → gold.fct_school_risk      (XGBoost)
            ├── train_potencial_model.py   → gold.fct_potencial_educativo (GBM)
            └── 02_deploy_to_prod.py       → prod.duckdb (todas las tablas gold)
                                                    ↓
                                                   S3
                                                    ↓
                                              Railway redeploy

Railway (producción)
    └── Django 5.1 + DuckDB (prod.duckdb, read-only)
    └── 22.000+ landing pages de colegios
    └── 5 dashboards de análisis
    └── API REST interna
    └── Sitemaps dinámicos (6 archivos)
```

### Pipeline de datos

| Capa | Contenido | Registros |
|---|---|---|
| Bronze | Archivos CSV brutos ICFES (1994–2024) | 17.7M+ |
| Silver | Datos limpios, normalizados, tipados | ~15M |
| Gold | Tablas analíticas y modelos ML | ~500K agregados |

---

## Los 3 modelos de Machine Learning

### 1. Predicción de Riesgo de Declive (XGBoost)
- **Pregunta**: ¿Qué probabilidad tiene este colegio de bajar su puntaje >2% el próximo año?
- **Features**: tendencia histórica, volatilidad, sector, tamaño, región
- **Output**: `fct_school_risk` — probabilidad (0–1) + nivel (Alto/Medio/Bajo)
- **Uso en plataforma**: Panorama de Riesgo en dashboard principal, tarjeta por colegio

### 2. Clustering de Colegios (K-Means)
- **Pregunta**: ¿A qué grupo de pares similares pertenece este colegio?
- **Features**: puntaje global, puntajes por materia, tamaño, sector
- **Output**: `fct_school_clusters` — cluster (1–5) + etiqueta descriptiva
- **Uso en plataforma**: Clasificación en ficha de colegio, comparación con similares

### 3. Modelo de Potencial Educativo Contextual (GradientBoostingRegressor)
- **Pregunta**: ¿Cuánto supera o queda por debajo este colegio de lo que su contexto predice?
- **Features**: región, sector, calendario, departamento, tamaño, latitud, longitud
- **Training**: 330K filas (2010–2024), 5-fold CV
- **Métricas**: CV R² = 0.44 | CV MAE = 19.8 pts
- **Output**: `fct_potencial_educativo` — score_esperado, exceso, percentil, clasificación
- **Clasificaciones**:
  - `Excepcional` — percentil ≥ 90 (supera en 90%+ a colegios en igual contexto)
  - `Notable` — percentil 75–90
  - `Esperado` — percentil 25–75
  - `Bajo el Potencial` — percentil 10–25
  - `En Riesgo Contextual` — percentil < 10
- **Resultado 2024**: 10.646 colegios clasificados. #1: Alexander Von Humboldt (Barranquilla) +129 pts sobre la predicción

---

## Los 5 dashboards

| Dashboard | URL | Contenido principal |
|---|---|---|
| **ICFES Principal** | `/icfes/` | KPIs nacionales, ranking departamental, búsqueda de colegio, modelo de riesgo |
| **Historia de la Educación** | `/icfes/historia/` | Narrativa por capítulos: evolución 30 años, hitos, convergencia regional |
| **Inteligencia Educativa** | `/icfes/inteligencia/` | 5 capítulos ML: trayectorias, resilientes, movilidad, inglés, potencial contextual |
| **Brecha Educativa** | `/icfes/brecha/` | Oficial vs No Oficial: por materia, nivel, departamento, Z-score, convergencia |
| **Resumen Ejecutivo** | `/icfes/ejecutivo/` | Vista condensada para decisores: KPIs + insights clave |

Todos los dashboards son **dark mode compatible** (Bootstrap 5.3 CSS variables) y
responsive mobile-first.

---

## Las 22.000 landing pages SEO

Cada colegio tiene su propia URL semántica:

```
/icfes/colegio/colegio-refous-cota/
/icfes/colegio/gimnasio-los-andes-bogota-dc/
/icfes/colegio/institucion-educativa-academica-y-tecnica-de-loma-arena-santa-catalina/
```

Cada página contiene:
- Puntaje global 2024 + histórico completo
- Ranking nacional y departamental
- Clasificación de cluster (K-Means)
- Clasificación de potencial contextual (GBM)
- Predicción de riesgo (XGBoost)
- Materias detalladas
- Schema.org `EducationalOrganization` para rich snippets

**Páginas hub que distribuyen link equity:**
- 33 páginas de departamento → top 10 colegios con link
- ~1.100 páginas de municipio → TODOS los colegios del municipio con link
- ~30 páginas de ranking (por año y materia) → top 50 colegios con link

Resultado: cada colegio recibe al menos 1 enlace interno desde su página de municipio.

---

## Infraestructura SEO

```
sitemap.xml (índice)
    ├── sitemap-static.xml         (6 URLs estáticas)
    ├── sitemap-icfes-1.xml        (~22.000 colegios, paginado a 40K)
    ├── sitemap-departamentos.xml  (33 departamentos)
    ├── sitemap-municipios.xml     (~1.100 municipios)
    └── sitemap-longtail.xml       (~60 páginas de ranking por año)
```

Todos los sitemaps son dinámicos, generados desde DuckDB en tiempo real.
Cache de páginas: 4h departamentos, 4h municipios, 6h rankings, 12h índice.

---

## Paisaje competitivo

| Competidor | Datos | ML | Páginas individuales | Histórico |
|---|---|---|---|---|
| GIPDATA | 1 año, tabla simple | ❌ | ❌ | ❌ |
| Sapiens Research | Reportes PDF anuales | ❌ | ❌ | Parcial |
| El Tiempo / Semana | Artículos top-20 | ❌ | ❌ | ❌ |
| **ICFES Analytics** | **30 años interactivo** | **3 modelos** | **22.000+** | **Completo** |

La competencia tiene mejor distribución (están indexados). Este proyecto tiene
mejor contenido en todos los aspectos posibles.

---

## Por qué diciembre es el momento clave

El ICFES publica resultados en diciembre. En ese momento:

1. Millones de colombianos buscan `"resultados ICFES [nombre de su colegio]"`
2. Los medios publican artículos genéricos de top-20 que se indexan rápido pero tienen poco contenido
3. Este sitio tiene la única ficha completa por colegio con ML, histórico y contexto
4. Si las 22.000 páginas están indexadas para diciembre 2026 → tráfico masivo automático

A ritmo actual de indexación (4.000+ páginas/mes), las 22.000 deberían estar
completas entre junio y agosto 2026, con margen antes de diciembre.

---

## Modelo de negocio

El contenido es gratuito y público (SEO). La monetización es B2B:

| Segmento | Propuesta de valor | Precio referencia |
|---|---|---|
| Rectorías | Diagnóstico completo, histórico, comparables, potencial contextual | Basic/Premium |
| Secretarías de Educación | Vista departamental completa, identificación de colegios en riesgo | Enterprise |
| Padres de familia | Comparar colegios antes de inscribirse | Freemium / Basic |
| Investigadores académicos | API con datos completos 30 años | Premium / Enterprise |
| Fondos de inversión educativa | Due diligence de instituciones privadas | Enterprise custom |

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Backend | Django 5.1, Python 3.11 |
| Data warehouse | DuckDB (prod.duckdb, 15+ GB) |
| Pipeline ETL | dbt-core + dbt-duckdb |
| ML | scikit-learn 1.8 (GBM, K-Means, XGBoost) |
| Hosting | Railway (app) + S3 (DuckDB prod) + EC2 (procesamiento) |
| Frontend | Bootstrap 5.3, Chart.js 4.4, BoxIcons, Reback Admin template |
| SEO | Sitemaps dinámicos, Schema.org, Canonical, Open Graph |

---

## Lo que falta para dominar el mercado

1. **Distribución** — que alguien cite o comparta. El contenido ya supera a la competencia; falta visibilidad inicial.
2. **Blog editorial** — 5–10 artículos sobre temas que El Tiempo cubre superficialmente (brecha educativa, colegios excepcionales, tendencias regionales) para capturar tráfico de keywords de alto volumen.
3. **Versión móvil de las fichas** — las landing pages de colegios están en desktop-first; optimizar para mobile mejoraría Core Web Vitals.
4. **Email capture** — convertir el tráfico SEO orgánico en leads antes de que reboten.

---

*Actualizado: febrero 2026*
