# SEO Architecture - ICFES Analytics

## Resumen
ICFES Analytics publica miles de paginas SEO dinamicas sobre desempeno escolar en Colombia. La arquitectura debe priorizar:
- escalabilidad
- consistencia de URLs
- crawlabilidad HTML
- estabilidad de sitemaps

## Capas de arquitectura
1. Home / hubs principales
2. Rankings y categorias
3. Geografia (departamento y municipio)
4. Fichas de colegio (nucleo SEO)
5. Hubs tematicos nuevos (cuadrante y supero prediccion)

## Principios tecnicos
- URL canonica unica por entidad.
- Redireccion 301 para variantes.
- Contenido principal server-rendered en HTML.
- Enlazado interno entre niveles para fortalecer descubrimiento.

## Regla critica: Sitemap inmutable
`/sitemap.xml` y familia de sitemaps ya estan avanzados en Google.

Por defecto NO cambiar:
- estructura
- rutas
- nomenclatura
- patron de paginacion

Si hay cambio inevitable:
- compatibilidad backward
- rollout por fases
- monitoreo en Search Console

## Riesgos a evitar
- duplicacion por slugs inconsistentes
- paginas huerfanas sin enlaces internos
- templates con contenido principal vacio
- cambios de URL sin redirects
- bloqueos de crawling por HTML no renderizado

## Politica para cambios futuros
Todo PR que toque SEO programatico debe incluir:
- impacto en URLs
- impacto en sitemap
- impacto en canonical
- validacion de linking interno
- plan de rollback

## Indicadores de control
- 404/410 no controlados
- cobertura indexada por tipo de pagina
- profundidad de crawl
- crecimiento de URLs validas en sitemap
