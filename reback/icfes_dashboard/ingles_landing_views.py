"""SEO landing pages for English/Bilingual rankings."""

import json
import logging
from datetime import date
from urllib.parse import urljoin

import duckdb
from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.utils.text import slugify

from .db_utils import get_duckdb_connection, resolve_schema

logger = logging.getLogger(__name__)


def _to_float(value, digits=1):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _absolute_url(base_url, path):
    return urljoin(f"{base_url}/", path.lstrip("/"))


def _rank_badges(row):
    badges = []
    if row.get("ranking_nacional") and row["ranking_nacional"] <= 100:
        badges.append("Top 100 nacional")
    if row.get("avg_ingles") is not None and row["avg_ingles"] >= 70:
        badges.append("Elite en inglés")
    if row.get("ing_pct_b1") is not None and row["ing_pct_b1"] >= 40:
        badges.append("B1+ alto")
    if row.get("sector") == "OFICIAL" and row.get("avg_ingles") is not None and row["avg_ingles"] >= 60:
        badges.append("Oficial destacado")
    if not badges and row.get("avg_ingles") is not None and row["avg_ingles"] >= 55:
        badges.append("Por encima de media")
    return badges[:2]


def _load_english_landing_data(departamento=None):
    with get_duckdb_connection() as conn:
        latest_year = conn.execute(
            resolve_schema("SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_agg_colegios_ano")
        ).fetchone()[0]
        if not latest_year:
            raise Http404("No hay datos de inglés disponibles")

        params = [latest_year]
        dept_filter = ""
        if departamento:
            dept_filter = " AND a.departamento = ? "
            params.append(departamento)

        kpi_query = f"""
            SELECT
                ROUND(AVG(a.avg_punt_ingles), 2) AS avg_ingles,
                ROUND(AVG(a.avg_punt_global), 2) AS avg_global,
                SUM(a.total_estudiantes) AS total_estudiantes,
                COUNT(DISTINCT a.colegio_sk) AS total_colegios,
                ROUND(AVG(CASE WHEN a.sector='OFICIAL' THEN a.avg_punt_ingles END), 2) AS avg_oficial,
                ROUND(AVG(CASE WHEN a.sector<>'OFICIAL' THEN a.avg_punt_ingles END), 2) AS avg_no_oficial,
                ROUND(SUM(COALESCE(i.ing_nivel_b1, 0)) * 100.0 / NULLIF(SUM(COALESCE(i.total_estudiantes, 0)), 0), 2) AS pct_b1_nacional
            FROM gold.fct_agg_colegios_ano a
            LEFT JOIN gold.fct_indicadores_desempeno i
              ON i.colegio_bk = a.colegio_bk AND i.ano = a.ano
            WHERE CAST(a.ano AS INTEGER) = ? {dept_filter}
              AND a.nombre_colegio != 'COLEGIO SINTETICO POR MUNICIPIO'
              AND a.total_estudiantes >= 5
        """
        kpi_row = conn.execute(resolve_schema(kpi_query), params).fetchone()

        top_query_with_slug = f"""
            SELECT
                a.colegio_sk,
                a.colegio_bk,
                a.nombre_colegio,
                a.municipio,
                a.departamento,
                a.sector,
                ROUND(a.avg_punt_ingles, 1) AS avg_ingles,
                ROUND(a.avg_punt_global, 1) AS avg_global,
                a.total_estudiantes,
                a.ranking_nacional,
                ROUND(COALESCE(i.ing_pct_b1, 0), 1) AS ing_pct_b1,
                ROUND(COALESCE(i.ing_pct_a2_o_superior, 0), 1) AS ing_pct_a2,
                COALESCE(s.slug, '') AS slug
            FROM gold.fct_agg_colegios_ano a
            LEFT JOIN gold.fct_indicadores_desempeno i
              ON i.colegio_bk = a.colegio_bk AND i.ano = a.ano
            LEFT JOIN gold.dim_colegios_slugs s
              ON s.codigo = a.colegio_bk
            WHERE CAST(a.ano AS INTEGER) = ? {dept_filter}
              AND a.nombre_colegio != 'COLEGIO SINTETICO POR MUNICIPIO'
              AND a.total_estudiantes >= 5
            ORDER BY a.avg_punt_ingles DESC, a.total_estudiantes DESC
            LIMIT 30
        """

        top_query_no_slug = f"""
            SELECT
                a.colegio_sk,
                a.colegio_bk,
                a.nombre_colegio,
                a.municipio,
                a.departamento,
                a.sector,
                ROUND(a.avg_punt_ingles, 1) AS avg_ingles,
                ROUND(a.avg_punt_global, 1) AS avg_global,
                a.total_estudiantes,
                a.ranking_nacional,
                ROUND(COALESCE(i.ing_pct_b1, 0), 1) AS ing_pct_b1,
                ROUND(COALESCE(i.ing_pct_a2_o_superior, 0), 1) AS ing_pct_a2,
                '' AS slug
            FROM gold.fct_agg_colegios_ano a
            LEFT JOIN gold.fct_indicadores_desempeno i
              ON i.colegio_bk = a.colegio_bk AND i.ano = a.ano
            WHERE CAST(a.ano AS INTEGER) = ? {dept_filter}
              AND a.nombre_colegio != 'COLEGIO SINTETICO POR MUNICIPIO'
              AND a.total_estudiantes >= 5
            ORDER BY a.avg_punt_ingles DESC, a.total_estudiantes DESC
            LIMIT 30
        """
        try:
            top_rows = conn.execute(resolve_schema(top_query_with_slug), params).fetchall()
        except duckdb.CatalogException:
            top_rows = conn.execute(resolve_schema(top_query_no_slug), params).fetchall()

        dept_query = """
            SELECT
                a.departamento,
                ROUND(AVG(a.avg_punt_ingles), 2) AS avg_ingles,
                COUNT(DISTINCT a.colegio_sk) AS total_colegios
            FROM gold.fct_agg_colegios_ano a
            WHERE CAST(a.ano AS INTEGER) = ?
              AND a.nombre_colegio != 'COLEGIO SINTETICO POR MUNICIPIO'
              AND a.total_estudiantes >= 5
            GROUP BY a.departamento
            ORDER BY avg_ingles DESC
        """
        dept_rows = conn.execute(resolve_schema(dept_query), [latest_year]).fetchall()

        top_schools = []
        for idx, row in enumerate(top_rows, start=1):
            item = {
                "rank": idx,
                "colegio_sk": row[0],
                "codigo": row[1],
                "nombre": row[2],
                "municipio": row[3],
                "departamento": row[4],
                "sector": row[5],
                "avg_ingles": _to_float(row[6]),
                "avg_global": _to_float(row[7]),
                "estudiantes": _to_int(row[8]) or 0,
                "ranking_nacional": _to_int(row[9]),
                "ing_pct_b1": _to_float(row[10]),
                "ing_pct_a2": _to_float(row[11]),
                "slug": row[12] or "",
            }
            item["badges"] = _rank_badges(item)
            top_schools.append(item)

        departments = [
            {
                "name": row[0],
                "slug": slugify(row[0] or ""),
                "avg_ingles": _to_float(row[1]),
                "total_colegios": _to_int(row[2]) or 0,
            }
            for row in dept_rows
            if row[0]
        ]

        return {
            "latest_year": int(latest_year),
            "kpis": {
                "avg_ingles": _to_float(kpi_row[0], 2) if kpi_row else None,
                "avg_global": _to_float(kpi_row[1], 2) if kpi_row else None,
                "total_estudiantes": _to_int(kpi_row[2]) if kpi_row else 0,
                "total_colegios": _to_int(kpi_row[3]) if kpi_row else 0,
                "avg_oficial": _to_float(kpi_row[4], 2) if kpi_row else None,
                "avg_no_oficial": _to_float(kpi_row[5], 2) if kpi_row else None,
                "pct_b1_nacional": _to_float(kpi_row[6], 2) if kpi_row else None,
            },
            "top_schools": top_schools,
            "departments": departments,
        }


