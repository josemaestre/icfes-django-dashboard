# 📤 Guía de Uso: Exportación de Reportes

## ✅ Implementación Completada

### Features Implementadas

**CSV Exports (Plan Basic - $39,900 COP):**
- ✅ Búsqueda de colegios
- ✅ Ranking departamental

**PDF Exports (Plan Premium - $100,000 COP):**
- ✅ Reporte detallado de colegio
- ✅ Comparación de colegios

---

## 🔗 URLs Disponibles

### CSV (Requiere Plan Basic)

```python
# Exportar búsqueda de colegios
GET /icfes/export/schools/csv/?query=bogota&ano=2024

# Exportar ranking departamental
GET /icfes/export/ranking/csv/?ano=2024
```

### PDF (Requiere Plan Premium)

```python
# Exportar reporte de colegio
GET /icfes/export/school/<colegio_sk>/pdf/

# Exportar comparación
GET /icfes/export/comparison/pdf/?colegios[]=123&colegios[]=456&ano=2024
```

---

## 🧪 Testing Local

### 1. Probar CSV - Búsqueda de Colegios

```bash
# Con usuario autenticado y plan Basic
curl -H "Cookie: sessionid=YOUR_SESSION" \
  "http://localhost:8000/icfes/export/schools/csv/?query=bogota&ano=2024" \
  -o colegios_bogota.csv

# Verificar
cat colegios_bogota.csv
```

### 2. Probar CSV - Ranking

```bash
curl -H "Cookie: sessionid=YOUR_SESSION" \
  "http://localhost:8000/icfes/export/ranking/csv/?ano=2024" \
  -o ranking_2024.csv
```

### 3. Probar PDF - Reporte de Colegio

```bash
# Con usuario autenticado y plan Premium
curl -H "Cookie: sessionid=YOUR_SESSION" \
  "http://localhost:8000/icfes/export/school/12345/pdf/" \
  -o reporte_colegio.pdf

# Abrir PDF
start reporte_colegio.pdf  # Windows
```

### 4. Probar PDF - Comparación

```bash
curl -H "Cookie: sessionid=YOUR_SESSION" \
  "http://localhost:8000/icfes/export/comparison/pdf/?colegios[]=123&colegios[]=456&ano=2024" \
  -o comparacion.pdf
```

---

## 🎨 Integración en Templates

### Botón CSV en Búsqueda

```html
<!-- En template de búsqueda de colegios -->
<div class="export-buttons">
    <a href="{% url 'icfes_dashboard:export_schools_csv' %}?query={{ query }}&ano={{ ano }}" 
       class="btn btn-success">
        <i class="fas fa-file-csv"></i> Exportar CSV
    </a>
</div>
```

### Botón PDF en Detalle de Colegio

```html
<!-- En template de detalle de colegio -->
<div class="export-buttons">
    <a href="{% url 'icfes_dashboard:export_school_pdf' colegio.colegio_sk %}" 
       class="btn btn-danger">
        <i class="fas fa-file-pdf"></i> Exportar PDF
    </a>
</div>
```

### Botón CSV en Ranking

```html
<!-- En template de ranking -->
<a href="{% url 'icfes_dashboard:export_ranking_csv' %}?ano={{ ano }}" 
   class="btn btn-success">
    <i class="fas fa-download"></i> Descargar Ranking CSV
</a>
```

---

## 🔒 Control de Acceso

### Decoradores Aplicados

```python
# CSV - Requiere Plan Basic o superior
@login_required
@subscription_required(tier='basic')
def export_school_search_csv(request):
    pass

# PDF - Requiere Plan Premium
@login_required
@subscription_required(tier='premium')
def export_school_report_pdf(request):
    pass
```

### Comportamiento

| Plan | CSV | PDF |
|------|-----|-----|
| **Free** | ❌ Redirect a pricing | ❌ Redirect a pricing |
| **Basic** | ✅ Acceso completo | ❌ Redirect a upgrade |
| **Premium** | ✅ Acceso completo | ✅ Acceso completo |

---

## 📊 Contenido de Exports

### CSV - Búsqueda de Colegios

```csv
Nombre,Departamento,Municipio,Naturaleza,Puntaje Global,Lectura,Matemáticas,Sociales,Ciencias,Inglés,Estudiantes
Colegio ABC,BOGOTA,BOGOTA,OFICIAL,285.5,65.2,70.1,58.3,62.4,29.5,150
...
```

### CSV - Ranking Departamental

```csv
Departamento,Promedio Global,Lectura,Matemáticas,Sociales,Ciencias,Inglés,Total Estudiantes
BOGOTA,275.8,62.5,68.3,55.2,60.1,29.7,45000
...
```

### PDF - Reporte de Colegio

**Contenido:**
- Nombre del colegio
- Ubicación (Departamento, Municipio)
- Naturaleza y Calendario
- Desempeño histórico (últimos 5 años)
- Tabla con puntajes por área
- Número de estudiantes por año

### PDF - Comparación

**Contenido:**
- Tabla comparativa de colegios
- Puntajes por área
- Número de estudiantes
- Departamento de cada colegio

---

## 📝 Logging

Todas las exportaciones generan logs:

```python
logger.info(f"CSV Export: School search - query='bogota', ano=2024, user=user@example.com")
logger.info(f"CSV Export successful: 150 schools exported")
```

**Ver logs:**
```bash
# En Railway
railway logs

# Local
# Los logs aparecen en consola del servidor
```

---

## 🚀 Deploy a Railway

### 1. Commit y Push

```bash
git add .
git commit -m "feat: Add CSV and PDF export functionality for school reports"
git push origin main
```

### 2. Verificar en Railway

Railway instalará automáticamente `reportlab==4.0.9` desde `requirements/base.txt`

### 3. Testing en Producción

```bash
# Usar URL de Railway
curl "https://your-app.up.railway.app/icfes/export/schools/csv/?query=bogota&ano=2024" \
  -H "Cookie: sessionid=..." \
  -o test.csv
```

---

## ✅ Checklist de Verificación

- [x] `reportlab` agregado a `requirements/base.txt`
- [x] `export_views.py` creado con 4 funciones
- [x] URLs registradas en `icfes_dashboard/urls.py`
- [x] Decoradores de suscripción aplicados
- [x] Logging implementado
- [ ] Templates actualizados con botones (pendiente)
- [ ] Testing local con usuario Basic
- [ ] Testing local con usuario Premium
- [ ] Deploy a Railway
- [ ] Testing en producción

---

## 🎯 Próximos Pasos

1. **Actualizar Templates:**
   - Agregar botones de exportación en búsqueda
   - Agregar botones en detalle de colegio
   - Agregar botones en ranking

2. **Testing:**
   - Crear usuario de prueba con plan Basic
   - Crear usuario de prueba con plan Premium
   - Probar cada tipo de exportación

3. **Deploy:**
   - Commit y push
   - Verificar logs en Railway
   - Probar en producción

4. **Documentación para Usuarios:**
   - Agregar sección en FAQ
   - Crear tutorial de exportación
   - Actualizar pricing page con features

---

**Tiempo total de implementación:** ~2 horas  
**Estado:** ✅ Backend completo, pendiente integración en templates
