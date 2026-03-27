"""
Long-tail SEO landing pages for high-intent ICFES searches.
"""
import json
import logging
from functools import lru_cache

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.cache import cache_page

from .db_utils import get_duckdb_connection, resolve_schema

logger = logging.getLogger(__name__)

# Safe integer cast for `ano` column (VARCHAR in DuckDB).
# Avoids ConversionException when prod DB contains non-numeric rows.
_YEAR_EXPR = (
    "CASE WHEN regexp_matches(CAST(ano AS VARCHAR), '^[0-9]+$') "
    "THEN CAST(ano AS INTEGER) ELSE NULL END"
)
_YEAR_EXPR_H = (
    "CASE WHEN regexp_matches(CAST(h.ano AS VARCHAR), '^[0-9]+$') "
    "THEN CAST(h.ano AS INTEGER) ELSE NULL END"
)
_YEAR_EXPR_F = (
    "CASE WHEN regexp_matches(CAST(f.ano AS VARCHAR), '^[0-9]+$') "
    "THEN CAST(f.ano AS INTEGER) ELSE NULL END"
)


def _build_base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _absolute_url(base_url, path):
    return f"{base_url}/{path.lstrip('/')}"


def _default_og_image(base_url):
    return _absolute_url(base_url, "/icfes/og/default.png")


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
        " Incluye comparativos por departamento, municipio y enlaces a rankings relacionados."
    )
    return _trim_meta(f"{value}{extra}", max_len)


def _available_years(conn):
    query = f"""
        SELECT DISTINCT {_YEAR_EXPR} AS ano
        FROM gold.fct_agg_colegios_ano
        WHERE {_YEAR_EXPR} IS NOT NULL
        ORDER BY ano DESC
    """
    rows = conn.execute(resolve_schema(query)).fetchall()
    return [int(row[0]) for row in rows if row[0] is not None]


# Module-level cache: years list changes at most once a year; no need to hit DB every request.
@lru_cache(maxsize=1)
def _get_cached_years_snapshot():
    """Returns (latest_year, prev_year) from a single DB round-trip, cached in-process."""
    with get_duckdb_connection() as conn:
        return _available_years(conn)


def _latest_snapshot(conn):
    # Use in-process LRU cache for years list — changes at most once a year
    years = _get_cached_years_snapshot()
    if not years:
        raise Http404("No hay datos históricos disponibles")
    latest_year = years[0]
    prev_year = years[1] if len(years) > 1 else None

    updated_query = """
        SELECT MAX(fecha_carga)
        FROM gold.fct_agg_colegios_ano
    """
    updated_at = conn.execute(resolve_schema(updated_query)).fetchone()[0]
    updated_date = updated_at.date().isoformat() if updated_at else None
    return latest_year, prev_year, updated_date


def _sector_from_slug(sector_slug):
    mapping = {
        "oficiales": ("OFICIAL", "públicos"),
        "privados": ("NO OFICIAL", "privados"),
    }
    return mapping.get((sector_slug or "").strip().lower())


@lru_cache(maxsize=16)
def _get_location_pairs(sector_value, year):
    """
    Cached fetch of all (dept, muni, dept_slug, muni_slug) tuples for a sector+year.
    Result is stable within a deployment — cached in-process to avoid repeated full scans.
    Only ~4 unique combinations exist (2 sectors × 2 recent years).
    """
    query = """
        SELECT DISTINCT departamento, municipio
        FROM gold.fct_colegio_historico
        WHERE ano = ?
          AND sector = ?
          AND departamento IS NOT NULL AND departamento != ''
          AND municipio IS NOT NULL AND municipio != ''
    """
    with get_duckdb_connection() as conn:
        rows = conn.execute(resolve_schema(query), [str(year), sector_value]).fetchall()
    return tuple((dept, muni, slugify(dept), slugify(muni)) for (dept, muni) in rows)


def _resolve_location(conn, sector_value, year, departamento_slug, municipio_slug=None):
    """
    Resolve slug(s) → real names using in-process cached location pairs.
    Returns (departamento, municipio) — municipio is None when municipio_slug is not given.
    """
    dept_found = None
    muni_found = None
    for (dept, muni, dept_s, muni_s) in _get_location_pairs(sector_value, year):
        if dept_s != departamento_slug:
            continue
        dept_found = dept
        if municipio_slug is None:
            break
        if muni_s == municipio_slug:
            muni_found = muni
            break
    return dept_found, muni_found


def _resolve_departamento(conn, sector_value, year, departamento_slug):
    dept, _ = _resolve_location(conn, sector_value, year, departamento_slug)
    return dept


