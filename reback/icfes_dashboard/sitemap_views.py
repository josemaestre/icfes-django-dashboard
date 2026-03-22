import math
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.utils.text import slugify

from .db_utils import get_duckdb_connection, resolve_schema
from .views_potencial import DEPT_NAME_CANONICAL


SITEMAP_PAGE_SIZE = 40000


def _base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    raw = configured if configured else request.build_absolute_uri("/")
    parsed = urlparse(raw)

    scheme = "https"
    netloc = parsed.netloc or request.get_host()
    path = parsed.path or ""

    canonical = urlunparse((scheme, netloc, path.rstrip("/"), "", "", ""))
    return canonical.rstrip("/")


def _format_lastmod(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def _dataset_lastmod_iso(conn):
    query = """
        SELECT MAX(fecha_carga)
        FROM gold.fct_agg_colegios_ano
    """
    value = conn.execute(resolve_schema(query)).fetchone()[0]
    return _format_lastmod(value)


def _sector_slug_rows():
    return [("OFICIAL", "oficiales"), ("NO OFICIAL", "privados")]


def _indexable_school_count(conn):
    """
    Keep school sitemap aligned with school_landing_page robots logic:
    noindex when latest total_estudiantes < 5 (thin_content).
    """
    query = """
        WITH latest_school AS (
            SELECT
                h.codigo_dane,
                h.total_estudiantes,
                ROW_NUMBER() OVER (
                    PARTITION BY h.codigo_dane
                    ORDER BY CAST(h.ano AS INTEGER) DESC
                ) AS rn
            FROM gold.fct_colegio_historico h
            WHERE h.codigo_dane IS NOT NULL
        )
        SELECT COUNT(*)
        FROM gold.dim_colegios_slugs s
        JOIN latest_school ls
          ON ls.codigo_dane = s.codigo
         AND ls.rn = 1
        WHERE s.slug IS NOT NULL
          AND s.slug != ''
          AND COALESCE(ls.total_estudiantes, 0) >= 5
    """
    return conn.execute(resolve_schema(query)).fetchone()[0]


def sitemap_index(request):
    base = _base_url(request)

    with get_duckdb_connection() as conn:
        total = _indexable_school_count(conn)

    pages = max(1, math.ceil(total / SITEMAP_PAGE_SIZE))

    items = [f"{base}/sitemap-static.xml"]
    # National school pages (paginated)
    items.extend(f"{base}/sitemap-icfes-{i}.xml" for i in range(1, pages + 1))
    # Geographic hierarchy: departamentos → municipios
    items.append(f"{base}/sitemap-departamentos.xml")
    items.append(f"{base}/sitemap-ranking-sector-departamentos.xml")
    items.append(f"{base}/sitemap-municipios.xml")
    items.append(f"{base}/sitemap-ranking-sector-municipios.xml")
    # National ranking pages
    items.append(f"{base}/sitemap-ranking-sector-nacional.xml")
    # Long-tail and thematic pages
    items.append(f"{base}/sitemap-longtail.xml")
    items.append(f"{base}/sitemap-materias.xml")
    items.append(f"{base}/sitemap-mejoraron.xml")
    items.append(f"{base}/sitemap-bilingues.xml")
    items.append(f"{base}/sitemap-cuadrante.xml")
    items.append(f"{base}/sitemap-potencial.xml")
    items.append(f"{base}/sitemap-motivacional.xml")

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
    # (url, changefreq, priority)
    urls = [
        (f"{base}/",                                "monthly", "1.0"),
        (f"{base}/pricing/",                        "monthly", "0.6"),
        (f"{base}/icfes/ranking/",                  "monthly", "0.9"),
        (f"{base}/icfes/departamentos/",            "monthly", "0.8"),
        (f"{base}/icfes/ingles-seo/",               "yearly",  "0.7"),
        (f"{base}/icfes/historico/puntaje-global/",   "yearly",  "0.7"),
        (f"{base}/icfes/colegios-bilingues/",         "yearly",  "0.7"),
        (f"{base}/icfes/que-es-icfes-analytics/",     "yearly",  "0.8"),
    ]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for loc, changefreq, priority in urls:
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append(f"    <changefreq>{changefreq}</changefreq>")
        xml.append(f"    <priority>{priority}</priority>")
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
        WITH latest_school AS (
            SELECT
                h.codigo_dane,
                h.total_estudiantes,
                ROW_NUMBER() OVER (
                    PARTITION BY h.codigo_dane
                    ORDER BY CAST(h.ano AS INTEGER) DESC
                ) AS rn
            FROM gold.fct_colegio_historico h
            WHERE h.codigo_dane IS NOT NULL
        )
        SELECT s.slug, s.created_at
        FROM gold.dim_colegios_slugs s
        JOIN latest_school ls
          ON ls.codigo_dane = s.codigo
         AND ls.rn = 1
        WHERE s.slug IS NOT NULL
          AND s.slug != ''
          AND COALESCE(ls.total_estudiantes, 0) >= 5
        ORDER BY s.slug
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
          AND ano = (SELECT MAX(ano) FROM gold.fct_agg_colegios_ano)
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
          AND ano = (SELECT MAX(ano) FROM gold.fct_agg_colegios_ano)
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


def sitemap_ranking_sector_index(request):
    base = _base_url(request)
    items = [
        f"{base}/sitemap-ranking-sector-nacional.xml",
        f"{base}/sitemap-ranking-sector-departamentos.xml",
        f"{base}/sitemap-ranking-sector-municipios.xml",
    ]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for loc in items:
        xml.append("  <sitemap>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append("  </sitemap>")
    xml.append("</sitemapindex>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_ranking_sector_nacional(request):
    base = _base_url(request)
    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for _, sector_slug in _sector_slug_rows():
        loc = f"{base}/icfes/ranking/sector/{sector_slug}/colombia/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>weekly</changefreq>")
        xml.append("    <priority>0.9</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_ranking_sector_departamentos(request):
    base = _base_url(request)
    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)
        latest_year_query = "SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_agg_colegios_ano"
        latest_year = conn.execute(resolve_schema(latest_year_query)).fetchone()[0]
        if latest_year is None:
            return HttpResponse(status=404)

        query = """
            SELECT DISTINCT sector, departamento
            FROM gold.fct_colegio_historico
            WHERE CAST(ano AS INTEGER) = ?
              AND sector IN ('OFICIAL', 'NO OFICIAL')
              AND departamento IS NOT NULL
              AND departamento != ''
            ORDER BY sector, departamento
        """
        rows = conn.execute(resolve_schema(query), [latest_year]).fetchall()

    sector_to_slug = dict(_sector_slug_rows())

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for sector, departamento in rows:
        sector_slug = sector_to_slug.get(sector)
        if not sector_slug:
            continue
        dep_slug = slugify(departamento)
        loc = f"{base}/icfes/ranking/sector/{sector_slug}/departamento/{dep_slug}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.85</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_ranking_sector_municipios(request):
    base = _base_url(request)
    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)
        latest_year_query = "SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_agg_colegios_ano"
        latest_year = conn.execute(resolve_schema(latest_year_query)).fetchone()[0]
        if latest_year is None:
            return HttpResponse(status=404)

        # Use fct_colegio_historico (same source as the view) and enforce
        # minimum thresholds to avoid thin-content pages: >= 2 schools and >= 20 students.
        query = """
            SELECT sector, departamento, municipio
            FROM gold.fct_colegio_historico
            WHERE CAST(ano AS INTEGER) = ?
              AND sector IN ('OFICIAL', 'NO OFICIAL')
              AND departamento IS NOT NULL AND departamento != ''
              AND municipio IS NOT NULL AND municipio != ''
              AND total_estudiantes >= 10
            GROUP BY sector, departamento, municipio
            HAVING COUNT(DISTINCT codigo_dane) >= 2
               AND SUM(total_estudiantes) >= 20
            ORDER BY sector, departamento, municipio
        """
        rows = conn.execute(resolve_schema(query), [latest_year]).fetchall()

    sector_to_slug = dict(_sector_slug_rows())

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for sector, departamento, municipio in rows:
        sector_slug = sector_to_slug.get(sector)
        if not sector_slug:
            continue
        dep_slug = slugify(departamento)
        muni_slug = slugify(municipio)
        loc = (
            f"{base}/icfes/ranking/sector/{sector_slug}/departamento/"
            f"{dep_slug}/municipio/{muni_slug}/"
        )
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.8</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_materias(request):
    """Sitemap for /icfes/materia/{materia}/{ano}/ pages."""
    base = _base_url(request)

    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)
        years_rows = conn.execute(
            resolve_schema("""
                SELECT DISTINCT CAST(ano AS INTEGER) AS ano
                FROM gold.fct_agg_colegios_ano
                WHERE ano IS NOT NULL
                ORDER BY ano DESC
            """)
        ).fetchall()

    years = [int(r[0]) for r in years_rows if r[0] is not None]
    materias = ["matematicas", "ingles"]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for materia in materias:
        for year in years:
            loc = f"{base}/icfes/materia/{materia}/{year}/"
            xml.append("  <url>")
            xml.append(f"    <loc>{escape(loc)}</loc>")
            xml.append(f"    <lastmod>{lastmod}</lastmod>")
            xml.append("    <changefreq>monthly</changefreq>")
            xml.append("    <priority>0.7</priority>")
            xml.append("  </url>")
    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_mejoraron(request):
    """Sitemap for /icfes/colegios-que-mas-mejoraron/{ano}/ pages."""
    base = _base_url(request)

    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)
        years_rows = conn.execute(
            resolve_schema("""
                SELECT DISTINCT CAST(ano AS INTEGER) AS ano
                FROM gold.fct_colegio_historico
                WHERE punt_global_ano_anterior IS NOT NULL
                ORDER BY ano DESC
            """)
        ).fetchall()

    years = [int(r[0]) for r in years_rows if r[0] is not None]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for year in years:
        loc = f"{base}/icfes/colegios-que-mas-mejoraron/{year}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.7</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_bilingues(request):
    """Sitemap for /icfes/colegios-bilingues/ and geographic sub-pages."""
    base = _base_url(request)

    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)
        geo_rows = conn.execute(
            resolve_schema("""
                SELECT DISTINCT d.departamento, d.municipio
                FROM gold.dim_colegios_ano d
                WHERE d.es_bilingue = TRUE
                  AND d.departamento IS NOT NULL AND d.departamento != ''
                  AND d.municipio IS NOT NULL AND d.municipio != ''
                  AND CAST(d.ano AS INTEGER) = (
                      SELECT MAX(CAST(ano AS INTEGER)) FROM gold.dim_colegios_ano
                  )
                ORDER BY d.departamento, d.municipio
            """)
        ).fetchall()

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")

    # Nacional
    xml.append("  <url>")
    xml.append(f"    <loc>{escape(f'{base}/icfes/colegios-bilingues/')}</loc>")
    xml.append(f"    <lastmod>{lastmod}</lastmod>")
    xml.append("    <changefreq>monthly</changefreq>")
    xml.append("    <priority>0.75</priority>")
    xml.append("  </url>")

    seen_depts = set()
    for departamento, municipio in geo_rows:
        dept_slug = slugify(departamento)
        muni_slug = slugify(municipio)

        if dept_slug not in seen_depts:
            seen_depts.add(dept_slug)
            loc = f"{base}/icfes/departamento/{dept_slug}/colegios-bilingues/"
            xml.append("  <url>")
            xml.append(f"    <loc>{escape(loc)}</loc>")
            xml.append(f"    <lastmod>{lastmod}</lastmod>")
            xml.append("    <changefreq>monthly</changefreq>")
            xml.append("    <priority>0.65</priority>")
            xml.append("  </url>")

        loc = f"{base}/icfes/departamento/{dept_slug}/municipio/{muni_slug}/colegios-bilingues/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.6</priority>")
        xml.append("  </url>")

    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_cuadrante(request):
    """Sitemap for /icfes/cuadrante/{cuadrante}/ and /icfes/cuadrante/{cuadrante}/{depto}/ pages."""
    base = _base_url(request)
    cuadrantes = ["estrella", "consolidada", "emergente", "alerta"]
    priorities = {
        "estrella":    "0.80",
        "emergente":   "0.80",
        "consolidada": "0.70",
        "alerta":      "0.65",
    }

    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)
        depto_rows = conn.execute(
            resolve_schema("""
                SELECT DISTINCT departamento
                FROM gold.fct_agg_colegios_ano
                WHERE CAST(ano AS INTEGER) = 2024
                  AND departamento IS NOT NULL
                  AND departamento != ''
                ORDER BY departamento
            """)
        ).fetchall()

    deptos = [r[0] for r in depto_rows if r[0]]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")

    for cuadrante in cuadrantes:
        prio = priorities[cuadrante]
        # National page
        loc = f"{base}/icfes/cuadrante/{cuadrante}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>yearly</changefreq>")
        xml.append(f"    <priority>{prio}</priority>")
        xml.append("  </url>")
        # Department pages
        for depto in deptos:
            depto_slug = slugify(depto)
            loc = f"{base}/icfes/cuadrante/{cuadrante}/{depto_slug}/"
            xml.append("  <url>")
            xml.append(f"    <loc>{escape(loc)}</loc>")
            xml.append(f"    <lastmod>{lastmod}</lastmod>")
            xml.append("    <changefreq>yearly</changefreq>")
            xml.append("    <priority>0.60</priority>")
            xml.append("  </url>")

    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_motivacional(request):
    """Sitemap for /icfes/bandas-motivacionales/ — nacional + 33 departamentos."""
    base = _base_url(request)
    lastmod = datetime.now(timezone.utc).date().isoformat()

    query = """
        SELECT DISTINCT departamento
        FROM gold.fct_distribucion_niveles
        WHERE departamento IS NOT NULL
          AND departamento NOT IN ('', 'EXTERIOR', 'SIN INFORMACION')
        ORDER BY departamento
    """
    with get_duckdb_connection() as conn:
        rows = conn.execute(resolve_schema(query)).fetchall()

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")

    # Nacional
    xml.append("  <url>")
    xml.append(f"    <loc>{escape(f'{base}/icfes/bandas-motivacionales/')}</loc>")
    xml.append(f"    <lastmod>{lastmod}</lastmod>")
    xml.append("    <changefreq>monthly</changefreq>")
    xml.append("    <priority>0.75</priority>")
    xml.append("  </url>")

    # Por departamento
    for (departamento,) in rows:
        dept_slug = slugify(departamento)
        loc = f"{base}/icfes/bandas-motivacionales/{dept_slug}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.65</priority>")
        xml.append("  </url>")

    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_potencial(request):
    """Sitemap for /icfes/supero-prediccion/ — schools that exceeded ML prediction."""
    base = _base_url(request)

    with get_duckdb_connection() as conn:
        lastmod = _dataset_lastmod_iso(conn)
        depto_rows = conn.execute(
            resolve_schema("""
                SELECT DISTINCT COALESCE(s.departamento, p.departamento) AS dep
                FROM gold.fct_potencial_educativo p
                LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = p.colegio_bk
                WHERE p.clasificacion IN ('Excepcional', 'Notable')
                  AND COALESCE(s.departamento, p.departamento) IS NOT NULL
                  AND COALESCE(s.departamento, p.departamento) != ''
                ORDER BY 1
            """)
        ).fetchall()

    # Normalize known variant names (e.g. "BOGOTÁ" → "Bogotá DC") then
    # deduplicate by slug, preferring title-case over ALL-CAPS
    raw = sorted(
        [DEPT_NAME_CANONICAL.get(r[0], r[0]) for r in depto_rows if r[0]],
        key=lambda x: (x == x.upper(), x),
    )
    seen: set = set()
    deptos = []
    for d in raw:
        s = slugify(d)
        if s not in seen:
            seen.add(s)
            deptos.append(d)
    sectors = [("oficial", "0.65"), ("privado", "0.65")]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")

    def add_url(loc, priority, changefreq="yearly"):
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append(f"    <lastmod>{lastmod}</lastmod>")
        xml.append(f"    <changefreq>{changefreq}</changefreq>")
        xml.append(f"    <priority>{priority}</priority>")
        xml.append("  </url>")

    # Nacional — todos
    add_url(f"{base}/icfes/supero-prediccion/", "0.80")
    # Nacional por sector
    for s_slug, prio in sectors:
        add_url(f"{base}/icfes/supero-prediccion/{s_slug}/", prio)

    for depto in deptos:
        depto_slug = slugify(depto)
        add_url(f"{base}/icfes/supero-prediccion/{depto_slug}/", "0.65")
        for s_slug, _ in sectors:
            add_url(f"{base}/icfes/supero-prediccion/{depto_slug}/{s_slug}/", "0.55")

    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")
