# Analisis Comparativo: ICFES Oficial 2024 vs Plataforma Reback

## Objetivo

Contrastar los resultados oficiales del informe nacional Saber 11 (2024) con los indicadores que actualmente expone nuestro stack de datos (`dbt + DuckDB + Django`) para identificar coincidencias, diferencias y acciones de mejora.

## Fuentes usadas

- Informe oficial: `c:\Users\joseg\OneDrive\Desktop\icfes\to -claUDE-INFORME_NACIONAL_RESULTADOS_SABER_11_2024 (1).pdf`
- Extraccion de texto del PDF: `c:\proyectos\tmp_icfes_2024.txt`
- Datos del proyecto:
  - `gold.fact_icfes_analytics`
  - `gold.fact_icfes_resumen_global`
  - `gold.fct_agg_colegios_ano`
  - `gold.fct_estadisticas_anuales`
  - `gold.dim_colegios`

## 1) Puntos clave del informe oficial ICFES (Saber 11 - 2024)

### Participacion y perfil poblacional (calendario A)

- Participacion 2024 calendario A: **498.583** estudiantes.
- Crecimiento 2014 -> 2024: **+7,5 %** (de 463.722 a 498.583).
- Composicion por sector: **80 % oficial** y **20 % no oficial**.
- Composicion por zona: **82 % urbana**.
- Estudiantes con discapacidad que presentaron la prueba: **8.725**.

### Resultados globales (calendario A)

- Promedio global nacional: **260**.
- Sector no oficial: **290**.
- Sector oficial: **252**.
- NSE 4: **307** vs NSE 1: **236**.
- Zona urbana: **265** vs zona rural: **235**.
- Hombres: **265** vs mujeres: **256**.

### Resultados globales (calendario B)

- Promedio 2024: **318**.
- Hombres: **322**.
- Zona rural: **330** vs urbana: **317**.
- Se reporta que en calendario B la poblacion presente es 100 % de instituciones no oficiales.

### Resultados territoriales (calendario A)

- Departamentos con promedio mas alto: **Quindio y Santander (277)**.
- Promedio mas bajo: **Choco (210)**.
- El informe indica **21 de 33 departamentos** por debajo del promedio nacional.

## 2) Lo que muestra hoy nuestra data (corte 2024)

### Cobertura temporal

- Nuestras tablas gold llegan a 2024 (`min_ano=1996`, `max_ano=2024`).

### Resultados globales calculados en proyecto

- `gold.fact_icfes_analytics` (promedio simple por estudiante, 2024): **255,38** (676.508 registros).
- `gold.fct_agg_colegios_ano` + `dim_colegios` (calendario A, ponderado por estudiantes, sectores oficial/no oficial): **253,93**.
- `gold.fct_agg_colegios_ano` + `dim_colegios` (calendario B, ponderado por estudiantes): **310,19**.

### Por sector (calendario A, ponderado)

- No oficial: **272,29**
- Oficial: **248,40**
- Brecha no oficial - oficial en nuestro sistema: **23,89 puntos**

### Por departamento (calendario A, ponderado)

- Altos: Boyaca (272,19), Bogota DC (271,16), Santander (269,57), Quindio (268,69).
- Bajo: Choco (209,48).

## 3) Comparacion directa (oficial vs nuestro sistema)

## Metricas comparables de alto nivel

| Metrica | ICFES oficial 2024 | Reback 2024 | Diferencia |
|---|---:|---:|---:|
| Global calendario A | 260,00 | 253,93 | -6,07 |
| Global calendario B | 318,00 | 310,19 | -7,81 |
| Sector A - No oficial | 290,00 | 272,29 | -17,71 |
| Sector A - Oficial | 252,00 | 248,40 | -3,60 |
| Brecha sector A (No oficial - Oficial) | 38,00 | 23,89 | -14,11 |
| Minimo departamental (A, Choco) | 210,00 | 209,48 | -0,52 |

## Coincidencias

- Se mantiene el patron de brecha: no oficial > oficial.
- Choco aparece como el extremo inferior en ambos sistemas.
- Santander y Quindio aparecen en el grupo alto en ambos enfoques.