def _fetch_top20_rows(conn, latest_year, prev_year, sector_value, departamento=None, municipio=None):
    filters = ["h.sector = ?", "h.total_estudiantes >= 10", "h.nombre_colegio IS NOT NULL"]
    # h.ano is VARCHAR — use string params for the IN clause to avoid CAST errors.
    params = [str(latest_year)]
    if prev_year is not None:
        params.append(str(prev_year))
    else:
        # Keep CTE valid when no previous year is available.
        params.append(str(latest_year))
    params.append(sector_value)

    if departamento:
        filters.append("h.departamento = ?")
        params.append(departamento)
    if municipio:
        filters.append("h.municipio = ?")
        params.append(municipio)

    where_clause = " AND ".join(filters)
    query = f"""
        WITH source AS (
            SELECT
                {_YEAR_EXPR_H} AS ano,
                h.codigo_dane,
                h.nombre_colegio,
                h.departamento,
                h.municipio,
                h.sector,
                h.total_estudiantes,
                h.avg_punt_global,
                h.avg_punt_lectura_critica,
                h.avg_punt_matematicas,
                h.avg_punt_c_naturales,
                h.avg_punt_sociales_ciudadanas,
                h.avg_punt_ingles,
                h.percentil_sector,
                h.cambio_absoluto_global,
                h.cambio_porcentual_global,
                a.avg_global_zscore,
                COALESCE(s.slug, '') AS slug
            FROM gold.fct_colegio_historico h
            LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = h.codigo_dane
            LEFT JOIN gold.fct_agg_colegios_ano a
              ON a.colegio_bk = h.codigo_dane
             AND a.ano = h.ano
            WHERE h.ano IN (?, ?)
              AND {where_clause}
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY ano
                    ORDER BY avg_punt_global DESC NULLS LAST, nombre_colegio
                ) AS ranking_scope
            FROM source
        ),
        current_year AS (
            SELECT * FROM ranked WHERE ano = ?
        ),
        previous_year AS (
            SELECT
                codigo_dane,
                ranking_scope AS ranking_scope_prev,
                avg_punt_global AS avg_punt_global_prev
            FROM ranked
            WHERE ano = ?
        )
        SELECT
            c.nombre_colegio,
            c.departamento,
            c.municipio,
            c.slug,
            ROUND(c.avg_punt_global, 1) AS punt_global,
            ROUND(c.avg_punt_lectura_critica, 1) AS punt_lectura,
            ROUND(c.avg_punt_matematicas, 1) AS punt_matematicas,
            ROUND(c.avg_punt_c_naturales, 1) AS punt_naturales,
            ROUND(c.avg_punt_sociales_ciudadanas, 1) AS punt_sociales,
            ROUND(c.avg_punt_ingles, 1) AS punt_ingles,
            c.ranking_scope,
            p.ranking_scope_prev,
            ROUND(c.cambio_absoluto_global, 2) AS cambio_abs,
            ROUND(c.cambio_porcentual_global, 2) AS cambio_pct,
            ROUND(c.percentil_sector * 100.0, 1) AS percentil_sector_pct,
            c.total_estudiantes,
            ROUND(c.avg_global_zscore, 2) AS z_score_global
        FROM current_year c
        LEFT JOIN previous_year p ON p.codigo_dane = c.codigo_dane
        ORDER BY c.ranking_scope
        LIMIT 20
    """
    params.extend([latest_year, prev_year if prev_year is not None else latest_year])
    rows = conn.execute(resolve_schema(query), params).fetchall()
    return rows


def _normalize_top_rows(rows):
    normalized = []
    for row in rows:
        ranking_current = int(row[10]) if row[10] is not None else None
        ranking_prev = int(row[11]) if row[11] is not None else None
        rank_delta = ranking_prev - ranking_current if ranking_prev and ranking_current else None
        rank_symbol = "↔"
        if rank_delta is not None:
            rank_symbol = "↑" if rank_delta > 0 else ("↓" if rank_delta < 0 else "→")

        normalized.append(
            {
                "nombre": row[0],
                "departamento": row[1],
                "departamento_slug": slugify(row[1]) if row[1] else "",
                "municipio": row[2],
                "municipio_slug": slugify(row[2]) if row[2] else "",
                "slug": row[3],
                "punt_global": float(row[4]) if row[4] is not None else None,
                "punt_lectura": float(row[5]) if row[5] is not None else None,
                "punt_matematicas": float(row[6]) if row[6] is not None else None,
                "punt_naturales": float(row[7]) if row[7] is not None else None,
                "punt_sociales": float(row[8]) if row[8] is not None else None,
                "punt_ingles": float(row[9]) if row[9] is not None else None,
                "ranking_actual": ranking_current,
                "ranking_anterior": ranking_prev,
                "rank_delta": rank_delta,
                "rank_symbol": rank_symbol,
                "cambio_abs": float(row[12]) if row[12] is not None else None,
                "cambio_pct": float(row[13]) if row[13] is not None else None,
                "percentil_sector_pct": float(row[14]) if row[14] is not None else None,
                "estudiantes": int(row[15]) if row[15] is not None else 0,
                "z_score_global": float(row[16]) if row[16] is not None else None,
            }
        )
    return normalized


def _top_departamento_links(rows, sector_slug, limit=6):
    sector_meta = _sector_from_slug(sector_slug)
    sector_label = sector_meta[1] if sector_meta else sector_slug
    links = []
    seen = set()
    for row in rows:
        dept_slug = row.get("departamento_slug") or ""
        dept_name = row.get("departamento") or ""
        if not dept_slug or dept_slug in seen:
            continue
        seen.add(dept_slug)
        links.append(
            {
                "label": f"Ranking {sector_label} en {dept_name}",
                "url": f"/icfes/ranking/sector/{sector_slug}/departamento/{dept_slug}/",
            }
        )
        if len(links) >= limit:
            break
    return links


def _top_municipio_links(rows, sector_slug, limit=8):
    sector_meta = _sector_from_slug(sector_slug)
    sector_label = sector_meta[1] if sector_meta else sector_slug
    links = []
    seen = set()
    for row in rows:
        dept_slug = row.get("departamento_slug") or ""
        mun_slug = row.get("municipio_slug") or ""
        mun_name = row.get("municipio") or ""
        dept_name = row.get("departamento") or ""
        key = (dept_slug, mun_slug)
        if not dept_slug or not mun_slug or key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "label": f"Top {sector_label} en {mun_name}, {dept_name}",
                "url": f"/icfes/ranking/sector/{sector_slug}/departamento/{dept_slug}/municipio/{mun_slug}/",
            }
        )
        if len(links) >= limit:
            break
    return links


