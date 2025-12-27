# 🚀 Onboarding Guide - ICFES Django Dashboard

> **Guía completa para nuevos desarrolladores del proyecto**  
> Última actualización: 2025-12-27

---

## 👋 Bienvenido al Equipo

Este proyecto es un **portal web Django** para análisis interactivo de datos del examen ICFES de Colombia, integrado con un data warehouse dbt + DuckDB.

### 📊 Stack Tecnológico

- **Backend:** Django 5.0+, Python 3.11+
- **Database:** DuckDB (read-only connection to dbt warehouse)
- **Frontend:** Bootstrap 5, ApexCharts, JavaScript ES6+
- **Template:** Reback Admin (premium)
- **Package Manager:** UV (ultra-fast pip replacement)

---

## 🏗️ Arquitectura del Proyecto

```
c:\proyectos\
├── .venv/                          # Entorno virtual compartido
├── requirements/                   # Dependencias centralizadas
│   ├── pins.in                    # Core (numpy, pandas, duckdb)
│   ├── django.in                  # Django y apps
│   ├── dbt.in                     # dbt (solo si trabajas con data)
│   └── dev.in                     # Herramientas de desarrollo
├── uv.lock                        # Lock file con versiones exactas
│
├── dbt/                           # Proyecto dbt (Data Engineering)
│   └── icfes_processing/
│       ├── dev.duckdb             # Base de datos DuckDB (15.5 GB)
│       └── models/                # Modelos dbt (Bronze/Silver/Gold)
│
└── www/                           # 🎯 Portal Web Django (ESTE REPO)
    ├── .git/                      # Repositorio Git
    ├── activar_venv.bat           # Script de activación rápida
    └── reback/
        ├── manage.py              # CLI Django
        ├── config/                # Configuración
        ├── icfes_dashboard/       # App principal
        └── reback/                # App core + templates
```

---

## 📥 Instalación Inicial

### Paso 1: Clonar el Repositorio

```bash
# Clonar el repo
git clone https://github.com/josemaestre/icfes-django-dashboard.git
cd icfes-django-dashboard

# O si ya tienes acceso al proyecto completo:
cd c:\proyectos\www
```

### Paso 2: Instalar UV (si no lo tienes)

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verificar instalación
uv --version
```

### Paso 3: Configurar Entorno Virtual

```bash
# Navegar a la raíz del proyecto
cd c:\proyectos

# Crear entorno virtual (si no existe)
python -m venv .venv

# Activar entorno virtual
.\.venv\Scripts\activate

# Instalar dependencias con UV
uv pip install -r requirements/pins.in -r requirements/django.in -r requirements/dev.in

# O usar el lock file para reproducibilidad exacta
uv pip sync uv.lock
```

### Paso 4: Configurar Variables de Entorno

Crear archivo `.env` en `c:\proyectos\www\reback\`:

```bash
# Django Settings
DEBUG=True
SECRET_KEY=tu-secret-key-cambiar-en-produccion
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite para metadata Django)
DATABASE_URL=sqlite:///db.sqlite3

# DuckDB (Read-Only)
DUCKDB_PATH=c:/proyectos/dbt/icfes_processing/dev.duckdb

# Email (desarrollo)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Paso 5: Ejecutar Migraciones

```bash
cd c:\proyectos\www\reback

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser
```

### Paso 6: Iniciar Servidor

```bash
# Iniciar servidor de desarrollo
python manage.py runserver

# Acceder a:
# - Dashboard: http://localhost:8000/dashboard-icfes/
# - Admin: http://localhost:8000/admin/
```

---

## 🔄 Flujo de Trabajo Diario

### Activar Entorno

```bash
# Opción A: Desde la raíz
cd c:\proyectos
.\.venv\Scripts\activate

# Opción B: Script rápido
cd c:\proyectos\www
.\activar_venv.bat
```

### Trabajar con Git

```bash
# Ver estado
git status

# Crear rama para tu feature
git checkout -b feature/nombre-descriptivo

# Hacer cambios...
# Editar archivos

# Agregar cambios
git add .

# Commit con mensaje descriptivo
git commit -m "feat: descripción del cambio

- Detalle 1
- Detalle 2"

# Push a tu rama
git push origin feature/nombre-descriptivo

# Crear Pull Request en GitHub
```

### Convenciones de Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: nueva funcionalidad
fix: corrección de bug
docs: cambios en documentación
style: formato, punto y coma faltantes, etc.
refactor: refactorización de código
test: agregar tests
chore: tareas de mantenimiento
```

**Ejemplos:**
```bash
git commit -m "feat: add hierarchical explorer for schools"
git commit -m "fix: resolve 500 error in regions API endpoint"
git commit -m "docs: update README with new API endpoints"
```

---

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
coverage run -m pytest
coverage html
# Abrir htmlcov/index.html

# Tests específicos
pytest icfes_dashboard/tests/test_views.py

# Type checking
mypy reback
```

---

## 📁 Estructura del Código

### Apps Principales

