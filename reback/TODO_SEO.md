# TODO SEO (ICFES Dashboard)

## Indexacion y descubrimiento
- [ ] Registrar el dominio en Google Search Console.
- [ ] Enviar el sitemap: `https://<dominio>/sitemap.xml`.
- [ ] Verificar que `robots.txt` permite `/icfes/colegio/` y referencia el sitemap.
- [ ] Confirmar que `sitemap.xml` incluye `sitemap-static.xml` y `sitemap-icfes-*.xml`.

## Tecnico
- [ ] Definir `ALLOWED_HOSTS` para el dominio final.
- [ ] Forzar HTTPS (ya en Railway) y redireccionar HTTP -> HTTPS.
- [ ] Configurar redireccion 301 del dominio antiguo al nuevo (si aplica).
- [ ] Asegurar `canonical` en las landings (apunta a la URL final).
- [ ] Revisar tiempos de respuesta y cache de paginas SEO (TTFB).

## Dominio (nombre y migracion)
- [ ] Elegir dominio corto y claro (marca + proposito).
- [ ] Verificar disponibilidad y precio.
- [ ] Configurar dominio en Railway.
- [ ] Configurar DNS (CNAME/A) segun Railway.
- [ ] Redireccion 301 del dominio actual al nuevo.
- [ ] Actualizar `ALLOWED_HOSTS` y revisar canonical en landings.

### Ideas de nombre (verificar disponibilidad)
- [ ] icfes-analytics.com
- [ ] icfesdata.com
- [ ] colegiosicfes.com
- [ ] icfesranking.com
- [ ] icfesreport.com
- [ ] icfesinsights.com
- [ ] icfesinfo.com
- [ ] resultadosicfes.com
- [ ] icfescomparador.com
- [ ] icfescolegios.com

## Contenido por landing
- [ ] `title` unico: "ICFES {Colegio} | {Municipio}".
- [ ] `meta description` unico con nombre y ciudad.
- [ ] `h1` con nombre del colegio.
- [ ] Contenido minimo: puntajes, comparaciones, contexto municipal/departamental.
- [ ] CTA claro: "Ver reporte completo", "Comparar con otros", "Descargar informe".

## Enlazado interno
- [ ] Listados/indices por ciudad y departamento con enlaces a landings.
- [ ] Buscador/autocomplete que genere enlaces reales.
- [ ] Enlazar desde dashboard a la landing del colegio.

## Datos estructurados
- [ ] Agregar JSON-LD basico (Organization/School) por colegio.
- [ ] Incluir `addressLocality` (municipio) y `addressRegion` (departamento).

## Analitica
- [ ] Medir trafico organico por slug.
- [ ] Medir conversion por landing (CTA -> registro/pago).

## Operacion
- [ ] Automatizar regeneracion de slugs y validar consistencia en prod.
- [ ] Revisar errores 404 en `/icfes/colegio/*` y arreglar slugs faltantes.