def _render_sector_ranking(
    request,
    *,
    sector_slug,
    scope_label,
    scope_slug,
    location_title,
    rows,
    canonical_path,
    updated_date,
    latest_year,
    links=None,
):
    sector_meta = _sector_from_slug(sector_slug)
    if not sector_meta:
        raise Http404("Sector inválido")
    _, sector_label = sector_meta

    seo_title = f"Top 20 colegios {sector_label} {scope_label.lower()} | ICFES {latest_year}"
    seo_description = (
        f"Ranking top 20 de colegios {sector_label} {scope_label.lower()} con datos ICFES {latest_year}. "
        "Incluye puntajes por materia, posición actual, variación anual y percentil sectorial."
    )
    seo_title = _trim_meta(seo_title, 65)
    seo_description = _fit_meta_description(seo_description, min_len=110, max_len=155)

    base_url = _build_base_url(request)
    canonical_url = _absolute_url(base_url, canonical_path)
    og_image = _default_og_image(base_url)
    schema_data = json.dumps(
        [
            {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "@id": f"{canonical_url}#webpage",
                "url": canonical_url,
                "name": seo_title,
                "description": seo_description,
                "inLanguage": "es-CO",
                "dateModified": updated_date,
            }
        ],
        ensure_ascii=False,
    )

    return render(
        request,
        "icfes_dashboard/longtail_landing_simple.html",
        {
            "mode": "ranking_sector",
            "rows": rows,
            "scope_label": scope_label,
            "scope_slug": scope_slug,
            "location_title": location_title,
            "sector_slug": sector_slug,
            "sector_label": sector_label,
            "latest_year": latest_year,
            "updated_date": updated_date,
            "related_links": links or [],
            "seo": {
                "title": seo_title,
                "description": seo_description,
                "og_image": og_image,
                "keywords": (
                    f"top 20 colegios {sector_label} {location_title.lower()}, ranking icfes {latest_year}, "
                    f"colegios {sector_label} colombia"
                ),
            },
            "canonical_url": canonical_url,
            "structured_data_json": schema_data,
        },
    )


def ranking_colegios_hub_page(request):
    """Redirect to the most recent year's ranking page."""
    try:
        with get_duckdb_connection() as conn:
            years = _available_years(conn)
        if not years:
            raise Http404("No hay datos de ranking disponibles")
        return redirect(f"/icfes/ranking/colegios/{years[0]}/", permanent=False)
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in ranking_colegios_hub_page: %s", e)
        raise Http404("Error al cargar la página")


@cache_page(60 * 60 * 6, key_prefix='v2')
def ranking_colegios_year_page(request, ano):
    try:
        year = int(ano)
    except (TypeError, ValueError):
        raise Http404("Año inválido")

    try:
        with get_duckdb_connection() as conn:
            years = _available_years(conn)
            if year not in years:
                raise Http404("Año no disponible")

            query = """
                SELECT
                    f.nombre_colegio,
                    f.departamento,
                    f.municipio,
                    f.sector,
                    ROUND(f.avg_punt_global, 1) AS promedio_global,
                    f.total_estudiantes,
                    COALESCE(s.slug, '') AS slug
                FROM gold.fct_agg_colegios_ano f
                LEFT JOIN gold.dim_colegios_slugs s ON f.colegio_bk = s.codigo
                WHERE f.ano = ?
                  AND f.nombre_colegio IS NOT NULL
                  AND f.sector != 'SINTETICO'
                ORDER BY f.avg_punt_global DESC
                LIMIT 50
            """
            rows = conn.execute(resolve_schema(query), [str(year)]).fetchall()

        title = f"Mejores colegios ICFES {year} en Colombia | Ranking actualizado"
        description = (
            f"Ranking ICFES {year} de colegios en Colombia. "
            "Consulta top colegios por puntaje global, departamento y municipio."
        )
        title = _trim_meta(title, 65)
        description = _fit_meta_description(description, min_len=110, max_len=155)
        canonical_url = request.build_absolute_uri(request.path)
        og_image = _default_og_image(_build_base_url(request))
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

        return render(
            request,
            "icfes_dashboard/longtail_landing_simple.html",
            {
                "mode": "ranking_general",
                "year": year,
                "years_free": years[:4],
                "years_locked": years[4:8],
                "year_base_url": "/icfes/ranking/colegios/",
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "departamento_slug": slugify(row[1]) if row[1] else "",
                        "municipio": row[2],
                        "municipio_slug": slugify(row[2]) if row[2] else "",
                        "sector": row[3],
                        "score": float(row[4]) if row[4] is not None else None,
                        "estudiantes": int(row[5]) if row[5] else 0,
                        "slug": row[6],
                    }
                    for row in rows
                ],
                "related_links": [
                    {"label": "Resultados ICFES por departamento", "url": "/icfes/departamentos/"},
                    {"label": f"Colegios con mejor matemáticas ({year})", "url": f"/icfes/ranking/matematicas/{year}/"},
                    {"label": "Ranking sector público nacional", "url": "/icfes/ranking/sector/oficiales/colombia/"},
                    {"label": "Ranking sector privado nacional", "url": "/icfes/ranking/sector/privados/colombia/"},
                    {"label": "Histórico nacional de puntaje global", "url": "/icfes/historico/puntaje-global/"},
                    {"label": "Colegios estrella en Colombia", "url": "/icfes/cuadrante/estrella/"},
                    {"label": "Colegios que superaron su rendimiento esperado", "url": "/icfes/supero-prediccion/"},
                    {"label": "Evolución motivacional en Colombia", "url": "/icfes/bandas-motivacionales/"},
                ],
                "seo": {
                    "title": title,
                    "description": description,
                    "og_image": og_image,
                    "keywords": (
                        f"mejores colegios icfes {year} colombia, ranking icfes {year}, "
                        "promedio icfes por colegio"
                    ),
                },
                "canonical_url": canonical_url,
                "structured_data_json": schema_data,
            },
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in ranking_colegios_year_page (%s): %s", ano, e)
        raise Http404("Error al cargar ranking de colegios")


