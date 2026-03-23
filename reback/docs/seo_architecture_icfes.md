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

## Monitoreo en tiempo real (Google Analytics 4)
El informe “Páginas en tiempo real” es clave para detectar incidentes de carga masiva, picos en onboarding y problemas de UX en tráfico orgánico inmediato.

Métricas principales:
- Usuarios activos últimos 30 minutos (ej: 5)
- Visualizaciones últimos 30 minutos (ej: 13)
- Usuarios activos por minuto (ej: 1-2)
- Top rutas de página (`/accounts/signup/`, `/icfes/colegio/...`, `/icfes/departamento/...`, etc.)

Qué validar:
- Que no haya concentraciones inesperadas en páginas con poco contenido SEO (ej. paso de signup) que indican campaña/errores de funnel.
- Que las fichas de colegio (puntos 4) y socio-geográficas (punto 3) aparezcan en top 10 cuando hay campaña local.
- Que no estén registrando rutas de error 4xx/5xx en tiempo real.

Acción operativa:
1. Configurar alertas GA4/BigQuery para decrecimiento de conversión o subida abrupta de session_rate en `/accounts/signup/`.
2. Registrar resumén diario de tráfico en dashboards con top-10 rutas, usuarios activos y vistas.
3. Relacionar con logs de backend de Sitemaps/SSR para verificar origen de visitas (Organic Search vs direct/referral).

Integración con la política de cambios SEO:
- Todo cambio de estructura de URL debe acompañarse de validación explícita en este informe (antes y después de deploy).
- Registrar los 9-10 endpoints más vistos en un release para no perder foco en las páginas críticas.
