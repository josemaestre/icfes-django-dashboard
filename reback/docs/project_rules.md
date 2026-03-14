# Project Rules - ICFES Analytics

## Objetivo
Mantener una arquitectura SEO programatica estable para miles de paginas sin romper indexacion ni consistencia tecnica.

## Reglas obligatorias
- Escalabilidad: todo cambio debe funcionar para miles de URLs sin logica manual por pagina.
- No duplicacion: evitar contenido y rutas duplicadas con la misma intencion de busqueda.
- Consistencia de URLs: una sola forma canonica por entidad (slug estable y normalizado).
- HTML crawlable: contenido principal renderizado en HTML, con encabezados y enlaces visibles para bots.
- No romper sitemap: no cambiar estructura, ubicacion ni convenciones actuales de `sitemap.xml` y sitemaps derivados.

## Contrato de Sitemap (bloqueante)
No se permite sin aprobacion explicita:
- Cambiar nombres de archivos sitemap ya indexados.
- Cambiar patrones de paginacion de sitemaps.
- Mover rutas sitemap actuales.
- Alterar jerarquia que Google ya conoce.

Si se requiere evolucion:
1. Mantener compatibilidad hacia atras.
2. Hacer rollout en paralelo.
3. Verificar Search Console antes de retirar rutas antiguas.

## Canonicalizacion y slugs
- Departamento/municipio/colegio deben usar slug unico canonico.
- Toda variante no canonica debe redirigir 301 a la URL canonica.
- Evitar mezclar mayusculas/minusculas en rutas publicas.

## Linking interno
- Toda pagina SEO debe enlazar a nivel superior y lateral relevante:
  - Home/hub correspondiente.
  - Categoria relacionada.
  - Entidades hermanas (cuando aplique).
- Evitar paginas huerfanas.

## Calidad minima por template SEO
- Titulo y meta description unicos por URL.
- H1 unico y alineado con intencion.
- Breadcrumbs crawlables.
- Schema valido (solo tipos que apliquen).
- Secciones de contenido no vacias.

## Checklist pre-merge (SEO)
- [ ] No se rompen rutas existentes indexadas.
- [ ] No se crean duplicados canibalizados.
- [ ] Canonical correcto en pagina.
- [ ] HTML principal visible sin depender de JS.
- [ ] Sitemap sin cambios estructurales.
- [ ] Enlaces internos actualizados.
- [ ] Prueba sobre muestra de URLs (home, hub, depto, muni, colegio).

## Checklist post-deploy
- [ ] Respuesta 200 en rutas objetivo y 301 en variantes no canonicas.
- [ ] Sitemap sirve igual que antes.
- [ ] Sin aumento anomalo de 404/410 no controlados.
- [ ] Crawl stats estables en Search Console.