## Diferencias relevantes

- Los niveles absolutos de puntaje en nuestra plataforma son sistematicamente menores frente al oficial (entre ~3 y ~18 puntos segun corte).
- La brecha entre sectores se reduce notablemente en nuestra data frente al reporte oficial.

## 4) Por que difieren los dos sistemas

## Diferencias metodologicas

- **Unidad de analisis**:
  - ICFES: resultados oficiales construidos con su metodologia institucional y su poblacion reportada por calendario.
  - Reback: modelos derivados (por estudiante, por colegio-ano y agregados), con transformaciones propias.
- **Poblacion**:
  - ICFES reporta separaciones explicitas por calendario y por perfiles poblacionales.
  - En nuestras tablas hay categorias adicionales (`SINTETICO`, `NULL`) que alteran promedios y comparabilidad.
- **Definicion de metrica**:
  - Dependiendo de tabla y ponderacion (promedio simple, ponderado por estudiantes, promedio de promedios), el resultado cambia materialmente.

## Hallazgos de calidad de datos internos (importante)

- En `gold.fact_icfes_resumen_global`, el campo `cole_zona_ubicacion` contiene valores de departamento (ej. `ANTIOQUIA`, `BOGOTA`, `CHOCO`) en lugar de dominios esperados tipo `URBANA/RURAL`.
- En 2024 aparecen `98.581` estudiantes con `cole_naturaleza = NULL` y `98.333` registros sector `SINTETICO` (en `fct_agg_colegios_ano`), lo que impacta comparaciones por sector.
- `gold.fct_estadisticas_anuales` muestra `promedio_nacional=265,39` para 2024, inconsistente con `gold.fact_icfes_analytics` (255,38) para el mismo ano.

## 5) Implicaciones para producto y analitica

- Hoy no debemos presentar como "equivalentes oficiales" los promedios de la plataforma sin aclarar metodologia.
- El comparativo con fuentes oficiales es valioso y debe formalizarse como modulo de validacion de confianza.
- La mayor oportunidad esta en estandarizar una metrica canonica de "promedio nacional" y "brecha sectorial" alineada con ICFES.

## 6) Recomendaciones concretas (priorizadas)

1. Definir una **metrica canonica oficial-compatible** para dashboard y API (misma poblacion, mismo corte, misma ponderacion).
2. Crear un **modelo dbt de reconciliacion** `gold.fct_reconciliacion_icfes_oficial` con columnas:
   - metrica
   - valor_oficial
   - valor_plataforma
   - delta_abs
   - delta_pct
   - periodo
3. Corregir mapeo de `cole_zona_ubicacion` y agregar test de dominio (`accepted_values`) en dbt.
4. Tratar `SINTETICO` y `NULL` de forma explicita en la capa gold (reglas de inclusion/exclusion documentadas).
5. Agregar en `docs/` una pagina de metodologia de indicadores para que negocio/marketing no mezclen metricas no comparables.

## 7) Conclusiones ejecutivas

- El informe oficial confirma los patrones estructurales que nuestro proyecto ya detecta (brechas por sector y desigualdad territorial).
- Sin embargo, hay diferencias numericas relevantes entre ambos sistemas que impiden afirmar equivalencia directa hoy.
- Con una capa de reconciliacion metodologica y limpieza puntual de datos, el proyecto puede pasar de "analitica potente" a "analitica auditable frente a fuente oficial".

## 8) Marco metodologico ICFES para replicar en Reback

## Como ICFES estructura sus estadisticas

- Segmenta por **calendario** (A y B) y compara evolucion temporal.
- Reporta resultados por:
  - Puntaje global.
  - Puntaje por prueba (Lectura Critica, Matematicas, Ciencias Naturales, Sociales y Ciudadanas, Ingles).
  - Distribucion por **niveles de desempeno** (y niveles MCER para Ingles).
- Cruza cada resultado por **sexo, sector, zona, NSE, departamento**.
- Agrega analisis de **condiciones de entorno**:
  - Educacion de madre/padre.
  - Acceso a internet.
  - Tenencia de computador.
  - Libros en hogar.
  - Tiempo de internet.
  - Tiempo de lectura.

