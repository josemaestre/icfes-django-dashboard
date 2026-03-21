# TODO SEO - ICFES Analytics

## Objetivo

Este documento define un backlog SEO priorizado para ICFES Analytics, enfocado en mejorar calidad tecnica, consistencia programatica e indexacion sin romper la arquitectura actual.

La regla central es simple:

- no romper URLs indexadas
- no romper `sitemap.xml`
- no introducir duplicacion
- no depender de JS para el contenido principal

Este TODO no propone una re-arquitectura. Propone mejoras incrementales, compatibles con el estado actual del proyecto.

---

## Estado general actual

La base SEO del proyecto es buena.

Fortalezas visibles hoy:

- arquitectura programatica clara por capas
- fichas de colegio con contenido rico y schema
- paginas geograficas y longtail server-rendered
- uso de canonical en templates SEO
- redirects de slugs canonicos en varias vistas
- family de sitemaps ya segmentada por tipo de pagina
- control de thin content en fichas de colegio
- linking interno razonable entre hubs y entidades

Eso significa que el proyecto no esta "mal en SEO". Esta en una fase donde conviene bajar deuda tecnica y endurecer consistencia.

---

## Prioridades

### P0 - Critico

Son cambios pequenos o medianos que reducen riesgo SEO real y no deberian esperar.

### P1 - Importante

Mejoran consistencia, control y escalabilidad SEO. No son una emergencia, pero si conviene resolverlos pronto.

### P2 - Mejora continua

No corrigen una falla inmediata, pero fortalecen la capacidad del proyecto para crecer sin deterioro tecnico.

---

## P0 - Critico

### 1. Hacer dinamico el ano de `sitemap_cuadrante`

#### Problema

El sitemap de cuadrantes esta amarrado a `2024` en vez de tomar el ultimo ano disponible del dataset.

Archivo relevante:

[sitemap_views.py](c:\proyectos\www\reback\icfes_dashboard\sitemap_views.py)

#### Riesgo SEO

- si el dataset avanza a otro ano, el sitemap puede quedar desactualizado
- Google puede seguir descubriendo una cobertura incompleta de URLs de cuadrante
- se genera inconsistencia entre contenido vivo y sitemap

#### Que hacer

- reemplazar el filtro fijo por `MAX(CAST(ano AS INTEGER))`
- mantener exactamente la misma ruta del sitemap
- no cambiar nombres ni estructura de salida

#### Criterio de terminado

- el sitemap devuelve URLs del ultimo ano disponible
- no cambia la estructura XML
- no cambia la ruta publica del sitemap

---

### 2. Unificar `lastmod` de sitemaps con fecha real del dataset

#### Problema

Hoy algunos sitemaps usan fecha actual del servidor y otros usan fecha real de actualizacion del dataset.

Archivo relevante:

[sitemap_views.py](c:\proyectos\www\reback\icfes_dashboard\sitemap_views.py)

#### Riesgo SEO

- `lastmod` deja de ser una senal confiable
- puede provocar recrawl innecesario
- dificulta interpretar cambios reales del inventario indexable

#### Que hacer

- usar una misma politica de `lastmod`
- preferir fecha real del dataset cuando la URL depende de datos
- reservar fecha actual solo para URLs realmente estaticas

#### Criterio de terminado

- todos los sitemaps dinamicos usan una politica consistente
- queda documentado cuando usar `datetime.now()` y cuando usar `_dataset_lastmod_iso`

---

### 3. Verificar y documentar `robots.txt`

#### Problema

No esta claro dentro del repo como se gestiona `robots.txt`.

#### Riesgo SEO

- dependencia invisible de infraestructura
- baja trazabilidad de cambios
- riesgo de bloqueo accidental de crawling

#### Que hacer

- confirmar si `robots.txt` vive fuera del repo
- si vive fuera, documentarlo en `docs/`
- si conviene, moverlo a gestion versionada dentro del proyecto

#### Criterio de terminado

- existe una fuente de verdad clara para `robots.txt`
- cualquier cambio futuro queda auditado y entendible

---

## P1 - Importante

### 4. Centralizar reglas de canonicalizacion y slugs

