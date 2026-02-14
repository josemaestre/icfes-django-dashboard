"""
SEO landing pages for departments and municipalities.
Uses lightweight aggregate queries from fct_agg_colegios_ano.
"""
import json
import logging

from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.cache import cache_page

from .db_utils import get_duckdb_connection, resolve_schema

logger = logging.getLogger(__name__)


def _build_geo_where(departamento=None, municipio=None, alias=""):
    prefix = f"{alias}." if alias else ""
    where = [f"{prefix}departamento IS NOT NULL", f"{prefix}departamento != ''"]
    params = []
    if departamento:
        where.append(f"{prefix}departamento = ?")
        params.append(departamento)
    if municipio:
        where.append(f"{prefix}municipio = ?")
        params.append(municipio)
    return " AND ".join(where), params


def _resolve_departamento(conn, departamento_slug):
    query = """
        SELECT DISTINCT departamento
        FROM gold.fct_agg_colegios_ano
        WHERE departamento IS NOT NULL AND departamento != ''
        ORDER BY departamento
    """
    rows = conn.execute(resolve_schema(query)).fetchall()
    for (departamento,) in rows:
        if slugify(departamento) == departamento_slug:
            return departamento
    return None


def _resolve_municipio(conn, departamento, municipio_slug):
    query = """
        SELECT DISTINCT municipio
        FROM gold.fct_agg_colegios_ano
        WHERE departamento = ?
          AND municipio IS NOT NULL
          AND municipio != ''
        ORDER BY municipio
    """
    rows = conn.execute(resolve_schema(query), [departamento]).fetchall()
    for (municipio,) in rows:
        if slugify(municipio) == municipio_slug:
            return municipio
    return None


