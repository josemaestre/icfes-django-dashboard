"""
Long-tail SEO landing pages for high-intent ICFES searches.
"""
import json
import logging

from django.http import Http404
from django.shortcuts import render

from .db_utils import get_duckdb_connection, resolve_schema

logger = logging.getLogger(__name__)


def _available_years(conn):
    query = """
        SELECT DISTINCT CAST(ano AS INTEGER) AS ano
        FROM gold.fct_agg_colegios_ano
        WHERE ano IS NOT NULL
        ORDER BY ano DESC
    """
    rows = conn.execute(resolve_schema(query)).fetchall()
    return [int(row[0]) for row in rows if row[0] is not None]


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
                    nombre_colegio,
                    departamento,
                    municipio,
                    sector,
                    ROUND(avg_punt_global, 1) AS promedio_global,
                    total_estudiantes
                FROM gold.fct_agg_colegios_ano
                WHERE CAST(ano AS INTEGER) = ?
                  AND nombre_colegio IS NOT NULL
                ORDER BY avg_punt_global DESC
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
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "municipio": row[2],
                        "sector": row[3],
                        "score": float(row[4]) if row[4] is not None else None,
                        "estudiantes": int(row[5]) if row[5] else 0,
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
                    nombre_colegio,
                    departamento,
                    municipio,
                    sector,
                    ROUND(avg_punt_matematicas, 1) AS promedio_matematicas,
                    ROUND(avg_punt_global, 1) AS promedio_global
                FROM gold.fct_agg_colegios_ano
                WHERE CAST(ano AS INTEGER) = ?
                  AND nombre_colegio IS NOT NULL
                  AND avg_punt_matematicas IS NOT NULL
                ORDER BY avg_punt_matematicas DESC
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
                "rows": [
                    {
                        "nombre": row[0],
                        "departamento": row[1],
                        "municipio": row[2],
                        "sector": row[3],
                        "score_math": float(row[4]) if row[4] is not None else None,
                        "score_global": float(row[5]) if row[5] is not None else None,
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