@cache_page(60 * 60 * 6)
def ranking_matematicas_year_page(request, ano):
    try:
        year = int(ano)
    except (TypeError, ValueError):
        raise Http404("Año inválido")

    try:
        with get_duckdb_connection() as conn:
            years = _available_years(conn)
            if year not in years:
                raise Http404("Año no disponible")

            query = """
                SELECT
                    f.nombre_colegio,
                    f.departamento,
                    f.municipio,
                    f.sector,
                    ROUND(f.avg_punt_matematicas, 1) AS promedio_matematicas,
                    ROUND(f.avg_punt_global, 1) AS promedio_global,
                    COALESCE(s.slug, '') AS slug
                FROM gold.fct_agg_colegios_ano f
                LEFT JOIN gold.dim_colegios_slugs s ON f.colegio_bk = s.codigo
                WHERE f.ano = ?
                  AND f.nombre_colegio IS NOT NULL
                  AND f.avg_punt_matematicas IS NOT NULL
                  AND f.sector != 'SINTETICO'
                ORDER BY f.avg_punt_matematicas DESC
                LIMIT 50
            """
            rows = conn.execute(resolve_schema(query), [str(year)]).fetchall()

        title = f"Colegios con mejor matemáticas ICFES {year} | Top Colombia"
        description = (
            f"Ranking de colegios con mejor puntaje en matemáticas ICFES {year} en Colombia. "
            "Incluye comparación con puntaje global por colegio."
        )
        title = _trim_meta(title, 65)
        description = _fit_meta_description(description, min_len=110, max_len=155)
        canonical_url = request.build_absolute_uri(request.path)
        og_image = _default_og_image(_build_base_url(request))
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

        return render(
            request,
            "icfes_dashboard/longtail_landing_simple.html",
            {
                "mode": "ranking_matematicas",
                "year": year,
                "years": years[:6],
                "year_base_url": "/icfes/ranking/matematicas/",
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "departamento_slug": slugify(row[1]) if row[1] else "",
                        "municipio": row[2],
                        "municipio_slug": slugify(row[2]) if row[2] else "",
                        "sector": row[3],
                        "score_math": float(row[4]) if row[4] is not None else None,
                        "score_global": float(row[5]) if row[5] is not None else None,
                        "slug": row[6],
                    }
                    for row in rows
                ],
                "related_links": [
                    {"label": "Resultados ICFES por departamento", "url": "/icfes/departamentos/"},
                    {"label": f"Ranking general de colegios ({year})", "url": f"/icfes/ranking/colegios/{year}/"},
                    {"label": "Ranking sector público nacional", "url": "/icfes/ranking/sector/oficiales/colombia/"},
                    {"label": "Ranking sector privado nacional", "url": "/icfes/ranking/sector/privados/colombia/"},
                    {"label": "Histórico nacional de puntaje global", "url": "/icfes/historico/puntaje-global/"},
                    {"label": "Colegios estrella en Colombia", "url": "/icfes/cuadrante/estrella/"},
                    {"label": "Colegios que superaron su rendimiento esperado", "url": "/icfes/supero-prediccion/"},
                    {"label": "Evolución motivacional en Colombia", "url": "/icfes/bandas-motivacionales/"},
                ],
                "seo": {
                    "title": title,
                    "description": description,
                    "og_image": og_image,
                    "keywords": (
                        f"colegios con mejor matematicas icfes {year}, ranking matematicas icfes, "
                        f"top colegios matematicas colombia {year}"
                    ),
                },
                "canonical_url": canonical_url,
                "structured_data_json": schema_data,
            },
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in ranking_matematicas_year_page (%s): %s", ano, e)
        raise Http404("Error al cargar ranking de matemáticas")


