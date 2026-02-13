import math
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.utils.text import slugify

from .db_utils import get_duckdb_connection, resolve_schema


SITEMAP_PAGE_SIZE = 40000


def _base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _format_lastmod(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def sitemap_index(request):
    base = _base_url(request)

    with get_duckdb_connection() as conn:
        count_query = "SELECT COUNT(*) FROM gold.dim_colegios_slugs"
        total = conn.execute(resolve_schema(count_query)).fetchone()[0]

    pages = max(1, math.ceil(total / SITEMAP_PAGE_SIZE))

    items = [f"{base}/sitemap-static.xml"]
    items.extend(f"{base}/sitemap-icfes-{i}.xml" for i in range(1, pages + 1))
    items.append(f"{base}/sitemap-departamentos.xml")
    items.append(f"{base}/sitemap-municipios.xml")
    items.append(f"{base}/sitemap-longtail.xml")

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for loc in items:
        xml.append("  <sitemap>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append("  </sitemap>")
    xml.append("</sitemapindex>")

    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_static(request):
    base = _base_url(request)
    lastmod = datetime.now(timezone.utc).date().isoformat()
    urls = [
        f"{base}/landing/",
        f"{base}/pricing/",
        f"{base}/icfes/",
        f"{base}/icfes/colegio/",
        f"{base}/icfes/departamentos/",
        f"{base}/icfes/historico/puntaje-global/",
    ]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for loc in urls:
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>weekly</changefreq>")
        xml.append("    <priority>0.8</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")

    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_icfes(request, page):
    if page < 1:
        return HttpResponse(status=404)

    base = _base_url(request)
    limit = SITEMAP_PAGE_SIZE
    offset = (page - 1) * limit

    query = """
        SELECT slug, created_at
        FROM gold.dim_colegios_slugs
        ORDER BY slug
        LIMIT ? OFFSET ?
    """
    with get_duckdb_connection() as conn:
        rows = conn.execute(resolve_schema(query), [limit, offset]).fetchall()

    if not rows:
        return HttpResponse(status=404)

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for slug, created_at in rows:
        loc = f"{base}/icfes/colegio/{slug}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{_format_lastmod(created_at)}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.6</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")

    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_departamentos(request):
    base = _base_url(request)
    lastmod = datetime.now(timezone.utc).date().isoformat()

    dept_query = """
        SELECT DISTINCT departamento
        FROM gold.fct_agg_colegios_ano
        WHERE departamento IS NOT NULL
          AND departamento != ''
        ORDER BY departamento
    """
    with get_duckdb_connection() as conn:
        dept_rows = conn.execute(resolve_schema(dept_query)).fetchall()

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")

    xml.append("  <url>")
    xml.append(f"    <loc>{escape(f'{base}/icfes/departamentos/')}</loc>")
    xml.append(f"    <lastmod>{lastmod}</lastmod>")
    xml.append("    <changefreq>weekly</changefreq>")
    xml.append("    <priority>0.7</priority>")
    xml.append("  </url>")

    for (departamento,) in dept_rows:
        dept_slug = slugify(departamento)
        loc = f"{base}/icfes/departamento/{dept_slug}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.65</priority>")
        xml.append("  </url>")

    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_municipios(request):
    base = _base_url(request)
    lastmod = datetime.now(timezone.utc).date().isoformat()

    muni_query = """
        SELECT DISTINCT departamento, municipio
        FROM gold.fct_agg_colegios_ano
        WHERE departamento IS NOT NULL
          AND departamento != ''
          AND municipio IS NOT NULL
          AND municipio != ''
        ORDER BY departamento, municipio
    """
    with get_duckdb_connection() as conn:
        muni_rows = conn.execute(resolve_schema(muni_query)).fetchall()

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")

    for departamento, municipio in muni_rows:
        dept_slug = slugify(departamento)
        muni_slug = slugify(municipio)
        loc = f"{base}/icfes/departamento/{dept_slug}/municipio/{muni_slug}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.55</priority>")
        xml.append("  </url>")

    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_longtail(request):
    base = _base_url(request)
    lastmod = datetime.now(timezone.utc).date().isoformat()

    years_query = """
        SELECT DISTINCT CAST(ano AS INTEGER) AS ano
        FROM gold.fct_agg_colegios_ano
        WHERE ano IS NOT NULL
        ORDER BY ano DESC
    """
    with get_duckdb_connection() as conn:
        year_rows = conn.execute(resolve_schema(years_query)).fetchall()

    years = [int(row[0]) for row in year_rows if row[0] is not None]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")

    historic_url = f"{base}/icfes/historico/puntaje-global/"
    xml.append("  <url>")
    xml.append(f"    <loc>{escape(historic_url)}</loc>")
    xml.append(f"    <lastmod>{lastmod}</lastmod>")
    xml.append("    <changefreq>weekly</changefreq>")
    xml.append("    <priority>0.8</priority>")
    xml.append("  </url>")

    for year in years:
        ranking_general = f"{base}/icfes/ranking/colegios/{year}/"
        ranking_math = f"{base}/icfes/ranking/matematicas/{year}/"

        xml.append("  <url>")
        xml.append(f"    <loc>{escape(ranking_general)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.75</priority>")
        xml.append("  </url>")

        xml.append("  <url>")
        xml.append(f"    <loc>{escape(ranking_math)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.75</priority>")
        xml.append("  </url>")

    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_geo(request):
    # Backward-compatible endpoint; keep old URL alive.
    return sitemap_departamentos(request)