#### Problema

La logica de canonical y slug esta bien implementada, pero esta repartida entre varias vistas.

Archivos relevantes:

[geo_landing_views.py](c:\proyectos\www\reback\icfes_dashboard\geo_landing_views.py)
[longtail_landing_views.py](c:\proyectos\www\reback\icfes_dashboard\longtail_landing_views.py)
[views_cuadrante.py](c:\proyectos\www\reback\icfes_dashboard\views_cuadrante.py)
[views_potencial.py](c:\proyectos\www\reback\icfes_dashboard\views_potencial.py)

#### Riesgo SEO

- drift entre implementaciones
- variantes canonicamente correctas en un modulo pero no en otro
- mantenimiento mas costoso a futuro

#### Que hacer

- extraer helpers comunes para:
  - normalizacion de departamento
  - construccion de slug canonico
  - redirect a URL canonica
- definir una unica politica por entidad

#### Criterio de terminado

- toda canonicalizacion critica se apoya en helpers compartidos
- baja la duplicacion de reglas

---

### 5. Auditar inclusion en sitemap vs indexabilidad real

#### Problema

Ya existe cierta alineacion, pero conviene auditarla de forma formal.

Ejemplo positivo actual:

- fichas thin content usan `noindex, follow`
- el sitemap de colegios excluye escuelas con baja densidad minima

Archivos relevantes:

[landing_views_simple.py](c:\proyectos\www\reback\icfes_dashboard\landing_views_simple.py)
[sitemap_views.py](c:\proyectos\www\reback\icfes_dashboard\sitemap_views.py)

#### Riesgo SEO

- que entren al sitemap paginas que no deberian indexarse
- que existan paginas indexables importantes que queden fuera del sitemap
- cobertura desigual entre familias de paginas

#### Que hacer

- revisar por familia:
  - colegio
  - departamento
  - municipio
  - ranking sector
  - materia
  - mejoraron
  - bilingues
  - cuadrante
  - potencial
- documentar criterio de inclusion / exclusion

#### Criterio de terminado

- cada familia tiene criterio explicito de indexabilidad
- el sitemap refleja ese criterio

---

### 6. Estandarizar schema por tipo de pagina

#### Problema

Las fichas de colegio ya estan fuertes, pero falta una matriz formal de que schema usa cada tipo de landing.

#### Riesgo SEO

- inconsistencias entre plantillas
- sobreuso o subuso de tipos schema
- mayor dificultad para validar rich results

#### Que hacer

- definir una matriz simple:
  - home
  - colegio
  - geo
  - ranking
  - cuadrante
  - potencial
- usar solo tipos que realmente apliquen

#### Propuesta inicial

- colegio: `School`, `Article`, `BreadcrumbList`, `FAQPage`
- geo: `WebPage`, `BreadcrumbList`
- ranking/longtail: `WebPage`, `BreadcrumbList`, opcional `ItemList`
- cuadrante: `WebPage`, `BreadcrumbList`, opcional `ItemList`
- potencial: `WebPage`, `BreadcrumbList`, opcional `ItemList`

#### Criterio de terminado

- cada familia de pagina tiene schema definido y consistente

---

### 7. Confirmar fallback real de `og_image`

#### Problema

Los templates consumen `seo.og_image`, pero no esta documentado si siempre llega con valor valido.

Archivos relevantes:

[school_landing_simple.html](c:\proyectos\www\reback\icfes_dashboard\templates\icfes_dashboard\school_landing_simple.html)
[geo_landing_simple.html](c:\proyectos\www\reback\icfes_dashboard\templates\icfes_dashboard\geo_landing_simple.html)
[longtail_landing_simple.html](c:\proyectos\www\reback\icfes_dashboard\templates\icfes_dashboard\longtail_landing_simple.html)
[cuadrante_landing.html](c:\proyectos\www\reback\icfes_dashboard\templates\icfes_dashboard\landing\cuadrante_landing.html)
[potencial_landing.html](c:\proyectos\www\reback\icfes_dashboard\templates\icfes_dashboard\landing\potencial_landing.html)

