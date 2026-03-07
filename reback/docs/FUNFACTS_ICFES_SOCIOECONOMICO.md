# Fun Facts: ICFES + Datos Socioeconómicos
**Última actualización:** 2026-03-02
**Fuentes cruzadas:** `fct_agg_colegios_ano` (gold) × `dim_municipio_nbi` × `dim_municipio_conectividad` × `dim_ano_contexto`

---

## Metodología General

### Join key municipio
Los colegios en `fct_agg_colegios_ano` tienen un campo `colegio_bk` con código DANE de 12 dígitos.
El código de municipio (5 dígitos DANE) se extrae así:

```sql
SUBSTRING(colegio_bk, 2, 5) AS codigo_municipio
-- Ej: colegio_bk = '311001027188'  →  codigo_municipio = '11001' (Bogotá)
```

### Notas sobre la escala de puntajes
- **1996–1999:** Escala 0–300 con pocas materias (formato antiguo). Puntajes ~155–158.
- **2000–2009:** Reforma ICFES — nuevas materias, nueva escala. Puntajes saltan a ~220.
- **2010 en adelante:** Pruebas Saber 11 — nuevo formato estandarizado. Escala 0–500. Puntajes ~220–260.

⚠️ **No comparar puntajes pre-2000 con post-2000 directamente.**

---

## BLOQUE 1 — Pobreza Estructural (NBI)

### Fuente NBI
- Archivo: `seeds/contexto/dim_municipio_nbi.csv`
- Origen: DANE — Censo CNPV 2018 (estático)
- Cobertura: 1,123 municipios (promedio NBI nacional: 22.9%)

---

### FACT 1 — La brecha de la pobreza: 55 puntos

```sql
WITH scores AS (
    SELECT SUBSTRING(colegio_bk, 2, 5) AS cod_mun, AVG(avg_punt_global) AS puntaje
    FROM gold.fct_agg_colegios_ano WHERE ano = '2023' GROUP BY cod_mun
),
joined AS (
    SELECT s.puntaje, n.pct_nbi_total,
        CASE
            WHEN n.pct_nbi_total < 10  THEN '1. NBI < 10% (baja pobreza)'
            WHEN n.pct_nbi_total < 25  THEN '2. NBI 10-25% (moderada)'
            WHEN n.pct_nbi_total < 50  THEN '3. NBI 25-50% (alta)'
            ELSE                            '4. NBI >= 50% (extrema)'
        END AS cat
    FROM scores s JOIN dim_municipio_nbi n ON n.codigo_municipio = s.cod_mun
)
SELECT cat, COUNT(*) n_mun, ROUND(AVG(puntaje),1) promedio FROM joined GROUP BY cat ORDER BY cat
```

**Resultado (2023):**

| Nivel NBI | Municipios | Puntaje prom. |
|-----------|-----------|---------------|
| NBI < 10% (baja pobreza) | 236 | **257.9** |
| NBI 10–25% (moderada) | 501 | 242.8 |
| NBI 25–50% (alta) | 244 | 226.8 |
| NBI ≥ 50% (extrema) | 67 | **202.8** |

**Insight:** 55 puntos separan los extremos — casi una desviación estándar completa. Cada 10 puntos de NBI adicionales ≈ -5.5 puntos ICFES.

---

### FACT 4 — La brecha privado/público es mayor donde más duele

| Nivel NBI | Privado | Público | Brecha |
|-----------|---------|---------|--------|
| NBI < 10% | 276.1 | 256.4 | 19.7 pts |
| NBI 10–25% | 248.2 | 238.5 | 9.7 pts |
| NBI 25–50% | 237.9 | 221.3 | 16.6 pts |
| NBI ≥ 50% | **230.3** | **201.1** | **29.2 pts** |

**Insight:** En municipios de pobreza extrema, pagar un colegio privado compra 29 puntos extra. La brecha es 50% mayor que en municipios ricos. Implicación para campaña: familias en zonas pobres con colegio privado son perfiles de alta motivación educativa.