## Conceptos metodologicos clave a incorporar textualmente en nuestra metodologia

- Diseño centrado en evidencias (DCE).
- Estimacion de puntajes con teoria de respuesta al item (TRI).
- Escala 0-100 para pruebas y 0-500 para global.
- Ponderacion del global: peso 3 para Lectura/Matematicas/Ciencias; peso 1 para Sociales/Ingles.
- Criterio de inclusion de poblacion para analisis estadistico (evaluados con respuesta valida).

## 9) Matriz de comparacion recomendada (ICFES vs Reback)

| Dimension | Metrica ICFES | Estado en Reback | Accion |
|---|---|---|---|
| Calendario | A vs B (global y por prueba) | Parcial | Formalizar tabla canonica por calendario. |
| Sexo | Hombres vs mujeres (global y por prueba) | No implementado en gold actual | Incorporar sexo desde fuente individual y exponerlo en gold. |
| NSE | Comparativos NSE 1..4 | No implementado en gold actual | Construir `dim_nse` y joins para indicadores oficiales. |
| Sector | Oficial vs no oficial | Implementado con ruido (`SINTETICO`/`NULL`) | Normalizar dominio y documentar reglas de inclusion. |
| Zona | Urbana vs rural | Inconsistente (`cole_zona_ubicacion` mal mapeado) | Corregir mapeo y agregar tests de calidad. |
| Territorio | Departamento/municipio | Implementado | Alinear nombres/codigos con referencia oficial. |
| Niveles por prueba | Niveles 1-4 y MCER | Parcial (`desempeno_*` existe) | Estandarizar salida y series 2017-2024 como ICFES. |
| Entorno familiar | Educacion padres, TIC, libros, tiempo | No consolidado | Crear fact table de factores asociados con diferencias de puntaje. |

## 10) Apartado nuevo sugerido para el producto

## Nombre sugerido

`Benchmark ICFES Oficial vs Reback`

## Bloques del apartado

1. **Comparacion canonica 2024**:
   - Global A/B.
   - Por prueba A/B.
   - Brechas por sector, sexo, zona y NSE.
2. **Comparacion territorial**:
   - Top y bottom por departamento.
   - Brecha contra promedio nacional.
3. **Factores asociados (estilo ICFES)**:
   - Internet/computador/libros/educacion de padres/uso de internet/lectura.
4. **Panel de trazabilidad metodologica**:
   - Definicion de universo.
   - Formula usada.
   - Tabla fuente.
   - Fecha de corte.
   - Diferencia frente al oficial.

## 11) Backlog tecnico minimo para llegar a paridad y superarla

1. Crear `gold.fct_icfes_oficial_benchmark` (grano: anio, calendario, dimension, categoria, metrica).
2. Crear `gold.fct_factores_asociados` (anio, calendario, factor, categoria, puntaje_promedio, n).
3. Estandarizar dominios:
   - `sector`: OFICIAL/NO OFICIAL.
   - `zona`: URBANA/RURAL.
   - `sexo`: H/M.
   - `nse`: 1/2/3/4.
4. Definir pruebas de calidad dbt:
   - `accepted_values` para dominios.
   - `not_null` para llaves de segmentacion.
   - reconciliacion de conteos con tabla base por anio/calendario.
5. Publicar `METODOLOGIA_INDICADORES.md` con formulas, filtros y equivalencias oficiales.
6. Agregar en dashboard un toggle:
   - `Vista Oficial-Compatible`.
   - `Vista Extendida Reback` (nuestro diferencial).

## 12) Como superarlos (enfoque estrategico)

- No competir solo en promedio global; competir en **profundidad diagnostica accionable**.
- Mantener indicadores equivalentes al oficial para confianza institucional.
- Encima de eso, ofrecer:
  - Alertas tempranas por riesgo (modelos ML).
  - Simulacion de impacto de intervenciones.
  - Priorizacion territorial por retorno esperado.
  - Seguimiento continuo (no solo corte anual).

Con esto, Reback queda no solo comparable con ICFES, sino util para decision operativa diaria.