@cache_page(60 * 60 * 12)
def historico_nacional_page(request):
    try:
        with get_duckdb_connection() as conn:
            years = _available_years(conn)
            if not years:
                raise Http404("No hay datos históricos disponibles")

            query = f"""
                SELECT
                    {_YEAR_EXPR} AS ano,
                    ROUND(AVG(avg_punt_global), 1)               AS promedio_global,
                    SUM(total_estudiantes)                        AS total_estudiantes,
                    COUNT(DISTINCT colegio_sk)                    AS total_colegios,
                    ROUND(AVG(avg_punt_matematicas), 1)          AS promedio_matematicas,
                    ROUND(AVG(avg_punt_ingles), 1)               AS promedio_ingles,
                    ROUND(AVG(avg_punt_lectura_critica), 1)      AS promedio_lectura,
                    ROUND(AVG(avg_punt_c_naturales), 1)          AS promedio_naturales,
                    ROUND(AVG(avg_punt_sociales_ciudadanas), 1)  AS promedio_sociales
                FROM gold.fct_agg_colegios_ano
                WHERE {_YEAR_EXPR} IS NOT NULL
                GROUP BY {_YEAR_EXPR}
                ORDER BY ano
            """
            rows = conn.execute(resolve_schema(query)).fetchall()

        title = "Histórico ICFES y Pruebas Saber Colombia | Por zona y año"
        description = (
            "Evolución histórica del puntaje ICFES (Pruebas Saber) en Colombia por año, "
            "departamento y zona geográfica. Tendencias nacionales desde 2014 hasta 2024."
        )
        title = _trim_meta(title, 65)
        description = _fit_meta_description(description, min_len=110, max_len=155)
        canonical_url = request.build_absolute_uri(request.path)
        og_image = _default_og_image(_build_base_url(request))
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

        latest_year_nacional = max(int(row[0]) for row in rows) if rows else 2024
        min_year_chart = latest_year_nacional - 5  # 6 años en el chart y en la tabla
        chart = {
            "years": [int(row[0]) for row in rows if int(row[0]) >= min_year_chart],
            "scores": [float(row[1]) if row[1] is not None else None for row in rows if int(row[0]) >= min_year_chart],
            "min_year": min_year_chart,
        }

        all_rows = [
            {
                "ano": int(row[0]),
                "promedio_global":      float(row[1]) if row[1] is not None else None,
                "total_estudiantes":    int(row[2]) if row[2] else 0,
                "total_colegios":       int(row[3]) if row[3] else 0,
                "promedio_matematicas": float(row[4]) if row[4] is not None else None,
                "promedio_ingles":      float(row[5]) if row[5] is not None else None,
                "promedio_lectura":     float(row[6]) if row[6] is not None else None,
                "promedio_naturales":   float(row[7]) if row[7] is not None else None,
                "promedio_sociales":    float(row[8]) if row[8] is not None else None,
            }
            for row in reversed(rows)
        ]
        table_rows = [r for r in all_rows if r["ano"] >= min_year_chart]
        locked_count = len([r for r in all_rows if r["ano"] < min_year_chart])

        return render(
            request,
            "icfes_dashboard/longtail_landing_simple.html",
            {
                "mode": "historico_nacional",
                "rows": table_rows,
                "locked_count": locked_count,
                "chart": chart,
                "related_links": [
                    {"label": "Ranking nacional de colegios", "url": f"/icfes/ranking/colegios/{max(years)}/"},
                    {"label": "Ranking sector público nacional", "url": "/icfes/ranking/sector/oficiales/colombia/"},
                    {"label": "Ranking sector privado nacional", "url": "/icfes/ranking/sector/privados/colombia/"},
                    {"label": "Colegios estrella en Colombia", "url": "/icfes/cuadrante/estrella/"},
                    {"label": "Colegios que superaron su rendimiento esperado", "url": "/icfes/supero-prediccion/"},
                    {"label": "Evolución motivacional en Colombia", "url": "/icfes/bandas-motivacionales/"},
                    {"label": "Resultados ICFES por departamento", "url": "/icfes/departamentos/"},
                ],
                "seo": {
                    "title": title,
                    "description": description,
                    "og_image": og_image,
                    "keywords": (
                        "historico icfes colombia, pruebas saber historico, "
                        "icfes por zona, icfes por departamento, evolucion icfes por ano"
                    ),
                },
                "canonical_url": canonical_url,
                "structured_data_json": schema_data,
                "latest_year": max(years),
            },
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in historico_nacional_page: %s", e)
        raise Http404("Error al cargar histórico nacional")


@cache_page(60 * 60 * 6)
def ranking_sector_nacional_page(request, sector_slug):
    sector_meta = _sector_from_slug(sector_slug)
    if not sector_meta:
        raise Http404("Sector inválido")
    sector_value, _ = sector_meta

    try:
        with get_duckdb_connection() as conn:
            latest_year, prev_year, updated_date = _latest_snapshot(conn)
            rows = _normalize_top_rows(
                _fetch_top20_rows(
                    conn,
                    latest_year=latest_year,
                    prev_year=prev_year,
                    sector_value=sector_value,
                )
            )

        links = [
            {
                "label": "Ver departamentos",
                "url": "/icfes/departamentos/",
            },
            {
                "label": (
                    "Ver ranking nacional privados"
                    if sector_slug == "oficiales"
                    else "Ver ranking nacional públicos"
                ),
                "url": (
                    "/icfes/ranking/sector/privados/colombia/"
                    if sector_slug == "oficiales"
                    else "/icfes/ranking/sector/oficiales/colombia/"
                ),
            },
            {"label": "Colegios estrella en Colombia", "url": "/icfes/cuadrante/estrella/"},
            {"label": "Colegios que superaron su rendimiento esperado", "url": "/icfes/supero-prediccion/"},
            {"label": "Evolución motivacional en Colombia", "url": "/icfes/bandas-motivacionales/"},
        ]
        links.extend(_top_departamento_links(rows, sector_slug, limit=8))
        return _render_sector_ranking(
            request,
            sector_slug=sector_slug,
            scope_label="Nacional",
            scope_slug="nacional",
            location_title="Colombia",
            rows=rows,
            canonical_path=request.path,
            updated_date=updated_date,
            latest_year=latest_year,
            links=links,
        )
    except Http404:
        raise
    except Exception as exc:
        logger.error("Error in ranking_sector_nacional_page (%s): %s", sector_slug, exc)
        raise Http404("Error al cargar ranking nacional por sector")


@cache_page(60 * 60 * 6)
def ranking_sector_departamento_page(request, sector_slug, departamento_slug):
    sector_meta = _sector_from_slug(sector_slug)
    if not sector_meta:
        raise Http404("Sector inválido")
    sector_value, _ = sector_meta

    try:
        with get_duckdb_connection() as conn:
            latest_year, prev_year, updated_date = _latest_snapshot(conn)
            departamento = _resolve_departamento(conn, sector_value, latest_year, departamento_slug)
            if not departamento:
                raise Http404("Departamento no disponible")

            rows = _normalize_top_rows(
                _fetch_top20_rows(
                    conn,
                    latest_year=latest_year,
                    prev_year=prev_year,
                    sector_value=sector_value,
                    departamento=departamento,
                )
            )

        links = [
            {
                "label": "Ranking nacional del sector",
                "url": f"/icfes/ranking/sector/{sector_slug}/colombia/",
            },
            {
                "label": (
                    f"Ranking departamental privados en {departamento}"
                    if sector_slug == "oficiales"
                    else f"Ranking departamental públicos en {departamento}"
                ),
                "url": (
                    f"/icfes/ranking/sector/privados/departamento/{departamento_slug}/"
                    if sector_slug == "oficiales"
                    else f"/icfes/ranking/sector/oficiales/departamento/{departamento_slug}/"
                ),
            },
            {"label": f"Colegios estrella en {departamento}", "url": f"/icfes/cuadrante/estrella/{departamento_slug}/"},
            {"label": f"Colegios que superaron su rendimiento en {departamento}", "url": f"/icfes/supero-prediccion/{departamento_slug}/"},
            {"label": f"Evolución motivacional en {departamento}", "url": f"/icfes/bandas-motivacionales/{departamento_slug}/"},
        ]
        links.extend(_top_municipio_links(rows, sector_slug, limit=10))
        return _render_sector_ranking(
            request,
            sector_slug=sector_slug,
            scope_label="Departamental",
            scope_slug="departamento",
            location_title=departamento,
            rows=rows,
            canonical_path=request.path,
            updated_date=updated_date,
            latest_year=latest_year,
            links=links,
        )
    except Http404:
        raise
    except Exception as exc:
        logger.error(
            "Error in ranking_sector_departamento_page (%s, %s): %s",
            sector_slug,
            departamento_slug,
            exc,
        )
        raise Http404("Error al cargar ranking departamental por sector")


@cache_page(60 * 60 * 6)
def ranking_sector_municipio_page(request, sector_slug, departamento_slug, municipio_slug):
    sector_meta = _sector_from_slug(sector_slug)
    if not sector_meta:
        raise Http404("Sector inválido")
    sector_value, _ = sector_meta

    try:
        with get_duckdb_connection() as conn:
            latest_year, prev_year, updated_date = _latest_snapshot(conn)
            # Single query resolves both departamento and municipio slugs
            departamento, municipio = _resolve_location(
                conn, sector_value, latest_year, departamento_slug, municipio_slug
            )
            if not departamento:
                # 410 Gone: URL was in old sitemap but data no longer exists — removes from index faster
                return HttpResponse(status=410)
            if not municipio:
                # 410 Gone: municipality has insufficient sector data — tell Google to deindex
                return HttpResponse(status=410)

            rows = _normalize_top_rows(
                _fetch_top20_rows(
                    conn,
                    latest_year=latest_year,
                    prev_year=prev_year,
                    sector_value=sector_value,
                    departamento=departamento,
                    municipio=municipio,
                )
            )

        links = [
            {
                "label": f"Ranking departamental ({departamento})",
                "url": f"/icfes/ranking/sector/{sector_slug}/departamento/{departamento_slug}/",
            },
            {
                "label": "Ranking nacional del sector",
                "url": f"/icfes/ranking/sector/{sector_slug}/colombia/",
            },
            {
                "label": (
                    f"Ranking municipal privados en {municipio}"
                    if sector_slug == "oficiales"
                    else f"Ranking municipal públicos en {municipio}"
                ),
                "url": (
                    f"/icfes/ranking/sector/privados/departamento/{departamento_slug}/municipio/{municipio_slug}/"
                    if sector_slug == "oficiales"
                    else f"/icfes/ranking/sector/oficiales/departamento/{departamento_slug}/municipio/{municipio_slug}/"
                ),
            },
        ]
        return _render_sector_ranking(
            request,
            sector_slug=sector_slug,
            scope_label="Municipal",
            scope_slug="municipio",
            location_title=f"{municipio}, {departamento}",
            rows=rows,
            canonical_path=request.path,
            updated_date=updated_date,
            latest_year=latest_year,
            links=links,
        )
    except Http404:
        raise
    except Exception as exc:
        logger.error(
            "Error in ranking_sector_municipio_page (%s, %s, %s): %s",
            sector_slug,
            departamento_slug,
            municipio_slug,
            exc,
        )
        raise Http404("Error al cargar ranking municipal por sector")


# ---------------------------------------------------------------------------
# Ranking por materia
# ---------------------------------------------------------------------------

_MATERIA_CONFIG = {
    "matematicas": {
        "column": "avg_punt_matematicas",
        "label": "Matemáticas",
    },
    "ingles": {
        "column": "avg_punt_ingles",
        "label": "Inglés",
    },
    # Extensible — descomentar para activar:
    # "lectura-critica": {"column": "avg_punt_lectura_critica", "label": "Lectura Crítica"},
    # "ciencias-naturales": {"column": "avg_punt_c_naturales", "label": "Ciencias Naturales"},
    # "sociales": {"column": "avg_punt_sociales_ciudadanas", "label": "Sociales"},
}


def ranking_materia_hub_page(request, materia_slug):
    """Redirect to the latest available year for this materia."""
    if materia_slug not in _MATERIA_CONFIG:
        raise Http404("Materia no disponible")
    try:
        with get_duckdb_connection() as conn:
            years = _available_years(conn)
        if not years:
            raise Http404("No hay datos disponibles")
        return redirect(f"/icfes/materia/{materia_slug}/{years[0]}/", permanent=False)
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in ranking_materia_hub_page (%s): %s", materia_slug, e)
        raise Http404("Error al cargar la materia")


@cache_page(60 * 60 * 6)
def ranking_materia_page(request, materia_slug, ano):
    if materia_slug not in _MATERIA_CONFIG:
        raise Http404("Materia no disponible")
    materia = _MATERIA_CONFIG[materia_slug]
    materia_col = materia["column"]
    materia_label = materia["label"]

    try:
        year = int(ano)
    except (TypeError, ValueError):
        raise Http404("Año inválido")

    try:
        with get_duckdb_connection() as conn:
            years = _available_years(conn)
            if year not in years:
                raise Http404("Año no disponible")

            query = f"""
                SELECT
                    f.nombre_colegio,
                    f.departamento,
                    f.municipio,
                    f.sector,
                    ROUND(f.{materia_col}, 1) AS puntaje_materia,
                    ROUND(f.avg_punt_global, 1) AS puntaje_global,
                    f.total_estudiantes,
                    COALESCE(s.slug, '') AS slug
                FROM gold.fct_agg_colegios_ano f
                LEFT JOIN gold.dim_colegios_slugs s ON f.colegio_bk = s.codigo
                WHERE f.ano = ?
                  AND f.nombre_colegio IS NOT NULL
                  AND f.{materia_col} IS NOT NULL
                  AND f.total_estudiantes >= 5
                  AND f.sector != 'SINTETICO'
                ORDER BY f.{materia_col} DESC
                LIMIT 100
            """
            rows = conn.execute(resolve_schema(query), [str(year)]).fetchall()

        title = (
            f"Colegios con mejor {materia_label} en ICFES {year} | Top 100 Colombia"
        )
        description = (
            f"Ranking de los 100 colegios con mayor puntaje en {materia_label} ICFES {year} "
            "en Colombia. Incluye comparación con puntaje global por colegio."
        )
        title = _trim_meta(title, 65)
        description = _fit_meta_description(description, min_len=110, max_len=155)
        canonical_url = request.build_absolute_uri(request.path)
        og_image = _default_og_image(_build_base_url(request))
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

        return render(
            request,
            "icfes_dashboard/longtail_landing_simple.html",
            {
                "mode": "ranking_materia",
                "materia_slug": materia_slug,
                "materia_label": materia_label,
                "year": year,
                "years": years[:6],
                "year_base_url": f"/icfes/materia/{materia_slug}/",
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "departamento_slug": slugify(row[1]) if row[1] else "",
                        "municipio": row[2],
                        "municipio_slug": slugify(row[2]) if row[2] else "",
                        "sector": row[3],
                        "score_materia": float(row[4]) if row[4] is not None else None,
                        "score_global": float(row[5]) if row[5] is not None else None,
                        "estudiantes": int(row[6]) if row[6] else 0,
                        "slug": row[7],
                    }
                    for row in rows
                ],
                "related_links": [
                    {"label": "Resultados ICFES por departamento", "url": "/icfes/departamentos/"},
                    {"label": f"Ranking general de colegios ({year})", "url": f"/icfes/ranking/colegios/{year}/"},
                    {"label": f"Ranking matemáticas ({year})", "url": f"/icfes/ranking/matematicas/{year}/"},
                    {"label": "Ranking sector público nacional", "url": "/icfes/ranking/sector/oficiales/colombia/"},
                    {"label": "Ranking sector privado nacional", "url": "/icfes/ranking/sector/privados/colombia/"},
                ],
                "seo": {
                    "title": title,
                    "description": description,
                    "og_image": og_image,
                    "keywords": (
                        f"colegios mejor {materia_label.lower()} icfes {year}, "
                        f"ranking {materia_label.lower()} icfes colombia, "
                        f"top colegios {materia_label.lower()} {year}"
                    ),
                },
                "canonical_url": canonical_url,
                "structured_data_json": schema_data,
            },
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in ranking_materia_page (%s, %s): %s", materia_slug, ano, e)
        raise Http404("Error al cargar ranking de materia")