#### Riesgo SEO

- previews sociales incompletos
- metadatos inconsistentes entre familias de pagina

#### Que hacer

- validar en vistas si siempre se construye una imagen valida
- si no, definir fallback estable y versionado

#### Criterio de terminado

- toda URL SEO publica responde con `og:image` valido

---

## P2 - Mejora continua

### 8. Crear una matriz maestra de tipos de pagina SEO

#### Objetivo

Tener un inventario tecnico que diga para cada familia:

- URL pattern
- canonical
- index/noindex
- schema
- inclusion en sitemap
- linking interno minimo
- criterio de calidad minima

#### Beneficio

- baja errores al agregar nuevas landings
- facilita revisiones futuras
- sirve como checklist pre-merge

---

### 9. Definir un checklist automatico para PRs SEO

#### Objetivo

Que cualquier PR que toque SEO programatico pase por una validacion minima.

#### Checklist sugerido

- ruta publica no cambia o tiene redirect
- canonical existe y apunta a la URL correcta
- sitemap no cambia estructura
- pagina mantiene contenido HTML crawlable
- no se crean paginas huerfanas
- el tipo schema sigue la matriz definida

#### Beneficio

- baja regresiones invisibles

---

### 10. Medir coverage por familia de pagina

#### Objetivo

Construir una vista simple de control SEO por familia:

- total URLs vivas
- total URLs en sitemap
- total URLs noindex
- total URLs con canonical
- total URLs con schema

#### Beneficio

- permite detectar drift estructural antes de que se vuelva un problema serio

---

## Cosas que NO debemos tocar sin justificacion fuerte

### 1. La estructura de `sitemap.xml`

No cambiar:

- nombres de archivos sitemap
- rutas sitemap
- paginacion existente
- jerarquia ya conocida por Google

Archivo clave:

[sitemap_views.py](c:\proyectos\www\reback\icfes_dashboard\sitemap_views.py)

---

### 2. Los patrones de URL ya indexados

Especialmente:

- `/icfes/colegio/.../`
- `/icfes/departamento/.../`
- `/icfes/departamento/.../municipio/.../`
- `/icfes/ranking/.../`
- `/icfes/cuadrante/.../`
- `/icfes/supero-prediccion/.../`

Si alguna URL cambia, debe haber redirect y rollout muy controlado.

---

### 3. La logica de `noindex` para thin content sin evidencia

La logica actual protege calidad del indice.

Archivo relevante:

[landing_views_simple.py](c:\proyectos\www\reback\icfes_dashboard\landing_views_simple.py)

No conviene relajarla solo por intuicion. Si se toca, debe ser con datos de cobertura/indexacion.

---

## Orden recomendado de ejecucion

### Fase 1 - Bajo riesgo, alto impacto

1. Hacer dinamico `sitemap_cuadrante`
2. Unificar politica de `lastmod`
3. Documentar `robots.txt`
4. Confirmar fallback real de `og_image`

### Fase 2 - Consistencia estructural

5. Centralizar canonicalizacion y slugs
6. Auditar inclusion en sitemap vs indexabilidad real
7. Estandarizar schema por tipo de pagina

### Fase 3 - Gobernanza SEO

8. Crear matriz maestra de tipos de pagina
9. Definir checklist automatico para PRs SEO
10. Medir coverage por familia

---

## Definicion de terminado

Podemos considerar que este TODO SEO esta bien ejecutado cuando:

- los sitemaps son consistentes y dinamicos
- cada familia de pagina tiene politica clara de indexacion
- canonical y slugs siguen una sola regla compartida
- schema esta estandarizado por tipo de pagina
- `robots.txt` deja de ser una caja negra
- los cambios SEO futuros tienen checklist y control

---

## Recomendacion final

No conviene abrir un frente gigante de cambios SEO al mismo tiempo.

La mejor estrategia para este proyecto es:

- pequenos cambios tecnicos
- cero ruptura de rutas
- cero ruptura de sitemap
- monitoreo despues de cada fase

Este proyecto ya tiene una base SEO fuerte. El trabajo correcto ahora no es reinventarlo. Es endurecerlo.