---

### FACT 3 — Los colegios héroes de La Guajira y Córdoba

Colegios con puntaje global > 270 en municipios con NBI > 40% (2023):

| Colegio | Municipio | Depto | Puntaje | Ranking Nal. | NBI% | Sector |
|---------|-----------|-------|---------|-------------|------|--------|
| Colegio Albania | Albania | La Guajira | 340.4 | #181 | 59.2% | Privado |
| Inst. Pedagógico de Maicao | Maicao | La Guajira | 321.9 | #494 | 59.2% | Privado |
| Jardín y Colegio El Divino Niño | Maicao | La Guajira | 320.0 | #535 | 59.2% | Privado |
| Inst. Educ. Filadelfia | San Andrés de Sotavento | Córdoba | 294.3 | #1369 | 72.6% | Privado |

**Insight:** Son casi todos privados. En zonas de pobreza extrema, los colegios privados de bajo costo son enclaves de excelencia académica. San Andrés de Sotavento (NBI 72.6%) tiene múltiples colegios entre los 2,000 mejores del país.

---

### FACT 5 — Municipios que superan su nivel de pobreza esperado

Regresión lineal simple: `puntaje_esperado = 249.5 - 0.99 × pct_nbi`

| Municipio | Depto | Puntaje real | Esperado | Exceso | NBI% |
|-----------|-------|-------------|---------|--------|------|
| San Jacinto | Bolívar | 233.4 | 157.0 | **+76 pts** | 93.4% |
| El Carmen | Nort. Santander | 261.2 | 201.3 | +60 pts | 48.7% |
| Puerto Colombia | Atlántico | 298.6 | 240.4 | +58 pts | 9.2% |
| Nobsa | Boyacá | 299.9 | 245.5 | +54 pts | 4.0% |
| Cubará | Boyacá | 242.0 | 189.0 | +53 pts | 61.1% |
| Pamplona | Nort. Santander | 293.9 | 240.9 | +53 pts | 8.7% |

**Insight:** Boyacá tiene 4 de los 12 municipios que más superan su esperado — fuerte tradición educativa, colegios técnicos y minería (Nobsa tiene acerías). San Jacinto (Bolívar, NBI 93.4%) supera en 76 pts — candidato a estudio de caso.

---

### FACT 8 — Los ricos mejoran, los pobres empeoran

Evolución de puntaje promedio por nivel NBI entre 2010 y 2023:

| Nivel NBI | Puntaje 2010 | Puntaje 2023 | Cambio |
|-----------|-------------|-------------|--------|
| NBI < 10% | 249.5 | 257.9 | **+8.4** |
| NBI 10–25% | 242.1 | 242.8 | +0.7 |
| NBI 25–50% | 234.2 | 226.6 | **-7.5** |
| NBI ≥ 50% | 226.7 | 204.3 | **-22.4** |

**Insight:** La brecha educativa está en expansión activa. Mientras los municipios prósperos mejoran, los de pobreza extrema han perdido 22 puntos en 13 años. El sistema educativo amplifica la desigualdad.

---

### FACT 10 — La inasistencia escolar es el predictor más brutal

Componente `comp_inasistencia` del NBI = % de niños en edad escolar sin estudiar.

| Inasistencia | Municipios | Puntaje ICFES |
|-------------|-----------|---------------|
| < 5% | 989 | 241.5 |
| 5–10% | 49 | 214.2 (-27 pts) |
| 10–20% | 9 | 204.5 (-37 pts) |

**Insight:** La tasa de inasistencia escolar es más predictiva que el acceso a agua, hacinamiento o calidad de vivienda. Si los niños no van al colegio, el efecto sobre los que sí van es severo (menos recursos, peores docentes, aulas vacías).

---

## BLOQUE 2 — Conectividad Internet (MinTIC)

### Fuente conectividad
- Archivo: `seeds/contexto/dim_municipio_conectividad.csv`
- Origen: MinTIC — datos.gov.co dataset `n48w-gutb` (Q3-2023)
- Cobertura: 1,117 municipios