# ---------------------------------------------------------------------------
# Colegios que más mejoraron
# ---------------------------------------------------------------------------


def colegios_mejoraron_hub_page(request):
    """Redirect to the most recent year that has improvement data."""
    try:
        with get_duckdb_connection() as conn:
            row = conn.execute(
                resolve_schema(f"""
                    SELECT MAX({_YEAR_EXPR})
                    FROM gold.fct_colegio_historico
                    WHERE punt_global_ano_anterior IS NOT NULL
                """)
            ).fetchone()
        latest_with_prev = row[0] if row else None
        if not latest_with_prev:
            raise Http404("No hay datos de mejora disponibles")
        return redirect(
            f"/icfes/colegios-que-mas-mejoraron/{latest_with_prev}/", permanent=False
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in colegios_mejoraron_hub_page: %s", e)
        raise Http404("Error al cargar la página")


@cache_page(60 * 60 * 6)
def colegios_mejoraron_page(request, ano):
    try:
        year = int(ano)
    except (TypeError, ValueError):
        raise Http404("Año inválido")

    try:
        with get_duckdb_connection() as conn:
            query = """
                SELECT
                    h.nombre_colegio,
                    h.departamento,
                    h.municipio,
                    h.sector,
                    ROUND(h.cambio_absoluto_global, 1) AS mejora,
                    ROUND(h.avg_punt_global, 1) AS puntaje_actual,
                    ROUND(h.punt_global_ano_anterior, 1) AS puntaje_anterior,
                    h.total_estudiantes,
                    h.ranking_nacional,
                    COALESCE(s.slug, '') AS slug
                FROM gold.fct_colegio_historico h
                LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = h.codigo_dane
                WHERE h.ano = ?
                  AND h.cambio_absoluto_global IS NOT NULL
                  AND h.total_estudiantes >= 10
                  AND h.nombre_colegio IS NOT NULL
                ORDER BY mejora DESC
                LIMIT 100
            """
            rows = conn.execute(resolve_schema(query), [str(year)]).fetchall()
            if not rows:
                raise Http404("No hay datos de mejora para ese año")
            years = _available_years(conn)

        prev_year = year - 1
        title = f"Colegios que más mejoraron en ICFES {year} | Ranking Colombia"
        description = (
            f"Los 100 colegios con mayor mejora en puntaje global ICFES {year} "
            f"comparado con {prev_year}. Incluye puntaje actual, anterior y variación."
        )
        title = _trim_meta(title, 65)
        description = _fit_meta_description(description, min_len=110, max_len=155)
        canonical_url = request.build_absolute_uri(request.path)
        og_image = _default_og_image(_build_base_url(request))
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

        return render(
            request,
            "icfes_dashboard/longtail_landing_simple.html",
            {
                "mode": "colegios_mejoraron",
                "year": year,
                "prev_year": prev_year,
                "years": [y for y in years if y <= year][:8],
                "year_base_url": "/icfes/colegios-que-mas-mejoraron/",
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "departamento_slug": slugify(row[1]) if row[1] else "",
                        "municipio": row[2],
                        "municipio_slug": slugify(row[2]) if row[2] else "",
                        "sector": row[3],
                        "mejora": float(row[4]) if row[4] is not None else None,
                        "puntaje_actual": float(row[5]) if row[5] is not None else None,
                        "puntaje_anterior": float(row[6]) if row[6] is not None else None,
                        "estudiantes": int(row[7]) if row[7] else 0,
                        "ranking_nacional": int(row[8]) if row[8] else None,
                        "slug": row[9],
                    }
                    for row in rows
                ],
                "related_links": [
                    {"label": "Resultados ICFES por departamento", "url": "/icfes/departamentos/"},
                    {"label": f"Ranking general de colegios ({year})", "url": f"/icfes/ranking/colegios/{year}/"},
                    {"label": f"Ranking matemáticas ({year})", "url": f"/icfes/ranking/matematicas/{year}/"},
                    {"label": "Ranking sector público nacional", "url": "/icfes/ranking/sector/oficiales/colombia/"},
                    {"label": "Ranking sector privado nacional", "url": "/icfes/ranking/sector/privados/colombia/"},
                ],
                "seo": {
                    "title": title,
                    "description": description,
                    "og_image": og_image,
                    "keywords": (
                        f"colegios que mas mejoraron icfes {year}, mejora icfes {year}, "
                        f"colegios progreso icfes colombia {year}"
                    ),
                },
                "canonical_url": canonical_url,
                "structured_data_json": schema_data,
            },
        )
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in colegios_mejoraron_page (%s): %s", ano, e)
        raise Http404("Error al cargar colegios que mejoraron")