def _geo_landing_context(request, departamento, municipio=None):
    with get_duckdb_connection() as conn:
        where_clause, where_params = _build_geo_where(departamento, municipio)

        latest_year_query = f"""
            SELECT MAX(CAST(ano AS INTEGER))
            FROM gold.fct_agg_colegios_ano
            WHERE {where_clause}
        """
        latest_year_row = conn.execute(
            resolve_schema(latest_year_query), where_params
        ).fetchone()
        latest_year = latest_year_row[0] if latest_year_row else None
        if not latest_year:
            raise Http404("No hay datos para esta ubicación")

        latest_where = f"{where_clause} AND CAST(ano AS INTEGER) = ?"
        latest_params = where_params + [latest_year]

        stats_query = f"""
            SELECT
                ROUND(AVG(avg_punt_global), 1) AS promedio_global,
                SUM(total_estudiantes) AS total_estudiantes,
                COUNT(DISTINCT colegio_sk) AS total_colegios
            FROM gold.fct_agg_colegios_ano
            WHERE {latest_where}
        """
        stats_row = conn.execute(resolve_schema(stats_query), latest_params).fetchone()

        trend_query = f"""
            SELECT
                CAST(ano AS INTEGER) AS ano,
                ROUND(AVG(avg_punt_global), 1) AS promedio_global
            FROM gold.fct_agg_colegios_ano
            WHERE {where_clause}
            GROUP BY CAST(ano AS INTEGER)
            ORDER BY CAST(ano AS INTEGER)
        """
        trend_rows = conn.execute(resolve_schema(trend_query), where_params).fetchall()

        f_where, f_params = _build_geo_where(departamento, municipio, alias="f")
        f_latest_where = f"{f_where} AND CAST(f.ano AS INTEGER) = ?"
        f_latest_params = f_params + [latest_year]

        top_schools_query = f"""
            SELECT
                f.nombre_colegio,
                f.sector,
                ROUND(f.avg_punt_global, 1) AS promedio_global,
                f.total_estudiantes,
                COALESCE(s.slug, '') AS slug
            FROM gold.fct_agg_colegios_ano f
            LEFT JOIN gold.dim_colegios_slugs s ON f.colegio_bk = s.codigo
            WHERE {f_latest_where}
              AND f.nombre_colegio IS NOT NULL
            ORDER BY f.avg_punt_global DESC
            LIMIT 10
        """
        top_rows = conn.execute(resolve_schema(top_schools_query), f_latest_params).fetchall()

        all_schools_in_municipality = []
        if municipio is not None:
            all_schools_query = f"""
                SELECT
                    f.nombre_colegio,
                    f.sector,
                    ROUND(f.avg_punt_global, 1) AS promedio_global,
                    COALESCE(s.slug, '') AS slug
                FROM gold.fct_agg_colegios_ano f
                LEFT JOIN gold.dim_colegios_slugs s ON f.colegio_bk = s.codigo
                WHERE {f_latest_where}
                  AND f.nombre_colegio IS NOT NULL
                ORDER BY f.nombre_colegio ASC
            """
            all_schools_rows = conn.execute(
                resolve_schema(all_schools_query), f_latest_params
            ).fetchall()
            all_schools_in_municipality = [
                {
                    "nombre": row[0],
                    "sector": row[1],
                    "promedio_global": float(row[2]) if row[2] is not None else None,
                    "slug": row[3],
                }
                for row in all_schools_rows
            ]

        municipios = []
        if municipio is None:
            municipios_query = """
                SELECT
                    municipio,
                    ROUND(AVG(avg_punt_global), 1) AS promedio_global,
                    COUNT(DISTINCT colegio_sk) AS total_colegios
                FROM gold.fct_agg_colegios_ano
                WHERE departamento = ?
                  AND CAST(ano AS INTEGER) = ?
                  AND municipio IS NOT NULL
                  AND municipio != ''
                GROUP BY municipio
                ORDER BY promedio_global DESC
                LIMIT 30
            """
            municipios_rows = conn.execute(
                resolve_schema(municipios_query), [departamento, latest_year]
            ).fetchall()
            municipios = [
                {
                    "nombre": row[0],
                    "slug": slugify(row[0]),
                    "promedio_global": row[1],
                    "total_colegios": int(row[2]) if row[2] else 0,
                }
                for row in municipios_rows
            ]

    location_name = f"{municipio}, {departamento}" if municipio else departamento
    location_type = "municipio" if municipio else "departamento"
    canonical_url = request.build_absolute_uri(request.path)

    seo_title = (
        f"Puntaje ICFES {latest_year} en {location_name} | Ranking de Colegios y Tendencias"
    )
    seo_description = (
        f"Resultados ICFES en {location_name}. "
        f"Consulta promedio global, evolución histórica y top colegios del año {latest_year}."
    )

    breadcrumb_items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Inicio",
            "item": request.build_absolute_uri("/"),
        },
        {
            "@type": "ListItem",
            "position": 2,
            "name": "Departamentos ICFES",
            "item": request.build_absolute_uri("/icfes/departamentos/"),
        },
    ]

    if municipio is None:
        breadcrumb_items.append(
            {
                "@type": "ListItem",
                "position": 3,
                "name": departamento,
                "item": canonical_url,
            }
        )
    else:
        breadcrumb_items.append(
            {
                "@type": "ListItem",
                "position": 3,
                "name": departamento,
                "item": request.build_absolute_uri(
                    f"/icfes/departamento/{slugify(departamento)}/"
                ),
            }
        )
        breadcrumb_items.append(
            {
                "@type": "ListItem",
                "position": 4,
                "name": municipio,
                "item": canonical_url,
            }
        )

    page_schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": f"{canonical_url}#webpage",
        "url": canonical_url,
        "name": seo_title,
        "description": seo_description,
        "inLanguage": "es-CO",
    }
    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumb_items,
    }

    return {
        "geo": {
            "departamento": departamento,
            "municipio": municipio,
            "departamento_slug": slugify(departamento),
            "municipio_slug": slugify(municipio) if municipio else None,
            "name": location_name,
            "type": location_type,
        },
        "stats": {
            "promedio_global": stats_row[0] if stats_row else None,
            "total_estudiantes": int(stats_row[1]) if stats_row and stats_row[1] else 0,
            "total_colegios": int(stats_row[2]) if stats_row and stats_row[2] else 0,
        },
        "latest_year": int(latest_year),
        "trend_chart": {
            "years": [int(row[0]) for row in trend_rows],
            "scores": [float(row[1]) if row[1] is not None else None for row in trend_rows],
        },
        "top_schools": [
            {
                "nombre": row[0],
                "sector": row[1],
                "promedio_global": float(row[2]) if row[2] is not None else None,
                "total_estudiantes": int(row[3]) if row[3] else 0,
                "slug": row[4],
            }
            for row in top_rows
        ],
        "all_schools_in_municipality": all_schools_in_municipality,
        "municipios": municipios,
        "seo": {
            "title": seo_title,
            "description": seo_description,
            "keywords": (
                f"ICFES {latest_year}, {location_name}, ranking colegios {location_name}, "
                f"puntaje ICFES {location_name}, pruebas saber 11 {location_name}"
            ),
        },
        "canonical_url": canonical_url,
        "structured_data_json": json.dumps([page_schema, breadcrumb_schema], ensure_ascii=False),
    }


