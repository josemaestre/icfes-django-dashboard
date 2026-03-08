"""
Long-tail SEO landing pages for high-intent ICFES searches.
"""
import json
import logging

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.cache import cache_page

from .db_utils import get_duckdb_connection, resolve_schema

logger = logging.getLogger(__name__)


def _build_base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _absolute_url(base_url, path):
    return f"{base_url}/{path.lstrip('/')}"


def _available_years(conn):
    query = """
        SELECT DISTINCT CAST(ano AS INTEGER) AS ano
        FROM gold.fct_agg_colegios_ano
        WHERE ano IS NOT NULL
        ORDER BY ano DESC
    """
    rows = conn.execute(resolve_schema(query)).fetchall()
    return [int(row[0]) for row in rows if row[0] is not None]


def _latest_snapshot(conn):
    years = _available_years(conn)
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


def _resolve_departamento(conn, sector_value, year, departamento_slug):
    query = """
        SELECT DISTINCT departamento
        FROM gold.fct_colegio_historico
        WHERE CAST(ano AS INTEGER) = ?
          AND sector = ?
          AND departamento IS NOT NULL
          AND departamento != ''
        ORDER BY departamento
    """
    rows = conn.execute(resolve_schema(query), [year, sector_value]).fetchall()
    for (departamento,) in rows:
        if slugify(departamento) == departamento_slug:
            return departamento
    return None


def _resolve_municipio(conn, sector_value, year, departamento, municipio_slug):
    query = """
        SELECT DISTINCT municipio
        FROM gold.fct_colegio_historico
        WHERE CAST(ano AS INTEGER) = ?
          AND sector = ?
          AND departamento = ?
          AND municipio IS NOT NULL
          AND municipio != ''
        ORDER BY municipio
    """
    rows = conn.execute(resolve_schema(query), [year, sector_value, departamento]).fetchall()
    for (municipio,) in rows:
        if slugify(municipio) == municipio_slug:
            return municipio
    return None


def _fetch_top20_rows(conn, latest_year, prev_year, sector_value, departamento=None, municipio=None):
    filters = ["h.sector = ?", "h.total_estudiantes >= 10", "h.nombre_colegio IS NOT NULL"]
    params = [latest_year]
    if prev_year is not None:
        params.append(prev_year)
    else:
        # Keep CTE valid when no previous year is available.
        params.append(latest_year)
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
                CAST(h.ano AS INTEGER) AS ano,
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
             AND CAST(a.ano AS INTEGER) = CAST(h.ano AS INTEGER)
            WHERE CAST(h.ano AS INTEGER) IN (?, ?)
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

    base_url = _build_base_url(request)
    canonical_url = _absolute_url(base_url, canonical_path)
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
                "keywords": (
                    f"top 20 colegios {sector_label} {location_title.lower()}, ranking icfes {latest_year}, "
                    f"colegios {sector_label} colombia"
                ),
            },
            "canonical_url": canonical_url,
            "structured_data_json": schema_data,
        },
    )


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
                WHERE CAST(f.ano AS INTEGER) = ?
                  AND f.nombre_colegio IS NOT NULL
                  AND f.sector != 'SINTETICO'
                ORDER BY f.avg_punt_global DESC
                LIMIT 50
            """
            rows = conn.execute(resolve_schema(query), [year]).fetchall()

        title = f"Mejores colegios ICFES {year} en Colombia | Ranking actualizado"
        description = (
            f"Ranking ICFES {year} de colegios en Colombia. "
            "Consulta top colegios por puntaje global, departamento y municipio."
        )
        canonical_url = request.build_absolute_uri(request.path)
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
                "years": years[:10],
                "year_base_url": "/icfes/ranking/colegios/",
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "municipio": row[2],
                        "sector": row[3],
                        "score": float(row[4]) if row[4] is not None else None,
                        "estudiantes": int(row[5]) if row[5] else 0,
                        "slug": row[6],
                    }
                    for row in rows
                ],
                "seo": {
                    "title": title,
                    "description": description,
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
                WHERE CAST(f.ano AS INTEGER) = ?
                  AND f.nombre_colegio IS NOT NULL
                  AND f.avg_punt_matematicas IS NOT NULL
                  AND f.sector != 'SINTETICO'
                ORDER BY f.avg_punt_matematicas DESC
                LIMIT 50
            """
            rows = conn.execute(resolve_schema(query), [year]).fetchall()

        title = f"Colegios con mejor matemáticas ICFES {year} | Top Colombia"
        description = (
            f"Ranking de colegios con mejor puntaje en matemáticas ICFES {year} en Colombia. "
            "Incluye comparación con puntaje global por colegio."
        )
        canonical_url = request.build_absolute_uri(request.path)
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
                "years": years[:10],
                "year_base_url": "/icfes/ranking/matematicas/",
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "municipio": row[2],
                        "sector": row[3],
                        "score_math": float(row[4]) if row[4] is not None else None,
                        "score_global": float(row[5]) if row[5] is not None else None,
                        "slug": row[6],
                    }
                    for row in rows
                ],
                "seo": {
                    "title": title,
                    "description": description,
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

            query = """
                SELECT
                    CAST(ano AS INTEGER) AS ano,
                    ROUND(AVG(avg_punt_global), 1) AS promedio_global,
                    SUM(total_estudiantes) AS total_estudiantes,
                    COUNT(DISTINCT colegio_sk) AS total_colegios
                FROM gold.fct_agg_colegios_ano
                GROUP BY CAST(ano AS INTEGER)
                ORDER BY CAST(ano AS INTEGER)
            """
            rows = conn.execute(resolve_schema(query)).fetchall()

        title = "Puntaje global ICFES histórico en Colombia | Evolución por año"
        description = (
            "Evolución histórica del puntaje global ICFES en Colombia. "
            "Consulta tendencia nacional, total de colegios y estudiantes por año."
        )
        canonical_url = request.build_absolute_uri(request.path)
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

        chart = {
            "years": [int(row[0]) for row in rows],
            "scores": [float(row[1]) if row[1] is not None else None for row in rows],
        }

        table_rows = [
            {
                "ano": int(row[0]),
                "promedio_global": float(row[1]) if row[1] is not None else None,
                "total_estudiantes": int(row[2]) if row[2] else 0,
                "total_colegios": int(row[3]) if row[3] else 0,
            }
            for row in reversed(rows)
        ]

        return render(
            request,
            "icfes_dashboard/longtail_landing_simple.html",
            {
                "mode": "historico_nacional",
                "rows": table_rows,
                "chart": chart,
                "seo": {
                    "title": title,
                    "description": description,
                    "keywords": (
                        "puntaje global icfes historico, tendencia icfes colombia, "
                        "evolucion icfes por ano"
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
            departamento = _resolve_departamento(conn, sector_value, latest_year, departamento_slug)
            if not departamento:
                raise Http404("Departamento no disponible")

            municipio = _resolve_municipio(
                conn,
                sector_value,
                latest_year,
                departamento,
                municipio_slug,
            )
            if not municipio:
                raise Http404("Municipio no disponible")

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
