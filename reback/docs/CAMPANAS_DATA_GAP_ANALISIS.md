# Análisis: Gap de Datos en Campañas Comerciales
**Fecha:** 2026-03-02
**Contexto:** Revisión del command `import_campaign_prospects` para generación de Campaña #2.

---

## Problema Central

El command no puede generar campañas porque el JOIN entre las tablas de contacto y las de puntaje falla — son **dos poblaciones de colegios distintas** que no se cruzan.

---

## Hallazgos de la Investigación

### 1. El `colegio_sk` no es un join key confiable

| Tabla | Tipo `colegio_sk` | Ejemplo |
|-------|-------------------|---------|
| `gold.dim_colegios` | VARCHAR (MD5) | `139d14127b3f49dfe08b4126a5c9a22c` |
| `gold.fct_agg_colegios_ano` | VARCHAR (MD5) | `0068b046e74af4c84485de1abbd59106` |

Son MD5s generados desde campos diferentes en cada modelo dbt. El JOIN `ON f.colegio_sk = d.colegio_sk` no produce ningún match.

### 2. El `colegio_bk` tampoco resuelve el join (hoy)

Ambas tablas usan `colegio_bk` de 12 dígitos (código DANE), pero los colegios son distintos:

- `dim_colegios` con email en Cali: `376001009087`, `376001011634`, `376001013114`...
- `fct_agg_colegios_ano` 2024 en Cali: `376001013173`, `376001031031`, `376001001558`...

JOIN por `colegio_bk`: **0 matches** (incluso quitando el filtro de sector).

### 3. Las dos poblaciones son disjuntas

Datos concretos para Cali, colegios privados, año 2024:

| Métrica | Valor |
|---------|-------|
| Colegios en `fct_agg` con `avg_punt_global > 0` | 278 |
| De esos 278, con entrada en `dim_colegios` | 278 ✅ |
| De esos 278, con `email` en `dim_colegios` | **0** ❌ |
| Colegios en `dim_colegios` con email (Cali) | 493 |
| De esos 493, con entrada en `fct_agg` 2024 | **0** ❌ |

**Conclusión:** Los colegios que tienen email en el directorio MEN (dim_colegios) son escuelas que en general NO presentaron ICFES en 2024 (jardines, escuelas pequeñas, etc.). Los colegios que SÍ presentaron ICFES tienen el campo `email = NULL` en todas las tablas.

### 4. Coverage de email por ciudad (dim_colegios / icfes_silver)

| Ciudad | Total privados | Con email |
|--------|---------------|-----------|
| Barranquilla | 442 | 269 |
| Bucaramanga | 210 | 140 |
| Cali | 868 | 493 |
| Cartagena | 384 | 194 |
| Pereira | 184 | 125 |
| Santa Marta | 261 | 134 |
| Soacha | 225 | 116 |
| Soledad | 334 | 207 |
| Valledupar | 219 | 152 |
| Villavicencio | 237 | 141 |

---

## Causa Raíz en dbt

### A. `colegio_sk` inconsistente entre modelos

Cada modelo dbt genera el surrogate key hasheando campos distintos. El TODO ya está anotado en `TODO_PXX_BACKLOG_2026-02-27.md` (P10):
- Usar `{{ dbt_utils.generate_surrogate_key(['colegio_bk']) }}` en **todos** los modelos
- Normalizar `colegio_bk` antes de hashear (quitar prefijo de sede si aplica)
- Considerar migrar a `BIGINT` en lugar de VARCHAR MD5 para mejor performance

### B. Email ausente para colegios ICFES

El campo `email` en `dim_colegios` proviene del directorio MEN (SINEB/Secretarías). La fuente de datos ICFES (`fct_agg_colegios_ano`) viene del CSV de resultados, que no incluye información de contacto. **El email para colegios con puntaje ICFES no está en el data warehouse actualmente.**

---

## Opciones de Solución

### Opción A — Usar dim_colegios directamente (sin score) ✅ Funciona YA

