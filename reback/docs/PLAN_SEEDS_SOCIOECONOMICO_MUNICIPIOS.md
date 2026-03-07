# Plan: Seeds Socioeconómicos Municipales — Segunda Iteración
**Fecha:** 2026-03-02
**Estado:** Pendiente de descarga y carga de datos
**Complementa:** `seeds/contexto/dim_municipio_geo.csv` (ya implementado)

---

## Objetivo

Enriquecer `dim_municipio_contexto` (gold) con indicadores cuantitativos por municipio,
habilitando análisis como:
- *"Colegios con buenos puntajes ICFES en municipios con IPM alto = excelencia en contexto difícil"*
- *"Correlación entre cobertura de internet y puntajes post-2015"*
- *"Municipios con mayor inversión educativa vs rendimiento ICFES"*
- *"Segmentación de prospectos de campañas: alta inversión + baja deserción = más receptivos"*

---

## Fuentes de Datos — Links Directos

### 1. DANE — Necesidades Básicas Insatisfechas (NBI) 2018

**Descarga directa (Excel):**
```
https://www.dane.gov.co/files/censo2018/informacion-tecnica/CNPV-2018-NBI.xlsx
```

**Variables disponibles por municipio:**
| Campo | Descripción |
|-------|-------------|
| `pct_nbi` | % hogares con NBI (pobreza estructural) |
| `pct_vivienda_inadecuada` | % viviendas sin condiciones mínimas |
| `pct_sin_servicios` | % sin agua/alcantarillado/electricidad |
| `pct_hacinamiento` | % viviendas con hacinamiento crítico |
| `pct_inasistencia_escolar` | % niños en edad escolar sin estudiar |
| `pct_alta_dependencia_economica` | % hogares con alta carga laboral |

**Año:** 2018 (Censo CNPV). Estático — no varía año a año.
**Seed destino:** `dim_municipio_nbi.csv`

---

### 2. DANE — Índice de Pobreza Multidimensional (IPM) 2018

**Portal:** https://geoportal.dane.gov.co/visipm/
**Microdatos:** http://microdatos.dane.gov.co/index.php/catalog/606

**Variables disponibles por municipio:**
| Campo | Descripción |
|-------|-------------|
| `ipm` | Índice 0-100 (100 = máxima pobreza multidimensional) |
| `incidencia_pobreza_monetaria` | % bajo línea de pobreza de ingreso |
| `intensidad_pobreza` | Promedio de privaciones por hogar pobre |

**Nota:** El IPM evalúa 15 privaciones en 5 dimensiones:
educación, niñez y juventud, trabajo, salud, acceso a servicios públicos.

**Año:** 2018 con actualización 2023.
**Seed destino:** `dim_municipio_nbi.csv` (mismo seed, columnas adicionales)

---

### 3. MinTIC — Conectividad Internet por Municipio

**Dataset ID datos.gov.co:** `fut2-keu8`
**URL portal:** https://www.datos.gov.co/Ciencia-Tecnolog-a-e-Innovaci-n/Internet-Fijo-Penetraci-n-Municipio/fut2-keu8
**Descarga CSV directa (SODA API):**
```
https://www.datos.gov.co/resource/fut2-keu8.csv?$limit=50000
```

**Variables disponibles por municipio y trimestre:**
| Campo | Descripción |
|-------|-------------|
| `penetracion_pct` | % hogares con internet fijo |
| `accesos_fijos` | Número de conexiones fijas |
| `accesos_moviles_4g` | Conexiones 4G |
| `tecnologia_predominante` | Fibra / Cable / xDSL / Inalámbrico |
| `trimestre` | Período (ej: 2024-T1) |

**Frecuencia:** Trimestral. Años disponibles: 2015-2025.
**Seed destino:** `dim_municipio_conectividad_ano.csv` (un registro por municipio-año)

---

### 4. Policía Nacional — Estadística Delictiva

**Portal SIEDCO:** https://portalsiedco.policia.gov.co:4443/extensions/PortalPublico/index.html
**Descarga Excel:** https://www.policia.gov.co/estadistica-delictiva

**Variables disponibles por municipio y año:**
| Campo | Descripción |
|-------|-------------|
| `homicidios` | Total de homicidios |
| `tasa_homicidios_x100k` | Por 100k habitantes (calculable con pop DANE) |
| `hurto_personas` | Hurtos a personas |
| `violencia_intrafamiliar` | Casos reportados |
| `lesiones_personales` | Total lesiones personales |
| `hurto_comercio` | Hurtos a establecimientos |

**Frecuencia:** Mensual (agregable anual). Años: 2020-2026.
**Seed destino:** `dim_municipio_seguridad_ano.csv`

---

### 5. DNP TerriData — Indicadores Territoriales (800+ indicadores)

**Portal:** https://terridata.dnp.gov.co/
**Contacto API:** terridata@dnp.gov.co
**Descarga:** Sección "Descargas" → Excel/TXT por indicador y municipio

**Variables más relevantes para educación:**
| Campo | Descripción | Frecuencia |
|-------|-------------|-----------|
| `indice_desempeno_fiscal` | Calidad de gestión financiera 0-100 | Anual |
| `ingresos_totales_cop` | Presupuesto total del municipio | Anual |
| `inversion_educacion_cop` | Gasto en educación | Anual |
| `inversion_por_estudiante_cop` | Inversión por alumno (calculable) | Anual |
| `cobertura_educativa_pct` | % niños matriculados en edad escolar | Anual |
| `tasa_desercion_pct` | % alumnos que abandonan el año | Anual |
| `ratio_alumno_docente` | Alumnos por docente | Anual |
| `tasa_analfabetismo_pct` | % adultos sin leer/escribir | Censal |
| `pib_per_capita_dpto` | PIB per cápita departamental | Anual |
| `tasa_desempleo_pct` | % desempleados | Anual |
| `cobertura_salud_pct` | % afiliados al sistema de salud | Anual |

