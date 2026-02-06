# ICFES Analytics Platform - Web Portal

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1+-green?logo=django&logoColor=white)](https://www.djangoproject.com/)

> **Portal web interactivo para análisis de datos del examen ICFES (Colombia)**  
> Integrado con dbt DuckDB data warehouse | 17.7M+ registros | 29 años de datos históricos

---

## 🎯 Descripción

Portal web Django que proporciona acceso interactivo a los datos procesados del examen ICFES. Conectado directamente al data warehouse dbt (`dev.duckdb`) para aprovechar modelos analíticos avanzados de la capa Gold.

### Características Principales

- 📊 **Dashboard Interactivo**: Visualizaciones con ApexCharts
- 🗺️ **Explorador Jerárquico**: Navegación Región → Departamento → Municipio → Colegio
- 📈 **Métricas Avanzadas**: Z-scores, percentiles, rankings, tendencias YoY
- 🔌 **API REST**: Endpoints JSON para integraciones
- ⚡ **Alto Rendimiento**: Queries optimizadas (~12-25ms)
- 🎨 **UI Premium**: Template Reback Admin responsive

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                      Django Web Portal                       │
│                    (c:\proyectos\www\reback)                 │
└───────────────────────────┬─────────────────────────────────┘
                            │ Read-Only Connection
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    dbt DuckDB Warehouse                      │
│              (c:\proyectos\dbt\icfes_processing)             │
│                                                               │
│  Bronze Layer  →  Silver Layer  →  Gold Layer                │
│  (Raw Data)       (Cleaned)        (Analytics)               │
│                                                               │
│  • 38 sources     • dim_colegios   • fact_icfes_analytics    │
│                   • dim_colegios   • fct_agg_colegios_ano    │
│                   • icfes          • tendencias_regionales   │
│                                    • vw_fct_colegios_region  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Instalación

### Prerrequisitos

- Python 3.11+
- pip
- Git
- dbt project configurado (ver `c:\proyectos\dbt\icfes_processing`)

### Setup

```bash
# 1. Navegar al directorio del proyecto
cd c:\proyectos\www\reback

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno virtual
# Windows:
venv\Scripts\activate

# 4. Instalar dependencias
pip install -r requirements\local.txt

# 5. Configurar variables de entorno
# Copiar .env.example a .env y configurar

# 6. Ejecutar migraciones
python manage.py migrate

# 7. Crear superusuario
python manage.py createsuperuser

# 8. Iniciar servidor de desarrollo
python manage.py runserver
```

### Inicializar Planes de Suscripción

```bash
# Crear los 4 planes de suscripción (Free, Basic, Premium, Enterprise)
python manage.py create_plans
```

---

## 🔐 Acceso a la Aplicación

### URLs Principales

| Página | URL | Acceso | Descripción |
|--------|-----|--------|-------------|
| **Pricing** | `http://localhost:8000/pages-pricing/` | 🌐 Público | Ver planes y precios |
| **Registro** | `http://localhost:8000/accounts/signup/` | 🌐 Público | Crear cuenta nueva |
| **Login** | `http://localhost:8000/accounts/login/` | 🌐 Público | Iniciar sesión |
| **Dashboard** | `http://localhost:8000/` | 🔒 Requiere login | Dashboard principal |
| **Admin Django** | `http://localhost:8000/admin/` | 🔒 Superuser | Gestión de suscripciones |

### Flujo de Usuario

```
1. Ver Pricing (Público)
   ↓
2. Seleccionar Plan → Click "Get Started"
   ↓
3. Registrarse (email + password)
   ↓
4. Verificar email (check console Django en desarrollo)
   ↓
5. Login
   ↓
6. ✅ Acceso al Dashboard con Plan Free automático
```

---

## 💳 Sistema de Suscripciones (Freemium)

### Planes Disponibles

| Plan | Precio | Queries/Día | Acceso Geográfico | Años Históricos | Exportar | API |
|------|--------|-------------|-------------------|-----------------|----------|-----|
| **Free** | $0/mes | 10 | Solo regiones | 3 años | ❌ | ❌ |
| **Basic** | $9.99/mes | 100 | Departamentos + Municipios | 10 años | CSV | ❌ |
| **Premium** | $29.99/mes | 1,000 | Colegios individuales | 29 años (completo) | CSV, Excel, PDF | ✅ (100 req/hr) |
| **Enterprise** | Custom | 10,000 | Todo | 29 años | Todo | ✅ Ilimitado |

### Características por Tier

#### 🆓 Free Plan
- ✅ Datos agregados por **región**
- ✅ Últimos **3 años** de datos
- ✅ **10 consultas** por día
- ❌ Sin exportación de datos
- ❌ Sin acceso a API

#### 💼 Basic Plan
- ✅ Datos por **departamento** y **municipio**
- ✅ Últimos **10 años** de datos
- ✅ **100 consultas** por día
- ✅ Exportación a **CSV**
- ❌ Sin acceso a API

#### ⭐ Premium Plan
- ✅ Datos de **colegios individuales**
- ✅ **Histórico completo** (1996-2024)
- ✅ **1,000 consultas** por día
- ✅ Exportación a **CSV, Excel y PDF**
- ✅ **Acceso a API REST** (100 requests/hora)

#### 🏢 Enterprise Plan
- ✅ Todo lo de Premium
- ✅ **API ilimitada**
- ✅ **10,000 consultas** por día
- ✅ Soporte dedicado
- ✅ Integraciones personalizadas

### Gestión de Suscripciones

#### Admin Django

```bash
# 1. Crear superusuario (si no existe)
python manage.py createsuperuser

# 2. Acceder al admin
http://localhost:8000/admin/

# 3. Navegar a: Users → Subscription plans / User subscriptions
```

**En el admin puedes:**
- ✅ Ver y editar planes de suscripción
- ✅ Asignar planes a usuarios manualmente
- ✅ Ver logs de queries por usuario
- ✅ Monitorear uso diario de queries

#### Asignar Plan Manualmente (Python Shell)

```bash
python manage.py shell
```

```python
from reback.users.models import User
from reback.users.subscription_models import SubscriptionPlan, UserSubscription

# Obtener usuario
user = User.objects.get(email='usuario@example.com')

# Obtener plan Premium
premium = SubscriptionPlan.objects.get(tier='premium')

# Asignar plan
subscription = UserSubscription.objects.create(user=user, plan=premium)
print(f"✅ {user.email} ahora tiene plan {premium.name}")
```

### Control de Acceso Automático

El sistema usa **middleware** para controlar acceso a endpoints `/icfes/api/`:

```python
# Verifica automáticamente:
✅ Usuario autenticado?
✅ Suscripción activa?
✅ Queries disponibles hoy?
✅ Plan permite acceder a este endpoint?

# Si todo OK → Procesa request
# Si NO → Retorna error 403/429 con mensaje de upgrade
```

**Ejemplo de respuesta cuando se excede límite:**

```json
{
  "error": "Daily query limit exceeded",
  "message": "You have reached your daily limit of 10 queries",
  "current_plan": "free",
  "queries_used": 10,
  "queries_limit": 10,
  "upgrade_url": "/pages-pricing/"
}
```

---

## 🧪 Testing del Sistema Freemium

### Test 1: Página Pública de Pricing

```bash
# Abrir en navegador (sin login):
http://localhost:8000/pages-pricing/
```

✅ Debe mostrar los 4 planes sin pedir login

### Test 2: Registro con Plan Free Automático

```bash
# 1. Ir a pricing y click "Get Started"
# 2. Registrarse con email nuevo
# 3. Verificar email (en desarrollo, ver console de Django)
# 4. Login
# 5. Verificar en admin que tiene UserSubscription con plan Free
```

### Test 3: Verificar Límites de Queries

```python
# En Django shell:
from reback.users.models import User

user = User.objects.get(email='tu@email.com')
sub = user.subscription

print(f"Plan: {sub.plan.name}")
print(f"Queries hoy: {sub.queries_today}/{sub.plan.max_queries_per_day}")
print(f"Queries restantes: {sub.get_remaining_queries()}")
```

---

## 📊 Acceso al Dashboard ICFES

### Dashboard Principal

```
http://localhost:8000/
```

**Requiere:** Login con cualquier plan (Free, Basic, Premium, Enterprise)



## 📊 Dashboard ICFES

### Vista General

Incluye:
- **KPIs**: Total estudiantes, colegios, promedio nacional, departamentos
- **Tendencias Nacionales**: Gráfico de líneas con evolución temporal (1996-2024)
- **Comparación Sectores**: Gráfico de barras (Oficial vs No Oficial)
- **Ranking Departamental**: Top 10 departamentos por puntaje
- **Distribución Regional**: Gráfico de dona con estudiantes por región
- **Top Colegios**: Tabla interactiva con los 50 mejores colegios

### Explorador Jerárquico

Tabla expandible de 4 niveles:

```
📍 Región (6 regiones)
  └─ 📍 Departamento
      └─ 📍 Municipio
          └─ 🏫 Colegio
```

**Métricas por nivel:**
- Puntajes (Global, Matemáticas, Lectura, C. Naturales, Sociales, Inglés)
- Ranking relativo
- Tendencia anual (YoY %)
- Z-Score (desviación estándar)
- Percentil (0-100%)

---

## 🔌 API Endpoints

### Estadísticas Generales

```bash
GET /icfes/api/estadisticas/?ano=2024
```

Retorna: Total estudiantes, colegios, promedio nacional, departamentos

### Tendencias Nacionales

```bash
GET /icfes/api/charts/tendencias/
```

Retorna: Serie temporal con puntajes por materia (1996-2024)

### Jerarquía Geográfica

```bash
# Regiones
GET /icfes/api/hierarchy/regions/?ano=2024

# Departamentos de una región
GET /icfes/api/hierarchy/departments/?region=ANDINA&ano=2024

# Municipios de un departamento
GET /icfes/api/hierarchy/municipalities/?department=BOGOTA&ano=2024

# Colegios de un municipio
GET /icfes/api/hierarchy/schools/?municipality=BOGOTA&ano=2024
```

### Top Colegios

```bash
GET /icfes/api/colegios/destacados/?ano=2024&limit=50
```

---

## 🛠️ Tecnologías

### Backend
- **Django 5.1+**: Framework web
- **DuckDB**: Conexión a data warehouse
- **Pandas**: Procesamiento de datos
- **Django REST Framework**: API endpoints

### Frontend
- **Bootstrap 5**: Framework CSS
- **ApexCharts**: Visualizaciones interactivas
- **JavaScript ES6+**: Lógica de frontend
- **Reback Admin**: Template premium

### Database
- **DuckDB** (dev.duckdb): Data warehouse principal (15.5 GB)
- **PostgreSQL/SQLite**: Metadata de Django (usuarios, sesiones)

---

## 📁 Estructura del Proyecto

```
c:\proyectos\www\reback\
├── config/                      # Configuración Django
│   └── settings/
│       ├── base.py             # Settings base
│       ├── local.py            # Settings desarrollo
│       └── production.py       # Settings producción
├── icfes_dashboard/            # App principal
│   ├── models.py               # Modelos Django (unmanaged)
│   ├── views.py                # Vistas y API endpoints
│   ├── urls.py                 # Rutas
│   └── templates/
│       └── icfes_dashboard/
│           └── pages/
│               └── dashboard-icfes.html
├── reback/                     # App core
│   └── static/
│       └── js/
│           └── pages/
│               └── dashboard.icfes.js  # Lógica frontend
├── requirements/               # Dependencias
│   ├── base.txt
│   ├── local.txt
│   └── production.txt
└── manage.py
```

---

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
coverage run -m pytest
coverage html
open htmlcov/index.html

# Type checking
mypy reback
```

---

## 🚀 Deployment

### Desarrollo Local

```bash
python manage.py runserver
```

### Producción (Pendiente)

- [ ] Configurar Docker
- [ ] Setup CI/CD (GitHub Actions)
- [ ] Deploy en Railway/Render/AWS
- [ ] Configurar CDN para assets
- [ ] Implementar caché (Redis)

---

## 📝 Configuración de Base de Datos

### DuckDB Connection (Read-Only)

```python
# config/settings/base.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'duckdb': {
        'ENGINE': 'django_duckdb',
        'NAME': 'c:/proyectos/dbt/icfes_processing/dev.duckdb',
        'OPTIONS': {
            'read_only': True,
        }
    }
}
```

### Vista Materializada

El proyecto usa `vw_fct_colegios_region` para optimizar queries regionales:

```bash
# Actualizar vista materializada
python create_materialized_view.py