**Cómo funciona:**
```sql
SELECT d.nombre_colegio, d.rector, d.email, d.telefono, d.municipio, ...
       COALESCE(f.avg_punt_global, 0) AS avg_punt_global,
       ROW_NUMBER() OVER (
           PARTITION BY d.municipio
           ORDER BY COALESCE(f.avg_punt_global, 0) DESC, d.nombre_colegio
       ) AS rank_municipio
FROM gold.dim_colegios d
LEFT JOIN gold.fct_agg_colegios_ano f
    ON f.colegio_bk = d.colegio_bk        -- hoy no hace match, produce NULL
    AND f.ano = CAST(? AS VARCHAR)
    AND f.sector IN ('NO OFICIAL', 'NO_OFICIAL')
LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = d.colegio_bk
WHERE d.sector IN ('NO OFICIAL', 'NO_OFICIAL')
  AND d.municipio IN (...)
  AND d.email IS NOT NULL AND TRIM(d.email) != ''
```

**Resultado:**
- Colegios privados con email ✅
- `avg_punt_global = 0.0` para todos (esperado, es un placeholder) ⚠️
- Ranking por nombre_colegio (no por puntaje) ⚠️
- Demo URL funcional ✅
- ~100-150 prospectos por campaña de 10 ciudades con top 10 ✅

**Pros:** Funciona ahora. Permite lanzar Campaña #2 esta semana.
**Contras:** Sin scoring real. Los prospectos no están seleccionados por performance ICFES.

---

### Opción B — Enriquecer dim_colegios con emails desde fuente externa

Obtener emails de los colegios que SÍ presentan ICFES de una fuente alternativa:
- Directorio oficial MEN (descargar CSV actualizado con más cobertura)
- Sitios web de las Secretarías de Educación departamentales
- Scraping manual de directorios educativos

**Pros:** Campañas con scoring ICFES real desde el inicio.
**Contras:** Trabajo manual/técnico significativo. No disponible de inmediato.

---

### Opción C — Fix dbt (P10) + enriquecer email en gold (mediano plazo)

1. Normalizar `colegio_bk` en `fct_agg` (quitar prefijo de sede si existe)
2. Hacer match `fct_agg.colegio_bk = dim_colegios.colegio_bk`
3. Enriquecer `dim_colegios` con email desde fuente actualizada
4. Regenerar gold layer

**Pros:** Solución limpia y permanente.
**Contras:** Requiere investigar pipeline dbt + fuente de datos. Semanas de trabajo.

---

## Estado del Command Actual

El command `import_campaign_prospects` hoy:
- Para `segmento='ciudad'`: JOIN con `fct_agg` por `colegio_sk` → **0 resultados**
- Para `segmento='departamento'`: LEFT JOIN con `fct_agg` por `colegio_sk` → **0 resultados** (el filtro `AND u.avg_punt_global IS NOT NULL` bloquea todo)
- Guardrail activo para ambos segmentos → cancela si hay scores inválidos

**Para generar campañas YA** hay que:
1. Cambiar el join key a `colegio_bk`
2. Hacer el join con `fct_agg` opcional (LEFT JOIN, no requerir match)
3. Desactivar el guardrail (o convertirlo en warning) cuando no hay datos de puntaje

---

## Decisión Pendiente

- [ ] **¿Opción A (campañas ya, sin score)** o esperar solución con score real?
- [ ] ¿Cuántos prospectos por ciudad queremos para Campaña #2? (default: 10)
- [ ] ¿Mismas ciudades del default o nuevas?
- [ ] ¿Se acepta que `avg_punt_global = 0.0` en los prospectos de la Campaña #2?

---

## Referencias

- Backlog P10 (fix pipeline dbt): `docs/TODO_PXX_BACKLOG_2026-02-27.md`
- Backlog P11 (módulo campañas): `docs/TODO_PXX_BACKLOG_2026-02-27.md`
- Command: `icfes_dashboard/management/commands/import_campaign_prospects.py`
- Admin: `icfes_dashboard/admin.py`