**Seed destino:** `dim_municipio_fiscal_ano.csv` + `dim_municipio_educacion_ano.csv`

---

### 6. DANE — Proyecciones de Población 2024

**Portal:** https://www.dane.gov.co/index.php/estadisticas-por-tema/demografia-y-poblacion/proyecciones-de-poblacion
**Descarga directa (Excel):**
```
https://www.dane.gov.co/files/investigaciones/poblacion/proyepobla06_20/Municipal_area_sexo.xls
```

**Variables disponibles por municipio y año:**
| Campo | Descripción |
|-------|-------------|
| `poblacion_total` | Población proyectada total |
| `poblacion_urbana` | Población área urbana |
| `poblacion_rural` | Población área rural |
| `poblacion_0_17` | Población en edad escolar |
| `poblacion_18_64` | Población en edad productiva |

**Años:** 2018-2035 (proyecciones).
**Seed destino:** `dim_municipio_poblacion_ano.csv`

---

## Estructura Final de Seeds a Crear

```
seeds/contexto/
  dim_ano_contexto.csv               ✅ IMPLEMENTADO
  dim_municipio_geo.csv              ✅ IMPLEMENTADO
  dim_municipio_nbi.csv              📥 Pendiente — DANE NBI/IPM 2018
  dim_municipio_poblacion_ano.csv    📥 Pendiente — DANE Proyecciones
  dim_municipio_conectividad_ano.csv 📥 Pendiente — MinTIC (API disponible)
  dim_municipio_seguridad_ano.csv    📥 Pendiente — Policía Nacional
  dim_municipio_fiscal_ano.csv       📥 Pendiente — DNP TerriData
  dim_municipio_educacion_ano.csv    📥 Pendiente — MEN / TerriData
```

---

## Modelo Gold Final: `dim_municipio_completo`

Una vez cargados todos los seeds, el modelo gold consolidará todo:

```sql
-- models/gold/dim_municipio_completo.sql
SELECT
    base.*,                    -- region, dpto, municipio
    geo.*,                     -- ruralidad, PDET, conflicto, lat/lon
    nbi.pct_nbi,               -- pobreza estructural
    nbi.ipm,                   -- pobreza multidimensional
    pop.poblacion_total,       -- población
    pop.poblacion_0_17,        -- edad escolar
    con.penetracion_pct,       -- internet
    seg.tasa_homicidios_x100k, -- seguridad
    fis.indice_desempeno_fiscal,
    fis.inversion_por_estudiante_cop,
    edu.cobertura_educativa_pct,
    edu.tasa_desercion_pct,
    edu.ratio_alumno_docente
FROM gold.dim_municipio_contexto base    -- ya existe
LEFT JOIN gold.dim_municipio_nbi nbi ON ...
LEFT JOIN gold.dim_municipio_poblacion pop ON ...
LEFT JOIN gold.dim_municipio_conectividad con ON ...
LEFT JOIN gold.dim_municipio_seguridad seg ON ...
LEFT JOIN gold.dim_municipio_fiscal fis ON ...
LEFT JOIN gold.dim_municipio_educacion edu ON ...
```

---

## Plan de Descarga — Orden Sugerido

| Prioridad | Dataset | Por qué primero | Tiempo estimado |
|-----------|---------|-----------------|-----------------|
| 1 | **NBI + IPM DANE** | Descarga directa disponible, un archivo, datos 2018 estáticos | 30 min |
| 2 | **Población DANE** | Descarga directa disponible, necesaria para tasas per-cápita | 30 min |
| 3 | **MinTIC Conectividad** | API CSV disponible, crítico para análisis post-2015 | 1 hora |
| 4 | **TerriData Fiscal/Educación** | Mayor valor analítico, requiere explorar portal | 2 horas |
| 5 | **Policía — Seguridad** | Requiere navegar SIEDCO, más laborioso | 2 horas |

---

## Script de Descarga Sugerido

```python
# scripts/download_socioeco_data.py
import requests, pandas as pd

# 1. NBI DANE (descarga directa)
nbi_url = "https://www.dane.gov.co/files/censo2018/informacion-tecnica/CNPV-2018-NBI.xlsx"
pd.read_excel(nbi_url).to_csv("seeds/contexto/dim_municipio_nbi.csv", index=False)

# 2. MinTIC conectividad (SODA API)
mintic_url = "https://www.datos.gov.co/resource/fut2-keu8.csv?$limit=50000"
pd.read_csv(mintic_url).to_csv("seeds/contexto/dim_municipio_conectividad_ano.csv", index=False)

# 3. Población DANE
pop_url = "https://www.dane.gov.co/files/investigaciones/poblacion/proyepobla06_20/Municipal_area_sexo.xls"
pd.read_excel(pop_url).to_csv("seeds/contexto/dim_municipio_poblacion_ano.csv", index=False)
```

---

## Referencias

- DANE NBI 2018: https://www.dane.gov.co/files/censo2018/informacion-tecnica/CNPV-2018-NBI.xlsx
- DANE IPM Geoportal: https://geoportal.dane.gov.co/visipm/
- MinTIC datos.gov.co: https://www.datos.gov.co/resource/fut2-keu8.csv
- Policía SIEDCO: https://portalsiedco.policia.gov.co:4443/extensions/PortalPublico/index.html
- DNP TerriData: https://terridata.dnp.gov.co/
- DANE Proyecciones: https://www.dane.gov.co/index.php/estadisticas-por-tema/demografia-y-poblacion/proyecciones-de-poblacion