# Probar endpoints
python test_materialized_view.py
```

---

## 🔧 Comandos Útiles

### Gestión de Usuarios

```bash
# Crear superusuario
python manage.py createsuperuser

# Cambiar contraseña
python manage.py changepassword <username>
```

### Desarrollo

```bash
# Ejecutar servidor
python manage.py runserver

# Shell interactivo
python manage.py shell

# Limpiar sesiones
python manage.py clearsessions
```

### Base de Datos

```bash
# Migraciones
python manage.py makemigrations
python manage.py migrate

# SQL de migraciones
python manage.py sqlmigrate <app> <migration_number>
```

---

---

## 📈 Estrategia SEO (Programmatic SEO)

El verdadero potencial de tráfico de la aplicación reside en las **Landing Pages de Colegios** (`/icfes/colegio/<slug>/`), no solo en la home.

### 1. El Concepto: Programmatic SEO
En lugar de escribir manualmente 10 artículos de blog, generamos automáticamente **22,000+ páginas únicas**, una por cada colegio en la base de datos.
- **Query de búsqueda**: "Resultados ICFES Colegio Javiera Londoño", "Mejor colegio en Medellín", "Puntaje ICFES colegio X".
- **Volumen**: Si cada colegio recibe solo 10 visitas/mes → **220,000 visitas/mes** de tráfico orgánico altamente cualificado.

### 2. Estructura de Indexación
Para que Google indexe estas miles de páginas sin considerarlas "Thin Content":
- **Contenido Único**: Cada página tiene datos específicos (gráficos, rankings, brechas) que no existen en otro lugar.
- **Sitemap Dinámico**: Un `sitemap.xml` que lista todas las URLs de colegios (ya tenemos la tabla `dim_colegios_slugs` para esto).
- **Schema.org**: Implementar datos estructurados `School` y `EducationalOrganization` para aparecer en Rich Snippets.

### 3. El Funnel de Conversión
Estas páginas actúan como la "parte ancha" del embudo:
1.  **Atracción**: Padre/Rector busca su colegio → Llega a nuestra Landing Page Gratuita.
2.  **Valor**: Ve los datos básicos (2024) y se impresiona con la calidad visual.
3.  **Conversión**: Ve un CTA "Ver histórico 10 años" o "Comparar con competencia".
4.  **Venta**: Se registra en el Plan Freemium/Premium.

### 4. Implementación Técnica
- **Slugs**: URLs amigables SEO (`/colegio/liceo-nacional-agustin-codazzi/`) en lugar de IDs (`/colegio/12345/`).
- **Meta Tags Dinámicos**: `<title>Resultados ICFES 2024 - Colegio X | Ranking y Análisis</title>`.
- **Performance**: Las páginas deben cargar en <1s (DuckDB + Vistas Materializadas) para pasar los Core Web Vitals.

---

## 📚 Documentación Adicional

- [TODO de Integración](../TODO_INTEGRACION_WEB_ICFES.md)
- [Evaluación del Proyecto](../EVALUACION_PROYECTO.md)
- [README dbt](../dbt/icfes_processing/README.md)
- [Django Documentation](https://docs.djangoproject.com/)
- [DuckDB Documentation](https://duckdb.org/docs/)

---

## 🤝 Contribución

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.

---

## 👤 Autor

**Jose Gregorio Maestre**

---

**⭐ Si este proyecto te resulta útil, considera darle una estrella en GitHub!**