def _render_ingles_page(request, departamento=None, departamento_slug=None):
    use_cache = request.method in {"GET", "HEAD"}
    cache_key = f"html:ingles_landing:v1:{departamento_slug or 'nacional'}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            request._cache_status = "HIT"
            return cached

    data = _load_english_landing_data(departamento=departamento)
    latest_year = data["latest_year"]
    kpis = data["kpis"]
    top_schools = data["top_schools"]
    departments = data["departments"]

    base_url = _build_base_url(request)
    canonical_url = _absolute_url(base_url, request.path)
    og_image = _absolute_url(base_url, static("images/screenshots/dashboard_main.png"))

    scope_title = f"en {departamento}" if departamento else "en Colombia"
    seo_title = f"Mejores Colegios en Inglés {scope_title} ({latest_year}) | ICFES Analytics"
    seo_description = (
        f"Ranking {latest_year} de colegios con mejor desempeño en inglés {scope_title}. "
        f"Incluye % B1+, puntajes, badges de excelencia y acceso al perfil de cada colegio."
    )

    breadcrumb = [
        {"name": "Inicio", "item": _absolute_url(base_url, "/")},
        {"name": "Inglés ICFES", "item": _absolute_url(base_url, "/icfes/ingles-seo/")},
    ]
    if departamento:
        breadcrumb.append({"name": departamento, "item": canonical_url})

    structured_data_json = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "name": seo_title,
                    "description": seo_description,
                    "url": canonical_url,
                    "dateModified": date.today().isoformat(),
                },
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": idx + 1,
                            "name": item["name"],
                            "item": item["item"],
                        }
                        for idx, item in enumerate(breadcrumb)
                    ],
                },
            ],
        },
        ensure_ascii=False,
    )

    context = {
        "departamento": departamento,
        "latest_year": latest_year,
        "kpis": kpis,
        "top_schools": top_schools,
        "departments": departments,
        "canonical_url": canonical_url,
        "structured_data_json": structured_data_json,
        "seo": {"title": seo_title, "description": seo_description, "og_image": og_image},
    }
    response = render(request, "icfes_dashboard/ingles_landing.html", context)
    if use_cache and response.status_code == 200:
        cache.set(cache_key, response, timeout=60 * 60 * 6)
        request._cache_status = "MISS"
    else:
        request._cache_status = "BYPASS"
    return response


def ingles_hub_page(request):
    return _render_ingles_page(request)


def ingles_department_page(request, departamento_slug):
    try:
        data = _load_english_landing_data()
    except Exception as exc:
        logger.error("Error loading department list for ingles landing: %s", exc)
        raise Http404("No se pudo cargar la información de inglés")

    def _compact_slug(value):
        return (value or "").replace("-", "").replace("_", "").lower()

    requested = _compact_slug(departamento_slug)
    selected = next((d for d in data["departments"] if d["slug"] == departamento_slug), None)
    if not selected:
        selected = next(
            (d for d in data["departments"] if _compact_slug(d["slug"]) == requested),
            None,
        )
    if not selected:
        raise Http404("Departamento no encontrado")
    return _render_ingles_page(
        request,
        departamento=selected["name"],
        departamento_slug=departamento_slug,
    )