@cache_page(60 * 60 * 24 * 7)
def que_es_icfes_analytics_page(request):
    base_url = _build_base_url(request)
    canonical_url = request.build_absolute_uri(request.path)
    og_image = _default_og_image(base_url)

    title = "¿Qué es ICFES Analytics? | Análisis de Pruebas Saber Colombia"
    description = (
        "ICFES Analytics analiza Pruebas Saber en Colombia desde 1996: 12.000+ colegios, "
        "datos por departamento y sector para impulsar decisiones educativas efectivas."
    )
    title = _trim_meta(title, 65)
    description = _fit_meta_description(description, min_len=110, max_len=155)

    faqs = [
        {
            "q": "¿Qué es ICFES Analytics?",
            "a": (
                "ICFES Analytics es una plataforma gratuita de análisis de datos educativos que "
                "procesa los resultados históricos de las Pruebas Saber 11 en Colombia desde 1996 "
                "hasta el presente. Su misión es que la educación colombiana cuente con los insights "
                "necesarios para mover las palancas correctas y tomar decisiones efectivas y a tiempo, "
                "de modo que millones de estudiantes alcancen la excelencia y Colombia tenga cada año "
                "mejores bachilleres. Permite comparar más de 12.000 colegios por puntaje global, "
                "área académica, sector (oficial/privado), departamento, municipio y zona geográfica."
            ),
        },
        {
            "q": "¿Qué son las Pruebas Saber 11?",
            "a": (
                "Las Pruebas Saber 11 (antes llamadas ICFES) son los exámenes de Estado que aplica el "
                "Instituto Colombiano para la Evaluación de la Educación a los estudiantes de grado 11 "
                "en Colombia. El puntaje global va de 0 a 500 puntos y es requisito de admisión para "
                "universidades públicas del país."
            ),
        },
        {
            "q": "¿Es gratis usar ICFES Analytics?",
            "a": (
                "Sí. La consulta de perfiles de colegios, rankings, series históricas y comparativos "
                "por departamento es completamente gratuita y no requiere registro. El registro opcional "
                "desbloquea reportes personalizados, diagnóstico con modelos de Machine Learning y "
                "alertas de mejora para docentes y directivos."
            ),
        },
        {
            "q": "¿Qué datos tiene ICFES Analytics?",
            "a": (
                "La plataforma contiene los microdatos oficiales del ICFES: 17,7 millones de resultados "
                "individuales de estudiantes desde 1996 hasta el año más reciente disponible, "
                "consolidados en más de 335.000 registros colegio-año. Incluye puntajes globales y "
                "por materia (Matemáticas, Lectura Crítica, Ciencias Naturales, Sociales e Inglés), "
                "más variables socioeconómicas del formulario de inscripción."
            ),
        },
        {
            "q": "¿Cómo busco el perfil de mi colegio en ICFES Analytics?",
            "a": (
                "Desde la página principal puedes buscar tu colegio por nombre o código DANE. "
                "También puedes navegar desde el índice de departamentos hacia tu región y municipio. "
                "Cada perfil muestra el histórico de puntajes, comparativo con el promedio nacional, "
                "fortalezas por materia y proyecciones para el año siguiente."
            ),
        },
        {
            "q": "¿Qué es el puntaje global ICFES?",
            "a": (
                "El puntaje global ICFES es el promedio ponderado de las cinco pruebas: "
                "Lectura Crítica, Matemáticas, Ciencias Naturales, Sociales y Ciudadanas, e Inglés. "
                "Va de 0 a 500 puntos. El promedio nacional en 2024 fue de 254 puntos, con diferencias "
                "entre colegios privados (promedio 275) y oficiales (promedio 247)."
            ),
        },
    ]

    schema_data = json.dumps(
        [
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": faq["q"],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": faq["a"],
                        },
                    }
                    for faq in faqs
                ],
            },
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "@id": f"{base_url}/#organization",
                "name": "ICFES Analytics",
                "url": base_url,
                "description": (
                    "Plataforma de análisis de las Pruebas Saber ICFES en Colombia desde 1996. "
                    "Datos de más de 12.000 colegios para impulsar decisiones educativas efectivas."
                ),
            },
        ],
        ensure_ascii=False,
    )

    return render(
        request,
        "icfes_dashboard/que_es_icfes_analytics.html",
        {
            "faqs": faqs,
            "seo": {
                "title": title,
                "description": description,
                "og_image": og_image,
            },
            "canonical_url": canonical_url,
            "structured_data_json": schema_data,
        },
    )


