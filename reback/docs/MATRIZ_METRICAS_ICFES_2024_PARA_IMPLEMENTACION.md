# Matriz de Metricas ICFES 2024 para Implementacion en Reback

## Proposito

Inventario de metricas y cortes del informe oficial que debemos replicar en la plataforma para comparabilidad 1:1 y luego extender.

## A. Estructura de comparacion oficial

| Bloque | Corte principal | Corte secundario |
|---|---|---|
| Caracterizacion poblacional | Calendario (A/B) | sexo, sector, zona, NSE, etnia, discapacidad, migrante |
| Resultados globales | Puntaje global | sexo, sector, zona, NSE, departamento, tendencia 2014-2024 |
| Resultados por prueba | Lectura, Matematicas, Ciencias, Sociales, Ingles | sexo, sector, zona, NSE, tendencia 2017-2024 |
| Niveles de desempeno | Niveles 1-4 por prueba | calendario A/B, evolucion anual |
| Entorno y aprendizaje | educacion padres, TIC, libros, tiempo internet/lectura | calendario A/B, diferencia de puntaje |

## B. Indicadores concretos a replicar

## B1. Base poblacional

- Total evaluados por anio y calendario.
- Distribucion por sexo (% y conteo).
- Distribucion por sector (% y conteo).
- Distribucion por zona (% y conteo).
- Distribucion por NSE (% y conteo).
- Conteo y porcentaje de poblacion:
  - con discapacidad
  - migrante
  - grupos etnicos

## B2. Desempeno global

- Puntaje global promedio por anio y calendario.
- Desviacion estandar global por anio y calendario.
- Puntaje global por:
  - sexo
  - sector
  - zona
  - NSE
  - departamento

## B3. Desempeno por prueba

- Puntaje promedio por prueba y anio.
- Desviacion estandar por prueba y anio.
- Puntaje por prueba segmentado por:
  - sexo
  - sector
  - zona
  - NSE
- Evolucion 2017-2024 por prueba.

## B4. Niveles

- Distribucion porcentual niveles 1-4 por prueba y anio.
- En Ingles: distribucion por niveles MCER.
- Cambio interanual de participacion en niveles bajos (1-2) y altos (3-4).

## B5. Factores asociados (no causal)

- Diferencia de puntaje segun:
  - educacion de la madre
  - educacion del padre
  - acceso a internet
  - tenencia de computador
  - cantidad de libros
  - tiempo de uso de internet
  - tiempo de lectura diaria

## C. Metodologia minima documentada para cada indicador

Para cada metrica publicar:

- Universo (quienes entran al calculo).
- Grano de agregacion.
- Formula exacta.
- Campos fuente.
- Reglas de calidad y exclusiones.
- Fecha de corte.
- Comparacion con valor oficial (delta absoluto y porcentual).

## D. Estado actual en Reback (resumen rapido)

- Disponible:
  - Puntaje global por anio.
  - Puntaje por prueba.
  - Segmentacion por sector y territorio.
  - Algunos campos de niveles de desempeno.
- Pendiente o inconsistente:
  - Sexo y NSE en capa gold de comparacion.
  - Zona urbana/rural con dominio confiable.
  - Reconciliacion canonica contra cifras oficiales.
  - Factores de entorno consolidados en un fact table de uso analitico.

## E. Orden recomendado de implementacion

1. Capa de normalizacion de dominios (`sector`, `zona`, `sexo`, `nse`).
2. Modelo canonico oficial-compatible por calendario.
3. Serie por prueba + niveles.
4. Factores asociados del cuestionario.
5. Dashboard de benchmark oficial vs Reback.

## F. Regla de oro para comunicacion externa

Ningun indicador debe salir como "equivalente oficial" si no tiene:

- metodo documentado,
- universo equivalente,
- y validacion de delta contra fuente ICFES.
