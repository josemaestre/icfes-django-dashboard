# TODO: Reducir tamaño prod_v2.duckdb (3.5 GB → ~0.5 GB)

**Fecha:** 2026-03-18
**Objetivo:** Eliminar `fact_icfes_analytics` (17.7M filas) del prod.duckdb reemplazando
sus 4 usos en el web con tablas pre-agregadas. Reducción estimada: 70-80% del archivo.

---

## Contexto

`fact_icfes_analytics` representa ~2.5 GB de los 3.5 GB del prod.duckdb.
El resto de tablas (~335K filas máximo) ocupan ~1 GB total.

Actualmente la tabla se usa en 4 endpoints de `views.py`:

| Línea | Endpoint / uso | Tipo |
|-------|---------------|------|
| ~2772 | Distribución por niveles de puntaje por colegio | Student-level |
| ~3150 | Mapa de calor (lat/lon de estudiantes) | Student-level |
| ~3226 | COUNT estudiantes por departamento | Agregación |
| ~3278 | COUNT estudiantes por municipio | Agregación |

---

## Fase 1 — Reemplazar COUNTs por fct_agg_colegios_ano ✅ fácil

**Archivos:** `views.py` líneas ~3222-3285

Las queries de `COUNT(*) GROUP BY departamento/municipio` se pueden reemplazar
con `fct_agg_colegios_ano` que ya tiene `total_estudiantes`, `departamento`, `municipio`.

**Acción:**
- Reescribir los 2 endpoints para leer de `gold.fct_agg_colegios_ano`
- No requiere cambios en dbt

---

## Fase 2 — Pre-agregar distribución de niveles por colegio ⚠️ medio

**Archivos:** `views.py` línea ~2772, dbt models

El query actual lee todos los estudiantes de un colegio y calcula distribución
de niveles (1-4) por materia. Con 17.7M filas, filtra por `colegio_sk`.

**Acción dbt:** Crear tabla `gold.fct_distribucion_niveles`:
```sql
-- Por colegio, año, materia: % en cada nivel (1=bajo, 2=medio, 3=alto, 4=muy alto)
SELECT
    colegio_sk, ano,
    COUNT(*) FILTER (WHERE nivel_matematicas = 1) * 100.0 / COUNT(*) as pct_nivel1_mat,
    ...
FROM gold.fact_icfes_analytics
GROUP BY colegio_sk, ano
```
Resultado estimado: ~335K filas (misma granularidad que fct_agg_colegios_ano).

**Acción web:** Reemplazar query en `views.py` ~2772 para leer de nueva tabla.

---

## Fase 3 — Pre-agregar mapa de calor ⚠️ medio

**Archivos:** `views.py` línea ~3150

El query actual lee lat/lon de cada estudiante y agrupa en grillas de 0.02°.
Con filtros dinámicos (año, categoría, departamento).

**Acción dbt:** Crear tabla `gold.fct_mapa_calor`:
```sql
-- Grilla pre-computada por año y combinaciones de filtros frecuentes
SELECT
    ano,
    sector,           -- para filtro por categoría
    departamento,
    ROUND(CAST(lat_estudiante AS DOUBLE), 2) as lat_grid,
    ROUND(CAST(lon_estudiante AS DOUBLE), 2) as lon_grid,
    COUNT(*) as count
FROM gold.fact_icfes_analytics
WHERE lat_estudiante IS NOT NULL AND lon_estudiante IS NOT NULL
GROUP BY ano, sector, departamento, lat_grid, lon_grid
```
Resultado estimado: mucho menor que 17.7M filas.

**Acción web:** Adaptar el endpoint del mapa para leer de la tabla pre-agregada.

---

## Fase 4 — Excluir fact_icfes_analytics del deploy a prod 🎯 objetivo final

**Archivo:** `deploy/02_sync_gold_to_prod.py`

Una vez completadas Fases 1-3, agregar `fact_icfes_analytics` a la lista de
tablas excluidas del sync gold→prod.

```python
EXCLUDED_TABLES = ['fact_icfes_analytics', ...]
```

**Resultado esperado:**
- prod_v2.duckdb: 3.5 GB → ~0.5-1 GB
- Descarga post-swipe: ~10-20 min → ~1-3 min
- Sin impacto funcional en el web

---

## Estado

- [ ] Fase 1: Reemplazar COUNTs (views.py ~3222-3285)
- [ ] Fase 2: Crear fct_distribucion_niveles (dbt + views.py ~2772)
- [ ] Fase 3: Crear fct_mapa_calor (dbt + views.py ~3150)
- [ ] Fase 4: Excluir fact_icfes_analytics del deploy