---

### FACT 2 — El COVID no fue el apocalipsis que creíamos

| Nivel conectividad | Puntaje 2019 | Puntaje 2020 | Delta COVID | Puntaje 2021 | Puntaje 2022 |
|--------------------|-------------|-------------|-------------|-------------|-------------|
| Sin internet | 227.0 | 227.0 | **0.0** | 226.9 | 231.2 |
| Baja cobertura (<20%) | 236.7 | 236.8 | +0.1 | 234.5 | 238.2 |
| Media cobertura (20–50%) | 229.7 | 228.9 | -0.8 | 229.3 | 233.3 |
| Alta cobertura (>50%) | 234.1 | 234.3 | +0.3 | 232.8 | 237.5 |

**Insight:** La caída real del COVID fue en 2021 (no 2020), y fue modesta (~2 pts en zonas conectadas). Los municipios sin internet no cayeron durante la pandemia — posiblemente porque directamente no presentaron el examen en 2020.

---

### FACT 7 — Internet ayuda más al inglés que a las matemáticas

Correlación de Pearson entre `pct_residencial` (cobertura internet) y puntaje por materia (2023):

| Materia | Correlación con internet |
|---------|-------------------------|
| **Inglés** | **0.145** ← más sensible |
| Lectura Crítica | 0.138 |
| Sociales/Ciudadanas | 0.120 |
| C. Naturales | 0.100 |
| **Matemáticas** | **0.095** ← menos sensible |

**Insight:** Netflix, YouTube, música y redes sociales en inglés. Las matemáticas son más "de aula" — la conectividad no las mueve tanto. Para campañas en zonas de alta conectividad, el énfasis en inglés/bilingüismo puede ser el gancho más efectivo.

---

## BLOQUE 3 — Generaciones y Era Tecnológica

### Fuente
- Archivo: `seeds/contexto/dim_ano_contexto.csv`
- Join: `ano_ctx.ano = CAST(fct_agg_colegios_ano.ano AS INTEGER)`

---

### GEN 1 — Puntaje por generación de estudiantes

> El año del examen ICFES corresponde a estudiantes nacidos ~17 años antes.

| Generación | Años ICFES | Puntaje prom. |
|-----------|-----------|---------------|
| Millennials | 1996–2008 | ~155–226 |
| Millennials tardíos | 2009–2011 | ~220–248 |
| Zillennials | 2012–2014 | ~238–248 |
| Gen Z temprana | 2015–2016 | 249–257 |
| Gen Z | 2017–2023 | 243–253 |
| Gen Z / Alpha | 2024 | 251.5 |

⚠️ El salto 1999→2000 (158→224) es un cambio de formato del examen, no mejora real. El salto 2009→2010 (220→248) es la transición a Pruebas Saber 11.

**Insight:** La Gen Z temprana (2015–2016, en plena era del smartphone maduro + acuerdo de paz) tiene los puntajes más altos de la historia. La Gen Z "core" retrocede levemente — posiblemente por saturación digital o fatiga pandémica.

---

### GEN 2 — Puntaje por era tecnológica

```sql
CASE
    WHEN chatgpt_disponible THEN 'Era IA (2022+)'
    WHEN smartphones_masivos THEN 'Era Smartphones (2012-2021)'
    WHEN youtube_existe THEN 'Era YouTube (2005-2011)'
    ELSE 'Pre-Internet (hasta 2004)'
END AS era
```

| Era | Años | Prom. global | Prom. inglés | Prom. mat. |
|-----|------|-------------|-------------|------------|
| Pre-Internet (hasta 2004) | 9 | 192.0* | 22.9* | 46.1 |
| Era YouTube (2005–2011) | 7 | 224.3 | 44.0 | 45.3 |
| Era Smartphones (2012–2021) | 10 | 246.8 | 48.6 | 48.9 |
| Era IA (2022+) | 3 | 249.9 | 50.5 | 50.5 |

