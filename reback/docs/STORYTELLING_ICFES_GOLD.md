# Storytelling ICFES (Gold Layer)

Este guion propone una narrativa ejecutiva de una pagina usando `gold.*` en DuckDB y alineada con los dashboards web actuales.

## Objetivo

Responder tres preguntas de negocio:

1. El sistema mejora o retrocede en resultados ICFES?
2. La desigualdad educativa se esta cerrando o ampliando?
3. Donde actuar primero (territorio/colegio) para reducir riesgo de deterioro?

## Estructura narrativa (10-15 min)

1. Apertura: Tendencia nacional 1996-2024 (nivel sistema)
2. Nudo: Brechas estructurales (sector, territorio, materias)
3. Cierre: Priorizacion accionable (riesgo por colegio/departamento)

## Bloque 1: Tendencia nacional

Mensaje clave:
- El promedio nacional debe leerse junto con dispersion y cobertura (estudiantes/colegios).
- Evitar concluir mejora solo por un cambio de 1-2 puntos sin contexto de variabilidad.

Fuentes:
- `gold.average_by_year`
- `gold.fct_estadisticas_anuales`

## Bloque 2: Brechas estructurales

Mensaje clave:
- La brecha no es unica: sector, territorio y area evaluada muestran dinamicas distintas.
- El foco debe estar en magnitud + tendencia (no solo foto de un ano).

Fuentes:
- `gold.brechas_educativas`
- `gold.convergencia_regional`
- `gold.fct_indicadores_desempeno`

## Bloque 3: Priorizacion de intervencion

Mensaje clave:
- Priorizar donde coinciden: alto riesgo de declive + bajo desempeno actual + alta brecha local.
- El ranking de accion debe ser transparente y replicable.

Fuentes:
- `gold.fct_riesgo_colegios`
- `gold.fct_agg_colegios_ano`
- `gold.fct_indicadores_desempeno`

## Integracion con capa web existente

Pantallas ya alineadas:
- `icfes_dashboard/templates/icfes_dashboard/pages/dashboard-icfes.html`
- `icfes_dashboard/templates/icfes_dashboard/pages/dashboard-brecha.html`

Elementos ya presentes para narrativa:
- Evolucion y resumen general (`tabla-resumen`, `graficoEvolucion`)
- Brecha por materia y tendencia (`chart-brecha-ranking`, `chart-tendencia-brecha`)
- Riesgo (`tabla-top-riesgo`, distribucion y factores)

## Recomendacion operativa semanal

1. Lunes: actualizar corte anual y recalcular resumen ejecutivo.
2. Martes: revisar top 10 departamentos con mayor brecha YoY.
3. Miercoles: revisar top 50 colegios en `nivel_riesgo='Alto'`.
4. Jueves: definir acciones por territorio (academica/gestion/acompanamiento).
5. Viernes: medir avance contra baseline de inicio de ano.

## Nota de calidad de datos

- `gold.sector_region_analysis` esta vacia en `dev.duckdb` (0 filas).
- Estandarizar `sector` (`OFICIAL`, `NO OFICIAL`, `0`, `1`) antes de reportes sensibles.