```
reback/
├── config/                        # Configuración Django
│   ├── settings/
│   │   ├── base.py               # Settings compartidos
│   │   ├── local.py              # Desarrollo
│   │   └── production.py         # Producción
│   └── urls.py                   # URLs principales
│
├── icfes_dashboard/              # App principal
│   ├── models.py                 # Modelos (unmanaged, apuntan a DuckDB)
│   ├── views.py                  # Vistas y API endpoints
│   ├── urls.py                   # URLs de la app
│   └── templates/
│       └── pages/
│           └── dashboard-icfes.html
│
└── reback/                       # App core
    ├── static/                   # Assets estáticos
    │   ├── css/
    │   ├── js/
    │   └── vendor/
    └── templates/                # Templates base
        ├── base.html
        └── partials/
```

### Archivos Importantes

| Archivo | Propósito |
|---------|-----------|
| `manage.py` | CLI de Django |
| `config/settings/base.py` | Configuración base |
| `icfes_dashboard/views.py` | Lógica de negocio y APIs |
| `icfes_dashboard/models.py` | Modelos que mapean a DuckDB |
| `reback/static/js/pages/dashboard.icfes.js` | Lógica frontend del dashboard |

---

## 🔌 API Endpoints

### Estadísticas Generales
```bash
GET /icfes/api/estadisticas/?ano=2024
```

### Jerarquía Geográfica
```bash
GET /icfes/api/hierarchy/regions/?ano=2024
GET /icfes/api/hierarchy/departments/?region=ANDINA&ano=2024
GET /icfes/api/hierarchy/municipalities/?department=BOGOTA&ano=2024
GET /icfes/api/hierarchy/schools/?municipality=BOGOTA&ano=2024
```

### Top Colegios
```bash
GET /icfes/api/colegios/destacados/?ano=2024&limit=50
```

---

## 🐛 Debugging

### Django Debug Toolbar

Ya está instalado en desarrollo. Accede a:
```
http://localhost:8000/dashboard-icfes/
```

Verás un panel lateral con:
- SQL queries ejecutadas
- Tiempo de renderizado
- Variables de contexto
- Headers HTTP

### Logs

```bash
# Ver logs en consola
python manage.py runserver

# Logs de Django
tail -f logs/django.log
```

### DuckDB Queries

```bash
# Conectar a DuckDB directamente
cd c:\proyectos\dbt\icfes_processing
duckdb dev.duckdb

# Ejecutar queries
SELECT COUNT(*) FROM gold.fact_icfes_analytics;
SELECT DISTINCT ano FROM gold.fact_icfes_analytics ORDER BY ano;
```

---

## 📦 Agregar Nuevas Dependencias

### Con UV (Recomendado)

```bash
# 1. Editar el archivo .in apropiado
notepad c:\proyectos\requirements\django.in

# 2. Agregar la dependencia
# Ejemplo: django-cors-headers==4.0.0

# 3. Recompilar el lock file
cd c:\proyectos
uv pip compile requirements\*.in -o uv.lock

# 4. Instalar
uv pip sync uv.lock

# 5. Commit los cambios
git add requirements/django.in uv.lock
git commit -m "deps: add django-cors-headers"
```

---

## 🚨 Problemas Comunes

### Error: DuckDB no encontrado

```bash
# Verificar que existe
ls c:\proyectos\dbt\icfes_processing\dev.duckdb

# Verificar variable de entorno
echo $env:DUCKDB_PATH

# Actualizar .env
DUCKDB_PATH=c:/proyectos/dbt/icfes_processing/dev.duckdb
```

### Error: Migraciones pendientes

```bash
python manage.py migrate
```

### Error: Static files no se cargan

```bash
# Recolectar static files
python manage.py collectstatic --noinput

# O en desarrollo, asegúrate de que DEBUG=True
```

### Error: Puerto 8000 en uso

```bash
# Usar otro puerto
python manage.py runserver 8001

# O matar el proceso
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

## 📚 Recursos Adicionales

### Documentación

- [Django Docs](https://docs.djangoproject.com/)
- [DuckDB Docs](https://duckdb.org/docs/)
- [UV Docs](https://github.com/astral-sh/uv)
- [ApexCharts Docs](https://apexcharts.com/docs/)

### Documentación del Proyecto

- [`README.md`](README.md) - Overview del proyecto
- [`install.md`](../../install.md) - Guía de instalación detallada
- [dbt README](../../dbt/icfes_processing/README.md) - Documentación del data warehouse

### Contacto

- **Repo:** https://github.com/josemaestre/icfes-django-dashboard
- **Issues:** https://github.com/josemaestre/icfes-django-dashboard/issues

---

## ✅ Checklist de Onboarding

- [ ] Clonar repositorio
- [ ] Instalar UV
- [ ] Crear y activar entorno virtual
- [ ] Instalar dependencias
- [ ] Configurar `.env`
- [ ] Ejecutar migraciones
- [ ] Crear superusuario
- [ ] Iniciar servidor y verificar que funciona
- [ ] Explorar dashboard en http://localhost:8000/dashboard-icfes/
- [ ] Revisar código en `icfes_dashboard/views.py`
- [ ] Ejecutar tests con `pytest`
- [ ] Crear rama de prueba y hacer un commit
- [ ] Leer documentación del proyecto

---

**¡Bienvenido al equipo! 🎉 Si tienes preguntas, no dudes en abrir un issue en GitHub.**
