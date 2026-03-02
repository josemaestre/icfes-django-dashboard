# Plan de Migración: Surrogate Keys dbt → BIGINT
**Fecha:** 2026-03-02
**Estado:** Pendiente de decisión / para ejecutar en el momento adecuado
**Prioridad:** Media-baja (mejora de performance, no fix de correctness)

---

## 1. Estado Actual

### Inventario de SKs

| SK | Definido en | Fórmula (compilada) | Tipo actual | JOINs en gold |
|----|-------------|---------------------|-------------|---------------|
| `colegio_sk` | `silver/colegios_ano.sql:265` | `md5(TRIM(LPAD(codigo_colegio,12,'0')))` | VARCHAR(32) | **17+** |
| `colegio_ano_sk` | `silver/colegios_ano.sql:264` y `silver/icfes.sql:2717` | `md5(ano \|\| '\|' \|\| codigo_colegio)` | VARCHAR(32) | 2 |
| `estudiante_sk` | `silver/icfes.sql:2712` | `md5(estu_consecutivo)` | VARCHAR(32) | 2 |

Todos generados vía `{{ dbt_utils.generate_surrogate_key() }}` del paquete dbt-labs/dbt_utils.
El hash resultante es un **MD5 en hex → VARCHAR(32)** (ej: `0068b046e74af4c84485de1abbd59106`).

### Flujo de propagación

```
SILVER
  colegios_ano.sql     → genera colegio_sk, colegio_ano_sk
  icfes.sql            → genera estudiante_sk, colegio_ano_sk (con CASE para SYN_*)
        ↓
  colegios.sql         → hereda colegio_sk de colegios_ano (SELECT *)
  alumnos.sql          → hereda estudiante_sk de icfes (SELECT *)
        ↓
GOLD
  dim_colegios.sql     → hereda colegio_sk (SELECT * FROM colegios)
  dim_colegios_ano.sql → unique_key = colegio_ano_sk
  fact_icfes_analytics → JOIN por colegio_ano_sk (icfes ↔ dim_colegios_ano)
  fct_agg_colegios_ano → usa colegio_sk en 2 JOINs + window functions
  [13 modelos analíticos] → usan colegio_sk en JOINs
```

---

## 2. Problemas Identificados

### Problema A — VARCHAR(32) es subóptimo para JOINs masivos

Con 17.7M+ registros de estudiantes y ~300k combinaciones colegio×año:
- Cada JOIN `VARCHAR(32) = VARCHAR(32)` compara 32 bytes carácter a carácter
- `BIGINT = BIGINT` compara 8 bytes en una sola operación de CPU
- Los índices de un VARCHAR(32) ocupan ~4x más espacio que BIGINT
- Impacto mayor en `fact_icfes_analytics` y los 17+ modelos analíticos en gold

### Problema B — Inconsistencia potencial en `colegio_ano_sk`

En `colegios_ano.sql` (línea 264):
```sql
{{ dbt_utils.generate_surrogate_key(['ano', 'codigo_colegio']) }} as colegio_ano_sk
-- 'codigo_colegio' aquí es el valor RAW de la fuente (sin TRIM/LPAD explícito)
```

En `icfes.sql` (línea 2717):
```sql
{{ dbt_utils.generate_surrogate_key([
    'ano',
    "CASE ... ELSE TRIM(LPAD(cole_cod_dane_establecimiento::string, 12, '0')) END"
]) }} AS colegio_ano_sk
-- La normalización TRIM/LPAD es EXPLÍCITA aquí
```

**Riesgo:** Si `codigo_colegio` en `colegios_ano.sql` llega sin padding completo en algún año,
el MD5 resultante diferirá del generado en `icfes.sql`, rompiendo el JOIN en `fact_icfes_analytics`.
En la práctica parece funcionar (los datos están bien), pero es una dependencia frágil.

### Problema C — Sin macro centralizada

No existe un macro propio `generate_sk()`. Si se decide cambiar la función hash, hay que
actualizar `icfes.sql` y `colegios_ano.sql` manualmente y de forma sincronizada.

---

## 3. Solución Propuesta

### 3.1 Crear macro `generate_sk()` que use `hash()` nativo de DuckDB

```sql
-- macros/sk/generate_sk.sql
{% macro generate_sk(columns) %}
    {#
        Genera un surrogate key BIGINT usando hash() nativo de DuckDB.
        Reemplaza dbt_utils.generate_surrogate_key() (VARCHAR MD5).

        Uso: {{ generate_sk(['col1', 'col2']) }}

        Internamente: hash(col1 || '||' || col2) → BIGINT (8 bytes)
        vs MD5:        md5(col1 || '|' || col2)  → VARCHAR(32) (32+ bytes)
    #}
    hash(
        {%- for col in columns %}
            CAST(COALESCE({{ col }}, '') AS VARCHAR)
            {%- if not loop.last %} || '||' || {% endif %}
        {%- endfor %}
    )
{% endmacro %}
```

