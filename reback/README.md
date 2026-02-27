# ICFES Analytics Platform — Web Portal

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1+-green?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.x-yellow?logo=duckdb&logoColor=white)](https://duckdb.org/)
[![Railway](https://img.shields.io/badge/Deploy-Railway-purple)](https://railway.app/)

> Portal web Django para la plataforma de inteligencia educativa ICFES Analytics.
> 30 años de datos | 17.7M+ registros | 3 modelos ML | 22.000+ landing pages SEO

---

## Descripción

Portal web conectado a un data warehouse DuckDB que expone:

- **5 dashboards interactivos** con análisis educativo avanzado
- **3 modelos de machine learning** en producción (riesgo, clusters, potencial contextual)
- **22.000+ landing pages** individuales por colegio, indexadas por Google
- **API REST interna** para todos los datos analíticos
- **Infraestructura SEO completa**: sitemaps dinámicos, Schema.org, canonical, Open Graph

---

## Arquitectura del sistema completo

```
┌─────────────────────────────────────────────────────────────────────┐
│  EC2 (procesamiento pesado, 50 GB RAM)                              │
│                                                                     │
│  1. git pull (icfes_dbt + icfes_data_science + deploy scripts)      │
│  2. dbt run   → Bronze → Silver → Gold (SQL models)                 │
│  3. deploy_all.py (en orden):                                       │
│       01_generate_slugs.py          → gold.dim_colegios_slugs       │
│       train_school_clusters.py      → gold.fct_school_clusters      │
│       predict_school_risk.py        → gold.fct_school_risk          │
│       train_potencial_model.py      → gold.fct_potencial_educativo  │
│       02_deploy_to_prod.py          → exporta TODO gold → prod.duckdb│
│  4. prod.duckdb sube a S3                                           │
│  5. Railway redeploy (descarga prod.duckdb desde S3 al arrancar)    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                          prod.duckdb (S3)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Railway (producción)                                               │
│  Django 5.1 + DuckDB read-only                                      │
│  → 22.000+ páginas de colegios                                      │
│  → 5 dashboards                                                     │
│  → API REST                                                         │
│  → Sitemaps dinámicos                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Capas del data warehouse

| Capa | Descripción | Herramienta |
|---|---|---|
| **Bronze** | Archivos CSV brutos del ICFES (1994–2024) | dbt sources |
| **Silver** | Datos limpios, normalizados, tipados | dbt SQL models |
| **Gold** | Tablas analíticas + modelos ML | dbt SQL + Python scripts |

---

## Modelos de Machine Learning

Los modelos se entrenan en EC2 con los scripts de `icfes_data_science/` y escriben
directamente a la capa Gold del data warehouse antes del deploy a producción.

### 1. Predicción de Riesgo de Declive
```
Archivo:  data_science/predict_school_risk.py
Modelo:   XGBoost Classifier
Output:   gold.fct_school_risk
Pregunta: ¿Probabilidad de que este colegio baje su puntaje >2% el próximo año?
```

### 2. Clustering de Colegios
```
Archivo:  data_science/train_school_clusters.py
Modelo:   K-Means (scikit-learn)
Output:   gold.fct_school_clusters
Pregunta: ¿A qué grupo de colegios similares pertenece este colegio?
```

### 3. Modelo de Potencial Educativo Contextual
```
Archivo:  data_science/train_potencial_model.py
Modelo:   GradientBoostingRegressor (scikit-learn)
Output:   gold.fct_potencial_educativo
Pregunta: ¿Cuánto supera o queda por debajo este colegio de lo que su contexto predice?

Training: 330K filas (2010–2024), 5-fold cross-validation
Métricas: CV R² = 0.44 | CV MAE = 19.8 pts

Features:
  Categóricas: región, sector, calendario, departamento  (OrdinalEncoder)
  Numéricas:   log1p(estudiantes), latitud, longitud

Clasificaciones (por percentil del exceso):
  >= 90  → Excepcional
  75–90  → Notable
  25–75  → Esperado
  10–25  → Bajo el Potencial
  < 10   → En Riesgo Contextual

Resultado 2024: 10.646 colegios clasificados
#1 Excepcional: Alexander Von Humboldt, Barranquilla (+129 pts sobre predicción)
```

---

## Pipeline de deploy completo

### En EC2 (deploy full, ~15–20 min)

```bash
# 1. Actualizar código
cd ~/icfes_dbt && git pull
cd ~/icfes_data_science && git pull
cd ~/deploy && git pull

# 2. Correr modelos dbt (capa Silver y Gold SQL)
cd ~/icfes_dbt/icfes_processing
dbt run

# 3. Correr todos los scripts ML + deploy a prod
cd ~/
python deploy/deploy_all.py
# Este script ejecuta en orden:
#   deploy/01_generate_slugs.py
#   data_science/train_school_clusters.py
#   data_science/predict_school_risk.py
#   data_science/train_potencial_model.py
#   deploy/02_deploy_to_prod.py   ← exporta TODAS las tablas gold a prod.duckdb

# 4. Subir prod.duckdb a S3
aws s3 cp prod.duckdb s3://icfes-analytics/prod.duckdb

# 5. Railway descarga prod.duckdb al arrancar (variable DB_PATH apunta a S3 mount)
```

### Script deploy_all.py

```python
# deploy/deploy_all.py — ejecuta los scripts en orden y aborta si alguno falla
SCRIPTS = [
    ("deploy/01_generate_slugs.py",        "Generating slugs for all schools"),
    ("data_science/train_school_clusters.py","Training school clusters (K-Means)"),
    ("data_science/predict_school_risk.py", "Generating risk predictions (XGBoost)"),
    ("data_science/train_potencial_model.py","Training contextual potential model (GBM)"),
    ("deploy/02_deploy_to_prod.py",         "Deploying gold tables to production"),
]
```

### Script 02_deploy_to_prod.py

Exporta automáticamente **todas** las tablas del schema `gold` de `dev.duckdb` a `prod.duckdb`
vía parquet. No requiere lista manual de tablas — descubre todo lo que existe en gold.

```bash
# Solo deploy a prod sin re-entrenar modelos (cuando solo cambiaron datos dbt)
python deploy/02_deploy_to_prod.py
```

---

## Dashboards

| Dashboard | URL | Descripción |
|---|---|---|
| **ICFES Principal** | `/icfes/` | KPIs, ranking depto, búsqueda colegio, modelo riesgo |
| **Historia Educación** | `/icfes/historia/` | Narrativa 30 años por capítulos, convergencia regional |
| **Inteligencia Educativa** | `/icfes/inteligencia/` | 5 capítulos ML: trayectorias, resilientes, movilidad, inglés, potencial |
| **Brecha Educativa** | `/icfes/brecha/` | Oficial vs No Oficial: materias, niveles, depto, Z-score |
| **Resumen Ejecutivo** | `/icfes/ejecutivo/` | Vista condensada para decisores |

Todos: dark mode compatible (Bootstrap 5.3 CSS variables), responsive, Chart.js 4.4.

---

## SEO — Landing pages programáticas

### Páginas indexadas

```
22.000+ URLs de colegios:
/icfes/colegio/<slug>/              → ficha completa con ML
/icfes/departamento/<slug>/         → 33 departamentos
/icfes/departamento/<d>/municipio/<m>/  → ~1.100 municipios
/icfes/ranking/colegios/<año>/      → top 50 por año (1994–2024)
/icfes/ranking/matematicas/<año>/   → top 50 en matemáticas
/icfes/historico/puntaje-global/    → tendencia nacional
```

### Sitemaps dinámicos

```
/sitemap.xml                 → índice de sitemaps
/sitemap-static.xml          → páginas estáticas
/sitemap-icfes-1.xml         → ~22.000 colegios (40K por página)
/sitemap-departamentos.xml   → 33 departamentos
/sitemap-municipios.xml      → ~1.100 municipios
/sitemap-longtail.xml        → páginas de ranking por año
```

### Estado de indexación (feb 2026)

- Indexadas: **6.110** (de 22.000+)
- Impresiones: **8.330/mes** (era 0 hace 3 semanas)
- Clics: **177/mes** (era 0)
- Tendencia: exponencial — punto de inflexión activo

---

## Setup local (desarrollo)

### Prerrequisitos

- Python 3.11+
- `uv` (instalador de paquetes recomendado)
- Acceso al archivo `dev.duckdb` del proyecto dbt

```bash
# Instalar dependencias
uv pip install -r requirements/local.txt

# Variables de entorno
cp .env.example .env
# Configurar DB_PATH apuntando a dev.duckdb local

# Migraciones Django (SQLite para metadata de usuarios)
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Inicializar planes de suscripción
python manage.py create_plans

# Servidor de desarrollo
python manage.py runserver
```

### Variables de entorno clave

```bash
DB_PATH=/ruta/a/dev.duckdb          # DuckDB local (desarrollo)
# En producción Railway apunta a prod.duckdb descargado desde S3
PUBLIC_SITE_URL=https://www.icfes-analytics.com
DJANGO_SECRET_KEY=...
DJANGO_SETTINGS_MODULE=config.settings.production
```

---

## Conexión a DuckDB

El portal usa **conexión read-only** a DuckDB. Nunca escribe en el warehouse desde el web.

```python
# icfes_dashboard/db_utils.py
def get_duckdb_connection():
    return duckdb.connect(DB_PATH, read_only=True)
```

En producción `DB_PATH` apunta al `prod.duckdb` descargado desde S3.
En desarrollo `DB_PATH` apunta al `dev.duckdb` del proyecto dbt local.

---

## Sistema de suscripciones (Freemium)

| Plan | Precio | Acceso |
|---|---|---|
| **Free** | $0 | Datos básicos, 3 años, 10 queries/día |
| **Basic** | $9.99/mes | Departamentos + municipios, 10 años, CSV export |
| **Premium** | $29.99/mes | Colegios individuales, histórico completo, API |
| **Enterprise** | Custom | Todo + soporte dedicado |

Las landing pages de colegios (`/icfes/colegio/<slug>/`) son **100% públicas** — sin
login requerido. El freemium aplica solo al dashboard interactivo con filtros avanzados.

---

## Repos relacionados

| Repo | Descripción |
|---|---|
| `icfes-django-dashboard` | Este repo — portal web Django |
| `icfes_dbt` | Pipeline dbt (Bronze → Silver → Gold) |
| `icfes_data_science` | Scripts ML (clusters, riesgo, potencial) |

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Django 5.1, Python 3.11 |
| Data warehouse | DuckDB 1.x |
| Pipeline ETL | dbt-core + dbt-duckdb |
| ML | scikit-learn 1.8 (GBM, K-Means), XGBoost |
| Hosting web | Railway |
| Procesamiento pesado | EC2 (50 GB RAM) |
| Almacenamiento | AWS S3 (prod.duckdb) |
| Frontend | Bootstrap 5.3, Chart.js 4.4, Reback Admin |
| SEO | Sitemaps dinámicos, Schema.org, OG tags |

---

## Estructura del proyecto

```
reback/
├── config/
│   └── settings/
│       ├── base.py
│       ├── local.py
│       └── production.py
├── icfes_dashboard/
│   ├── api_views.py            # Todos los endpoints JSON
│   ├── db_utils.py             # Queries DuckDB centralizadas
│   ├── views.py                # Vistas Django principales
│   ├── geo_landing_views.py    # Páginas departamento/municipio
│   ├── longtail_landing_views.py # Páginas de ranking por año
│   ├── landing_views_simple.py # Fichas individuales de colegio
│   ├── sitemap_views.py        # Sitemaps dinámicos
│   ├── urls.py
│   └── templates/
│       └── icfes_dashboard/
│           ├── pages/
│           │   ├── dashboard-icfes.html
│           │   ├── dashboard-historia.html
│           │   ├── dashboard-inteligencia.html
│           │   ├── dashboard-brecha.html
│           │   └── school_landing_page.html
│           ├── geo_landing_simple.html
│           └── longtail_landing_simple.html
├── reback/
│   └── templates/
│       └── partials/
│           └── main-nav.html
└── manage.py
```

---

## Comandos útiles

```bash
# Desarrollo
python manage.py runserver
python manage.py shell

# Producción local (simular Railway)
DB_PATH=/ruta/prod.duckdb python manage.py runserver

# Verificar que el DuckDB está accesible
python -c "import duckdb; c = duckdb.connect('dev.duckdb', read_only=True); print(c.execute('SHOW TABLES').fetchall())"

# Tests
pytest

# Linting
ruff check .
```

---

## Autor

**Jose Gregorio Maestre** — [sabededatos.com](https://www.sabededatos.com)

---

*Para contexto estratégico completo ver [ESTADO_Y_VISION.md](ESTADO_Y_VISION.md)*
