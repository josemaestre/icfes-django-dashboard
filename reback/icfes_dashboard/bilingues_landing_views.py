"""SEO landing pages for bilingual schools (colegios bilingues)."""
import json
import logging

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.cache import cache_page

from .db_utils import get_duckdb_connection, resolve_schema

logger = logging.getLogger(__name__)

# Reuse the same alias dict pattern as geo_landing_views for slug resolution.
_DEPARTAMENTO_SLUG_ALIASES = {
    "san-andres": "San Andr",
    "norte-santander": "Norte de Santander",
    "valle": "Valle del Cauca",
    "bogota": "Bogotá",
}


def _meta_compact(text):
    return " ".join((text or "").split()).strip()


def _trim_meta(text, max_len):
    value = _meta_compact(text)
    if len(value) <= max_len:
        return value
    cut = value[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return f"{cut}…"


def _fit_meta_description(text, min_len=110, max_len=155):
    value = _trim_meta(text, max_len)
    if len(value) >= min_len:
        return value
    extra = (
        " Incluye puntajes de inglés, puntaje global y enlaces por departamento y municipio."
    )
    return _trim_meta(f"{value}{extra}", max_len)


def _default_og_image(base_url):
    return f"{base_url}/static/images/logo-dark-full.png"


def _build_base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _resolve_departamento(conn, departamento_slug):
    rows = conn.execute(
        resolve_schema("""
            SELECT DISTINCT departamento
            FROM gold.fct_agg_colegios_ano
            WHERE departamento IS NOT NULL AND departamento != ''
            ORDER BY departamento
        """)
    ).fetchall()
    for (departamento,) in rows:
        if slugify(departamento) == departamento_slug:
            return departamento
    alias_fragment = _DEPARTAMENTO_SLUG_ALIASES.get(departamento_slug)
    if alias_fragment:
        for (departamento,) in rows:
            if alias_fragment.lower() in departamento.lower():
                return departamento
    return None


def _resolve_municipio(conn, departamento, municipio_slug):
    rows = conn.execute(
        resolve_schema("""
            SELECT DISTINCT municipio
            FROM gold.fct_agg_colegios_ano
            WHERE departamento = ?
              AND municipio IS NOT NULL AND municipio != ''
            ORDER BY municipio
        """),
        [departamento],
    ).fetchall()
    for (municipio,) in rows:
        if slugify(municipio) == municipio_slug:
            return municipio
    return None


def _fetch_bilingues(conn, latest_year, departamento=None, municipio=None):
    """
    Returns bilingual schools for the given year/location.
    Uses gold.dim_colegios_ano.es_bilingue — no silver join needed.
    """
    geo_filters = []
    geo_params = [latest_year]
    if departamento:
        geo_filters.append("a.departamento = ?")
        geo_params.append(departamento)
    if municipio:
        geo_filters.append("a.municipio = ?")
        geo_params.append(municipio)
    extra_where = (" AND " + " AND ".join(geo_filters)) if geo_filters else ""

    query = f"""
        SELECT
            a.nombre_colegio,
            a.departamento,
            a.municipio,
            a.sector,
            ROUND(a.avg_punt_ingles, 1) AS avg_ingles,
            ROUND(a.avg_punt_global, 1) AS avg_global,
            a.total_estudiantes,
            a.ranking_nacional,
            COALESCE(s.slug, '') AS slug
        FROM gold.fct_agg_colegios_ano a
        JOIN gold.dim_colegios_ano d
            ON a.colegio_bk = d.colegio_bk AND CAST(a.ano AS INTEGER) = CAST(d.ano AS INTEGER)
        LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = a.colegio_bk
        WHERE CAST(a.ano AS INTEGER) = ?
          AND d.es_bilingue = TRUE
          AND a.total_estudiantes >= 5
          AND a.nombre_colegio IS NOT NULL
          AND a.sector != 'SINTETICO'
          {extra_where}
        ORDER BY a.avg_punt_ingles DESC NULLS LAST
        LIMIT 100
    """
    return conn.execute(resolve_schema(query), geo_params).fetchall()


def _render_bilingues(request, *, rows, latest_year, location_name, canonical_path,
                      departamento=None, departamento_slug=None,
                      municipio=None, municipio_slug=None):
    base_url = _build_base_url(request)
    canonical_url = f"{base_url}{canonical_path}"
    og_image = _default_og_image(base_url)

    if municipio:
        title = f"Colegios bilingues en {municipio}, {departamento} | ICFES {latest_year}"
        description = (
            f"Listado de colegios bilingues en {municipio} ({departamento}) con resultados ICFES {latest_year}. "
            "Puntaje en inglés, puntaje global y comparación por sector."
        )
        keywords = (
            f"colegios bilingues {municipio.lower()}, "
            f"colegios bilingues {departamento.lower()} {latest_year}, "
            "icfes bilingue"
        )
    elif departamento:
        title = f"Colegios bilingues en {departamento} | ICFES {latest_year}"
        description = (
            f"Ranking de colegios bilingues en el departamento de {departamento} según resultados "
            f"ICFES {latest_year}. Incluye puntaje en inglés y puntaje global."
        )
        keywords = (
            f"colegios bilingues {departamento.lower()}, "
            f"ranking bilingue {departamento.lower()} {latest_year}, "
            "colegios bilingues colombia"
        )
    else:
        title = f"Mejores colegios bilingues de Colombia | ICFES {latest_year}"
        description = (
            f"Ranking nacional de los mejores colegios bilingues de Colombia según ICFES {latest_year}. "
            "Puntaje en inglés, nivel MCER y comparación público vs privado."
        )
        keywords = (
            f"mejores colegios bilingues colombia {latest_year}, "
            "ranking colegios bilingues, colegios bilingues icfes"
        )

    title = _trim_meta(title, 65)
    description = _fit_meta_description(description, min_len=110, max_len=155)

    schema_data = json.dumps(
        [
            {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "@id": f"{canonical_url}#webpage",
                "url": canonical_url,
                "name": title,
                "description": description,
                "inLanguage": "es-CO",
            }
        ],
        ensure_ascii=False,
    )

    normalized_rows = [
        {
            "nombre": row[0],
            "departamento": row[1],
            "departamento_slug": slugify(row[1]) if row[1] else "",
            "municipio": row[2],
            "municipio_slug": slugify(row[2]) if row[2] else "",
            "sector": row[3],
            "avg_ingles": float(row[4]) if row[4] is not None else None,
            "avg_global": float(row[5]) if row[5] is not None else None,
            "estudiantes": int(row[6]) if row[6] else 0,
            "ranking_nacional": int(row[7]) if row[7] else None,
            "slug": row[8],
        }
        for row in rows
    ]

    # Breadcrumb links
    breadcrumbs = [{"label": "Inicio", "url": "/"}]
    breadcrumbs.append({"label": "Colegios bilingues (Nacional)", "url": "/icfes/colegios-bilingues/"})
    if departamento and departamento_slug:
        breadcrumbs.append({
            "label": departamento,
            "url": f"/icfes/departamento/{departamento_slug}/colegios-bilingues/",
        })
    if municipio and municipio_slug and departamento_slug:
        breadcrumbs.append({
            "label": municipio,
            "url": f"/icfes/departamento/{departamento_slug}/municipio/{municipio_slug}/colegios-bilingues/",
        })

    return render(
        request,
        "icfes_dashboard/bilingues_landing.html",
        {
            "rows": normalized_rows,
            "latest_year": latest_year,
            "location_name": location_name,
            "departamento": departamento,
            "departamento_slug": departamento_slug,
            "municipio": municipio,
            "municipio_slug": municipio_slug,
            "breadcrumbs": breadcrumbs,
            "seo": {
                "title": title,
                "description": description,
                "keywords": keywords,
                "og_image": og_image,
            },
            "canonical_url": canonical_url,
            "structured_data_json": schema_data,
        },
    )


@cache_page(60 * 60 * 6)
def bilingues_nacional_page(request):
    try:
        with get_duckdb_connection() as conn:
            latest_year = conn.execute(
                resolve_schema(
                    "SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_agg_colegios_ano"
                )
            ).fetchone()[0]
            if not latest_year:
                raise Http404("No hay datos disponibles")
            rows = _fetch_bilingues(conn, latest_year)

        return _render_bilingues(
            request,
            rows=rows,
            latest_year=latest_year,
            location_name="Colombia",
            canonical_path="/icfes/colegios-bilingues/",
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in bilingues_nacional_page: %s", e)
        raise Http404("Error al cargar colegios bilingues")


@cache_page(60 * 60 * 6)
def bilingues_departamento_page(request, dept):
    try:
        with get_duckdb_connection() as conn:
            latest_year = conn.execute(
                resolve_schema(
                    "SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_agg_colegios_ano"
                )
            ).fetchone()[0]
            if not latest_year:
                raise Http404("No hay datos disponibles")
            departamento = _resolve_departamento(conn, dept)
            if not departamento:
                raise Http404("Departamento no encontrado")
            canonical_slug = slugify(departamento)
            rows = _fetch_bilingues(conn, latest_year, departamento=departamento)

        return _render_bilingues(
            request,
            rows=rows,
            latest_year=latest_year,
            location_name=departamento,
            canonical_path=f"/icfes/departamento/{canonical_slug}/colegios-bilingues/",
            departamento=departamento,
            departamento_slug=canonical_slug,
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in bilingues_departamento_page (%s): %s", dept, e)
        raise Http404("Error al cargar colegios bilingues")


@cache_page(60 * 60 * 6)
def bilingues_municipio_page(request, dept, muni):
    try:
        with get_duckdb_connection() as conn:
            latest_year = conn.execute(
                resolve_schema(
                    "SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_agg_colegios_ano"
                )
            ).fetchone()[0]
            if not latest_year:
                raise Http404("No hay datos disponibles")
            departamento = _resolve_departamento(conn, dept)
            if not departamento:
                raise Http404("Departamento no encontrado")
            municipio = _resolve_municipio(conn, departamento, muni)
            if not municipio:
                raise Http404("Municipio no encontrado")
            canonical_dept_slug = slugify(departamento)
            canonical_muni_slug = slugify(municipio)
            rows = _fetch_bilingues(
                conn, latest_year, departamento=departamento, municipio=municipio
            )

        return _render_bilingues(
            request,
            rows=rows,
            latest_year=latest_year,
            location_name=f"{municipio}, {departamento}",
            canonical_path=(
                f"/icfes/departamento/{canonical_dept_slug}"
                f"/municipio/{canonical_muni_slug}/colegios-bilingues/"
            ),
            departamento=departamento,
            departamento_slug=canonical_dept_slug,
            municipio=municipio,
            municipio_slug=canonical_muni_slug,
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in bilingues_municipio_page (%s, %s): %s", dept, muni, e)
        raise Http404("Error al cargar colegios bilingues")