> **Nota:** `hash()` en DuckDB es determinístico por sesión pero puede cambiar entre versiones
> de DuckDB. Alternativa más estable: `farm_fingerprint()` o `xxhash64()` si están disponibles.
> Verificar con `SELECT hash('test')` en la versión productiva antes de migrar.

### 3.2 Reemplazar en los modelos fuente

**`silver/colegios_ano.sql`** (2 cambios):
```sql
-- ANTES:
{{ dbt_utils.generate_surrogate_key(['ano', 'codigo_colegio']) }} as colegio_ano_sk,
{{ dbt_utils.generate_surrogate_key([
    "TRIM(LPAD(codigo_colegio::string, 12, '0'))"
]) }} as colegio_sk,

-- DESPUÉS:
{{ generate_sk(['ano', "TRIM(LPAD(codigo_colegio::string, 12, '0'))"]) }} as colegio_ano_sk,
{{ generate_sk(["TRIM(LPAD(codigo_colegio::string, 12, '0'))"]) }} as colegio_sk,
```

> **Fix de consistencia incluido:** `colegio_ano_sk` ahora usa la forma normalizada
> con TRIM+LPAD, igual que en `icfes.sql`.

**`silver/icfes.sql`** (2 cambios):
```sql
-- ANTES:
{{ dbt_utils.generate_surrogate_key(['estu_consecutivo']) }} AS estudiante_sk,
{{ dbt_utils.generate_surrogate_key(['ano', "CASE ... END"]) }} AS colegio_ano_sk,

-- DESPUÉS:
{{ generate_sk(['estu_consecutivo']) }} AS estudiante_sk,
{{ generate_sk(['ano', "CASE ... END"]) }} AS colegio_ano_sk,
```

### 3.3 Actualizar schema.yml (tipos)

En `models/gold/schema.yml`, añadir `data_type: bigint` a las columnas SK:
```yaml
- name: colegio_sk
  data_type: bigint
  description: "Surrogate key del colegio (BIGINT, hash DuckDB)"
  tests:
    - not_null
```

---

## 4. Archivos a Modificar

| Archivo | Cambio | Prioridad |
|---------|--------|-----------|
| `macros/sk/generate_sk.sql` | **CREAR** — macro centralizada | Alta |
| `silver/colegios_ano.sql` | Reemplazar 2 calls + normalizar `colegio_ano_sk` | Alta |
| `silver/icfes.sql` | Reemplazar 2 calls | Alta |
| `macros/scd/scd_duckdb.sql` | Evaluar si usar nueva macro | Media |
| `macros/scd/scd2_merge.sql` | Evaluar si usar nueva macro | Media |
| `models/gold/schema.yml` | Actualizar data_type de columnas SK | Baja |

**Modelos gold que NO necesitan cambios:** heredan los SKs por SELECT * o los reciben como FK.
Sus JOINs funcionarán igual (BIGINT = BIGINT es más rápido, misma semántica).

---

## 5. Impacto en Django / Aplicación Web

Los SKs **no se usan directamente** en las queries del servidor web Django.
Las queries de la app usan `colegio_bk` (DANE code) como lookup key en la mayoría de los casos.

**Excepción:** `import_campaign_prospects.py` hace JOIN `dim_colegios ↔ fct_agg_colegios_ano`
por `colegio_sk`. Este JOIN ya retorna 0 resultados por el data gap de emails (Problema
documentado en `CAMPANAS_DATA_GAP_ANALISIS.md`), no por el tipo de SK.

**Conclusión:** La migración de SKs a BIGINT **no requiere cambios en el código Django**.

---

## 6. Procedimiento de Migración

### Pre-requisitos

- [ ] Verificar que `hash()` es estable en la versión de DuckDB en producción:
  ```sql
  SELECT hash('376001009087') AS test_sk;
  -- Debe retornar el mismo BIGINT en dev y en EC2 prod
  ```
- [ ] Confirmar versión de DuckDB: `SELECT version();`
- [ ] Backup del estado actual de las tablas gold críticas (opcional pero recomendado)
- [ ] Verificar que no hay queries en producción que filtren por valor de SK hardcodeado

### Pasos de ejecución