@cache_page(60 * 60 * 12)
def departments_index_page(request):
    try:
        with get_duckdb_connection() as conn:
            query = """
                SELECT DISTINCT departamento
                FROM gold.fct_agg_colegios_ano
                WHERE departamento IS NOT NULL
                  AND departamento != ''
                ORDER BY departamento
            """
            rows = conn.execute(resolve_schema(query)).fetchall()
        departments = [{"name": row[0], "slug": slugify(row[0])} for row in rows]
        return render(
            request,
            "icfes_dashboard/geo_landing_simple.html",
            {
                "index_mode": True,
                "departments": departments,
                "seo": {
                    "title": "Departamentos con resultados ICFES | ICFES Analytics",
                    "description": "Explora resultados ICFES por departamento en Colombia.",
                    "keywords": "ICFES por departamento, ranking departamentos ICFES, pruebas saber 11",
                },
                "canonical_url": request.build_absolute_uri(request.path),
            },
        )
    except Exception as e:
        logger.error("Error in departments_index_page: %s", e)
        raise Http404("Error al cargar departamentos")


@cache_page(60 * 60 * 4)
def department_landing_page(request, departamento_slug):
    try:
        with get_duckdb_connection() as conn:
            departamento = _resolve_departamento(conn, departamento_slug)
        if not departamento:
            raise Http404("Departamento no encontrado")
        context = _geo_landing_context(request, departamento=departamento, municipio=None)
        return render(request, "icfes_dashboard/geo_landing_simple.html", context)
    except Http404:
        raise
    except Exception as e:
        logger.error("Error in department_landing_page for slug %s: %s", departamento_slug, e)
        raise Http404("Error al cargar el departamento")


@cache_page(60 * 60 * 4)
def municipality_landing_page(request, departamento_slug, municipio_slug):
    try:
        with get_duckdb_connection() as conn:
            departamento = _resolve_departamento(conn, departamento_slug)
            if not departamento:
                raise Http404("Departamento no encontrado")
            municipio = _resolve_municipio(conn, departamento, municipio_slug)
            if not municipio:
                raise Http404("Municipio no encontrado")

        context = _geo_landing_context(
            request, departamento=departamento, municipio=municipio
        )
        return render(request, "icfes_dashboard/geo_landing_simple.html", context)
    except Http404:
        raise
    except Exception as e:
        logger.error(
            "Error in municipality_landing_page for slugs %s/%s: %s",
            departamento_slug,
            municipio_slug,
            e,
        )
        raise Http404("Error al cargar el municipio")