*Pre-Internet incluye escala antigua 1996-1999, comparación parcialmente sesgada por cambio de formato.

**Insight:** Cada transición tecnológica coincide con mejoras en inglés. La Era IA ya muestra leve mejora adicional — pero solo tenemos 3 años de datos. La materia que más creció: inglés (+27 pts de Pre-Internet a Smartphones).

---

### GEN 3 — Efecto postconflicto en departamentos históricamente violentos

Comparación puntaje promedio antes (2010–2016) vs después (2017–2023) del Acuerdo de Paz:

| Departamento | Pre-acuerdo | Post-acuerdo | Cambio |
|-------------|------------|-------------|--------|
| Caquetá | 226.7 | 236.4 | **+9.7** |
| Córdoba | 228.0 | 238.3 | **+10.3** |
| Arauca | 240.4 | 243.9 | +3.5 |
| Cauca | 228.7 | 228.1 | -0.6 |
| La Guajira | 229.5 | 224.5 | -5.0 |
| Putumayo | 232.2 | 229.2 | -3.0 |
| Vichada | 227.0 | 217.3 | -9.7 |
| Chocó | 207.8 | 194.6 | **-13.2** |
| Guainía | 234.5 | 208.1 | **-26.4** |

**Insight:** El efecto postconflicto fue MIXTO. Caquetá y Córdoba mejoraron (mayor presencia estatal, menos desplazamiento). Guainía y Chocó empeoraron significativamente — posiblemente por reorganización de grupos armados, vacío de poder o migración de docentes. La paz firmada ≠ paz en el territorio para todos.

---

## BLOQUE 4 — Presidentes y Períodos de Gobierno

### PRES 1 — Puntaje promedio por gobierno (serie histórica)

```sql
SELECT
    CAST(f.ano AS INTEGER) AS anio,
    ROUND(AVG(f.avg_punt_global), 1) AS prom_global,
    ROUND(AVG(f.avg_punt_ingles), 1) AS prom_ingles,
    a.presidente,
    a.postconflicto, a.pandemia_covid, a.paro_nacional
FROM gold.fct_agg_colegios_ano f
JOIN gold.dim_tiempo a ON a.ano = CAST(f.ano AS INTEGER)
GROUP BY anio, a.presidente, a.postconflicto, a.pandemia_covid, a.paro_nacional
ORDER BY anio
```

**Tabla completa:**

| Año | Global | Inglés | Mat. | Presidente | Postconflicto | COVID | Paro |
|-----|--------|--------|------|------------|:-------------:|:-----:|:----:|
| 1996 | 155.9 | 0* | 49.1 | Samper | – | – | – |
| 1997 | 157.8 | 0* | 49.4 | Samper | – | – | – |
| 1998 | 158.2 | 0* | 49.1 | Pastrana | – | – | – |
| 1999 | 158.6 | 0* | 49.9 | Pastrana | – | – | – |
| 2000 | 224.1 | 41.0 | 49.0 | Pastrana | – | – | – |
| 2001 | 217.2 | 42.1 | 43.9 | Pastrana | – | – | – |
| 2002 | 220.3 | 41.9 | 42.3 | Uribe | – | – | – |
| 2003 | 217.0 | 41.5 | 41.7 | Uribe | – | – | – |
| 2004 | 218.5 | 39.5 | 40.8 | Uribe | – | – | – |
| 2005 | 219.5 | 43.5 | 44.2 | Uribe | – | – | – |
| 2006 | 225.9 | 42.8 | 45.5 | Uribe | – | – | – |
| 2007 | 217.6 | 43.2 | 44.5 | Uribe | – | – | – |
| 2008 | 218.7 | 41.4 | 44.1 | Uribe | – | – | – |
| 2009 | 220.8 | 44.0 | 43.7 | Uribe | – | – | – |
| 2010 | 248.0 | 50.0 | 49.4 | Santos | – | – | – |
| 2011 | 219.7 | 43.1 | 45.5 | Santos | – | – | – |
| 2012 | 238.7 | 44.1 | 45.5 | Santos | – | – | – |
| 2013 | 238.4 | 44.6 | 44.6 | Santos | – | – | – |
| 2014 | 248.3 | 50.1 | 49.5 | Santos | – | – | – |
| 2015 | 249.0 | 50.7 | 49.8 | Santos | – | – | – |
| **2016** | **257.2** | 52.1 | 50.5 | Santos | **SI** | – | – |
| 2017 | 253.1 | 49.4 | 49.4 | Santos | SI | – | – |
| 2018 | 249.5 | 50.6 | 49.8 | Duque | SI | – | – |
| 2019 | 245.1 | 48.5 | 50.3 | Duque | SI | – | **Paro** |
| 2020 | 245.2 | 46.9 | 50.3 | Duque | SI | **COVID** | – |
| 2021 | 243.6 | 48.8 | 49.1 | Duque | SI | COVID | **Paro** |
| 2022 | 248.0 | 49.7 | 50.1 | Petro | SI | – | – |
| 2023 | 250.2 | 50.7 | 50.5 | Petro | SI | – | – |
| 2024 | 251.5 | 50.9 | 50.9 | Petro | SI | – | – |