```bash
# 1. Crear la macro
# (Crear archivo macros/sk/generate_sk.sql con el contenido del §3.1)

# 2. Editar los 2 modelos fuente
# (colegios_ano.sql e icfes.sql según §3.2)

# 3. Rebuild completo desde silver (full-refresh obligatorio)
dbt build --full-refresh --select silver.colegios_ano silver.icfes

# 4. Rebuild de los modelos dependientes (también full-refresh)
dbt build --full-refresh --select silver.colegios silver.alumnos

# 5. Rebuild de gold
dbt build --full-refresh --select gold

# 6. Validar
dbt test --select gold

# 7. Verificar en DuckDB que los JOINs retornan resultados esperados
SELECT COUNT(*) FROM gold.fact_icfes_analytics WHERE colegio_sk IS NOT NULL;
```

### Estimación de tiempo de rebuild

| Tabla | Filas aprox. | Tiempo estimado |
|-------|-------------|-----------------|
| `silver/icfes` | 17.7M | ~15-20 min |
| `silver/colegios_ano` | ~300k | ~2 min |
| `gold/*` | Varios | ~10-15 min |
| **Total** | | **~30-40 min** |

---

## 7. Rollback

Si el rebuild falla o se detectan inconsistencias post-migración:

```bash
# Revertir los 3 archivos modificados (git)
git checkout -- dbt/icfes_processing/models/silver/colegios_ano.sql
git checkout -- dbt/icfes_processing/models/silver/icfes.sql
git rm dbt/icfes_processing/macros/sk/generate_sk.sql

# Rebuild con los valores originales
dbt build --full-refresh --select silver gold
```

---

## 8. Cuándo Ejecutar Esta Migración

### Criterios para elegir el momento

**Ejecutar CUANDO:**
- [x] Se hace `--full-refresh` de silver por otra razón (incorporar nuevos datos ICFES 2025)
- [x] Se resuelve el data gap de emails (P10 en backlog) — ese rebuild ya requiere full-refresh
- [x] Se detectan queries lentas en gold debido al JOIN VARCHAR en producción
- [x] Se añaden nuevos modelos analíticos que multipliquen los JOINs por `colegio_sk`

**NO ejecutar cuando:**
- [ ] Hay campañas activas en curso (evitar cambios en pipeline de datos)
- [ ] No hay ventana de mantenimiento disponible (rebuild tarda ~40 min)
- [ ] El equipo está en sprint de features críticas

### Dependencias con otros trabajos del backlog

| Item | Relación |
|------|----------|
| P10 — Fix dbt colegio_bk/email gap | **Prerequisito recomendado** — ese rebuild ya requiere full-refresh, hacer ambos juntos |
| P11 — Módulo campañas comerciales | Independiente — campañas usan `colegio_bk`, no `colegio_sk` directamente |
| Nuevos datos ICFES 2025 | Oportunidad — si se hace full-refresh de `icfes.sql`, aprovechar para migrar SK |

**Recomendación:** Ejecutar esta migración en la misma ventana que P10 (fix del pipeline dbt).
Ambos requieren `dbt build --full-refresh` de silver+gold. Hacerlos en dos ventanas separadas
duplica el downtime del pipeline.

---

## 9. Validaciones Post-Migración

```sql
-- 1. Tipo correcto
SELECT typeof(colegio_sk) FROM gold.dim_colegios LIMIT 1;
-- Esperado: BIGINT

-- 2. No hay NULLs inesperados
SELECT COUNT(*) FROM gold.fct_agg_colegios_ano WHERE colegio_sk IS NULL;
-- Esperado: 0

-- 3. JOINs retornan datos
SELECT COUNT(*)
FROM gold.fact_icfes_analytics f
JOIN gold.dim_colegios_ano c ON f.colegio_ano_sk = c.colegio_ano_sk
WHERE f.ano = '2024';
-- Esperado: mismo count que antes de la migración

-- 4. colegio_ano_sk es consistente entre tablas (nuevo)
SELECT COUNT(*)
FROM gold.fct_agg_colegios_ano f
LEFT JOIN gold.dim_colegios d ON f.colegio_sk = d.colegio_sk
WHERE d.colegio_sk IS NULL;
-- Esperado: 0 (o mismo número que antes si había data gap)
```

---

## Referencias

- Inventario completo explorado en sesión: 2026-03-02
- Backlog P10 (fix dbt pipeline): `docs/TODO_PXX_BACKLOG_2026-02-27.md`
- Data gap análisis: `docs/CAMPANAS_DATA_GAP_ANALISIS.md`
- Arquitectura gold layer: `docs/ARQUITECTURA_DATOS.md`
- Archivos fuente dbt:
  - `dbt/icfes_processing/models/silver/colegios_ano.sql`
  - `dbt/icfes_processing/models/silver/icfes.sql`
  - `dbt/icfes_processing/macros/scd/scd_duckdb.sql`