*Inglés no medido o con escala diferente en 1996–1999.

---

### PRES 2 — Brecha público vs privado por gobierno

| Gobierno | Oficial | Privado | Brecha |
|---------|---------|---------|--------|
| Uribe II (2006–2010) | 241.5 | 258.5 | 17.0 pts |
| Santos I (2010–2014) | 227.2 | 251.0 | 23.8 pts |
| Petro (2022–2026) | 239.3 | 271.2 | **31.9 pts** |

**Insight:** Bajo el gobierno de Petro, la brecha privado-público alcanza su máximo histórico (31.9 pts), a pesar de las políticas de gratuidad en educación pública. Los colegios privados siguen acelerando mientras los públicos no logran alcanzarlos.

---

## BLOQUE 5 — Insights Estratégicos para Campañas

### Segmentación de prospectos por contexto socioeconómico

| Perfil | Característica | Potencial campaña |
|--------|---------------|-------------------|
| **Alta receptividad** | Privado + NBI > 30% | Familia ya invierte en edu. pese a pobreza → muy motivada |
| **Movilidad social** | Público + municipio "sobre-rendimiento" | Estudiante excelente en contexto difícil → busca oportunidades |
| **Digital ready** | Conectividad alta + inglés fuerte | Candidato a programas online o bilinguismo |
| **Rezago recuperable** | NBI 10-25% + tendencia mejorando | Municipio en transición → timing ideal para prospección |
| **Zona PDET con mejora** | Caquetá, Córdoba | Postconflicto funciona → familias más estables y receptivas |

---

## Reproducibilidad

### Cargar seeds en DuckDB para análisis ad-hoc

```python
import duckdb, pandas as pd

con = duckdb.connect("tmp_dev_copy.duckdb", read_only=True)

nbi = pd.read_csv("seeds/contexto/dim_municipio_nbi.csv", dtype={"codigo_municipio": str})
nbi["codigo_municipio"] = nbi["codigo_municipio"].str.zfill(5)
conn = pd.read_csv("seeds/contexto/dim_municipio_conectividad.csv", dtype={"codigo_municipio": str})
conn["codigo_municipio"] = conn["codigo_municipio"].str.zfill(5)
ano_ctx = pd.read_csv("seeds/contexto/dim_ano_contexto.csv")

con.register("nbi_temp", nbi)
con.register("conn_temp", conn)
con.register("ano_ctx", ano_ctx)
```

### Ejecutar seeds en dbt (producción)

```bash
dbt seed --select dim_municipio_nbi dim_municipio_conectividad dim_ano_contexto dim_municipio_geo
dbt run --select dim_tiempo dim_municipio_contexto
```

Una vez ejecutado, los joins usan directamente `gold.dim_municipio_nbi`, etc.
