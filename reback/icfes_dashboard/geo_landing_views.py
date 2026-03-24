"""
SEO landing pages for departments and municipalities.
Uses lightweight aggregate queries from fct_agg_colegios_ano.
"""
import json
import logging
from functools import lru_cache

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.cache import cache_page

from contextlib import contextmanager

from .db_utils import get_duckdb_connection, resolve_schema


@contextmanager
def _noop_ctx(conn):
    """Yield an existing connection without closing it."""
    yield conn

logger = logging.getLogger(__name__)

# Cross-version-safe integer parsing for `ano` (avoids hard failures on dirty values).
YEAR_INT_EXPR = (
    "CASE WHEN regexp_matches(CAST(ano AS VARCHAR), '^[0-9]+$') "
    "THEN CAST(ano AS INTEGER) ELSE NULL END"
)
YEAR_INT_EXPR_F = (
    "CASE WHEN regexp_matches(CAST(f.ano AS VARCHAR), '^[0-9]+$') "
    "THEN CAST(f.ano AS INTEGER) ELSE NULL END"
)


def _safe_year_int(value):
    text = str(value or "").strip()
    if len(text) == 4 and text.isdigit():
        try:
            return int(text)
        except (TypeError, ValueError):
            return None
    return None


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
        " Revisa ranking de colegios, evolución anual y comparativos territoriales con datos actualizados."
    )
    return _trim_meta(f"{value}{extra}", max_len)


def _default_og_image(base_url):
    return f"{base_url}/icfes/og/default.png"


def _build_base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


# Aliases para departamentos cuyo nombre completo genera slugs muy largos o poco amigables.
# Clave: slug alternativo → fragmento identificador del nombre real en la DB.
_DEPARTAMENTO_SLUG_ALIASES = {
    "san-andres": "San Andr",       # "Archipiélago de San Andrés, Providencia y Santa Catalina"
    "norte-santander": "Norte de Santander",  # bots omiten "de"
    "valle": "Valle del Cauca",     # bots usan solo "valle"
    "bogota": "Bogotá",             # slugify("Bogotá DC") = "bogota-dc"
}

_MUNICIPIO_SLUG_ALIASES = {
    "bogota": "Bogotá",
    "bogota-dc": "Bogotá",
    "bogota-d-c": "Bogotá",
}


@lru_cache(maxsize=1)
def _get_all_departamentos():
    """Fetch all department names once per process — 33 rows, changes only on redeploy."""
    query = f"""
        SELECT DISTINCT departamento
        FROM gold.fct_agg_colegios_ano
        WHERE departamento IS NOT NULL AND departamento != ''
          AND {YEAR_INT_EXPR} IS NOT NULL
        ORDER BY departamento
    """
    with get_duckdb_connection() as conn:
        rows = conn.execute(resolve_schema(query)).fetchall()
    return [row[0] for row in rows]


@lru_cache(maxsize=64)
def _get_municipios_for_depto(departamento):
    """Fetch all municipalities for a department once per process — changes only on redeploy."""
    query = """
        SELECT DISTINCT municipio
        FROM gold.fct_agg_colegios_ano
        WHERE departamento = ?
          AND municipio IS NOT NULL
          AND municipio != ''
        ORDER BY municipio
    """
    with get_duckdb_connection() as conn:
        rows = conn.execute(resolve_schema(query), [departamento]).fetchall()
    return [row[0] for row in rows]


def _resolve_departamento(conn, departamento_slug):
    rows = _get_all_departamentos()

    # Primero: match exacto por slug
    for departamento in rows:
        if slugify(departamento) == departamento_slug:
            return departamento

    # Segundo: match por alias conocido
    alias_fragment = _DEPARTAMENTO_SLUG_ALIASES.get(departamento_slug)
    if alias_fragment:
        for departamento in rows:
            if alias_fragment.lower() in departamento.lower():
                return departamento

    return None


def _resolve_municipio(conn, departamento, municipio_slug):
    rows = _get_municipios_for_depto(departamento)
    for municipio in rows:
        if slugify(municipio) == municipio_slug:
            return municipio

    alias_fragment = _MUNICIPIO_SLUG_ALIASES.get((municipio_slug or "").strip().lower())
    if alias_fragment:
        for municipio in rows:
            if alias_fragment.lower() in municipio.lower():
                return municipio
    return None


def _geo_landing_context(request, departamento, municipio=None, conn=None):
    own_conn = conn is None
    cm = get_duckdb_connection() if own_conn else _noop_ctx(conn)
    with cm as c:
        where_clause, where_params = _build_geo_where(departamento, municipio)

        # Single CTE: find latest year and compute stats in one table scan
        combined_query = f"""
            WITH base AS (
                SELECT
                    {YEAR_INT_EXPR} AS ano_int,
                    avg_punt_global,
                    total_estudiantes,
                    colegio_sk,
                    MAX({YEAR_INT_EXPR}) OVER () AS max_ano
                FROM gold.fct_agg_colegios_ano
                WHERE {where_clause}
                  AND {YEAR_INT_EXPR} IS NOT NULL
            )
            SELECT
                max_ano,
                ROUND(AVG(avg_punt_global) FILTER (WHERE ano_int = max_ano), 1),
                SUM(total_estudiantes) FILTER (WHERE ano_int = max_ano),
                COUNT(DISTINCT colegio_sk) FILTER (WHERE ano_int = max_ano)
            FROM base
            GROUP BY max_ano
        """
        combined_row = c.execute(resolve_schema(combined_query), where_params).fetchone()
        if not combined_row or not combined_row[0]:
            raise Http404("No hay datos para esta ubicación")

        latest_year = int(combined_row[0])
        min_year = latest_year - 5
        stats_row = (combined_row[1], combined_row[2], combined_row[3])

        trend_query = f"""
            SELECT
                {YEAR_INT_EXPR} AS ano,
                ROUND(AVG(avg_punt_global), 1) AS promedio_global
            FROM gold.fct_agg_colegios_ano
            WHERE {where_clause}
              AND {YEAR_INT_EXPR} >= ?
            GROUP BY {YEAR_INT_EXPR}
            ORDER BY ano
        """
        trend_rows = c.execute(resolve_schema(trend_query), where_params + [min_year]).fetchall()

        national_trend_query = """
            SELECT
                CASE WHEN regexp_matches(CAST(ano AS VARCHAR), '^[0-9]+$') THEN CAST(ano AS INTEGER) ELSE NULL END AS ano,
                ROUND(AVG(avg_punt_global), 1) AS promedio_nacional
            FROM gold.fct_agg_colegios_ano
            WHERE CASE WHEN regexp_matches(CAST(ano AS VARCHAR), '^[0-9]+$') THEN CAST(ano AS INTEGER) ELSE NULL END >= ?
              AND sector != 'SINTETICO'
            GROUP BY CASE WHEN regexp_matches(CAST(ano AS VARCHAR), '^[0-9]+$') THEN CAST(ano AS INTEGER) ELSE NULL END
            ORDER BY ano
        """
        national_trend_rows = c.execute(resolve_schema(national_trend_query), [min_year]).fetchall()

        f_where, f_params = _build_geo_where(departamento, municipio, alias="f")

        top_schools_query = f"""
            SELECT
                f.nombre_colegio,
                f.sector,
                ROUND(f.avg_punt_global, 1) AS promedio_global,
                f.total_estudiantes,
                COALESCE(s.slug, '') AS slug
            FROM gold.fct_agg_colegios_ano f
            LEFT JOIN gold.dim_colegios_slugs s ON f.colegio_bk = s.codigo
            WHERE {f_where}
              AND {YEAR_INT_EXPR_F} = ?
              AND f.nombre_colegio IS NOT NULL
            ORDER BY f.avg_punt_global DESC
            LIMIT 10
        """
        top_rows = c.execute(resolve_schema(top_schools_query), f_params + [latest_year]).fetchall()

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
                WHERE {f_where}
                  AND {YEAR_INT_EXPR_F} = ?
                  AND f.nombre_colegio IS NOT NULL
                ORDER BY f.nombre_colegio ASC
            """
            all_schools_rows = c.execute(
                resolve_schema(all_schools_query), f_params + [latest_year]
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
                  AND {YEAR_INT_EXPR} = ?
                  AND municipio IS NOT NULL
                  AND municipio != ''
                GROUP BY municipio
                ORDER BY promedio_global DESC
                LIMIT 30
            """
            municipios_rows = c.execute(
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

    # When municipio and departamento are the same (Bogotá DC), avoid "Bogotá, Bogotá D.C."
    if municipio and slugify(municipio) == slugify(departamento):
        location_name = municipio
    else:
        location_name = f"{municipio}, {departamento}" if municipio else departamento
    location_type = "municipio" if municipio else "departamento"
    canonical_url = request.build_absolute_uri(request.path)
    base_url = _build_base_url(request)
    og_image = _default_og_image(base_url)

    seo_title = f"Mejores colegios de {location_name} ICFES {latest_year} | Ranking"
    seo_description = (
        f"Ranking de colegios en {location_name} según resultados ICFES {latest_year}. "
        f"Puntaje global, evolución histórica y comparativa por sector."
    )
    seo_title = _trim_meta(seo_title, 65)
    seo_description = _fit_meta_description(seo_description, min_len=110, max_len=155)

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
        "latest_year": latest_year,
        "trend_min_year": min_year,
        "trend_chart": {
            "years": [int(row[0]) for row in trend_rows],
            "scores": [float(row[1]) if row[1] is not None else None for row in trend_rows],
            "national_scores": [float(row[1]) if row[1] is not None else None for row in national_trend_rows],
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
            "og_image": og_image,
            "keywords": (
                f"ICFES {latest_year}, {location_name}, ranking colegios {location_name}, "
                f"puntaje ICFES {location_name}, pruebas saber 11 {location_name}"
            ),
        },
        "canonical_url": canonical_url,
        "structured_data_json": json.dumps([page_schema, breadcrumb_schema], ensure_ascii=False),
    }


@cache_page(60 * 60 * 6)
def departments_index_page(request):
    try:
        with get_duckdb_connection() as conn:
            try:
                query = f"""
                    WITH ranked AS (
                        SELECT
                            departamento,
                            {YEAR_INT_EXPR} AS ano,
                            ROUND(AVG(avg_punt_global), 1)  AS promedio_global,
                            SUM(total_estudiantes)           AS total_estudiantes,
                            COUNT(DISTINCT colegio_sk)       AS total_colegios,
                            ROW_NUMBER() OVER (
                                PARTITION BY departamento
                                ORDER BY {YEAR_INT_EXPR} DESC
                            ) AS rn
                        FROM gold.fct_agg_colegios_ano
                        WHERE departamento IS NOT NULL
                          AND departamento != ''
                          AND sector != 'SINTETICO'
                          AND {YEAR_INT_EXPR} IS NOT NULL
                        GROUP BY departamento, {YEAR_INT_EXPR}
                    )
                    SELECT
                        cur.departamento,
                        cur.ano                                                     AS latest_ano,
                        cur.promedio_global,
                        cur.total_estudiantes,
                        cur.total_colegios,
                        ROUND(cur.promedio_global - COALESCE(prev.promedio_global, cur.promedio_global), 1) AS delta
                    FROM ranked cur
                    LEFT JOIN ranked prev
                           ON prev.departamento = cur.departamento AND prev.rn = 2
                    WHERE cur.rn = 1
                      AND cur.departamento NOT IN ('EXTERIOR', 'SIN INFORMACION')
                    ORDER BY cur.promedio_global DESC NULLS LAST
                """
                rows = conn.execute(resolve_schema(query)).fetchall()
            except Exception:
                # Fallback for engines/envs where complex casting/window SQL can fail.
                logger.exception("Primary departments index query failed; using fallback query")
                fallback_query = """
                    SELECT
                        departamento,
                        ano,
                        ROUND(AVG(avg_punt_global), 1)  AS promedio_global,
                        SUM(total_estudiantes)           AS total_estudiantes,
                        COUNT(DISTINCT colegio_sk)       AS total_colegios
                    FROM gold.fct_agg_colegios_ano
                    WHERE departamento IS NOT NULL
                      AND departamento != ''
                      AND sector != 'SINTETICO'
                    GROUP BY departamento, ano
                """
                raw_rows = conn.execute(resolve_schema(fallback_query)).fetchall()
                by_depto = {}
                for dep, ano_raw, promedio, estudiantes, colegios in raw_rows:
                    if dep in ("EXTERIOR", "SIN INFORMACION"):
                        continue
                    year = _safe_year_int(ano_raw)
                    if year is None:
                        continue
                    by_depto.setdefault(dep, []).append(
                        (year, promedio, estudiantes, colegios)
                    )

                rows = []
                for dep, dep_rows in by_depto.items():
                    dep_rows.sort(key=lambda x: x[0], reverse=True)
                    cur = dep_rows[0]
                    prev = dep_rows[1] if len(dep_rows) > 1 else cur
                    cur_prom = float(cur[1]) if cur[1] is not None else 0.0
                    prev_prom = float(prev[1]) if prev[1] is not None else cur_prom
                    rows.append(
                        (
                            dep,
                            cur[0],
                            cur_prom,
                            cur[2],
                            cur[3],
                            round(cur_prom - prev_prom, 1),
                        )
                    )
                rows.sort(key=lambda r: (r[2] is None, -(r[2] or 0.0)))

        departments = [
            {
                "name":        row[0],
                "slug":        slugify(row[0]),
                "ano":         int(row[1]) if row[1] else None,
                "promedio":    float(row[2]) if row[2] is not None else None,
                "estudiantes": int(row[3]) if row[3] else 0,
                "colegios":    int(row[4]) if row[4] else 0,
                "delta":       float(row[5]) if row[5] is not None else 0.0,
            }
            for row in rows
        ]

        latest_year = departments[0]["ano"] if departments else 2024
        promedio_nacional = (
            round(sum(d["promedio"] for d in departments if d["promedio"]) / len(departments), 1)
            if departments else None
        )

        return render(
            request,
            "icfes_dashboard/geo_landing_simple.html",
            {
                "index_mode": True,
                "departments": departments,
                "latest_year": latest_year,
                "promedio_nacional": promedio_nacional,
                "seo": {
                    "title": f"Resultados ICFES por Departamento {latest_year} | Ranking Colombia",
                    "description": (
                        f"Compara el promedio ICFES {latest_year} de los 33 departamentos de Colombia. "
                        "Rankings, tendencias y colegios destacados por región."
                    ),
                    "keywords": "ICFES por departamento, ranking departamentos ICFES, pruebas saber 11",
                    "og_image": _default_og_image(_build_base_url(request)),
                },
                "canonical_url": request.build_absolute_uri(request.path),
            },
        )
    except Exception:
        logger.exception("Error in departments_index_page")
        # Never hard-fail public index with 404; return empty state and keep SEO URL alive.
        latest_year = 2024
        return render(
            request,
            "icfes_dashboard/geo_landing_simple.html",
            {
                "index_mode": True,
                "departments": [],
                "latest_year": latest_year,
                "promedio_nacional": None,
                "seo": {
                    "title": f"Resultados ICFES por Departamento {latest_year} | Ranking Colombia",
                    "description": (
                        f"Compara el promedio ICFES {latest_year} de los departamentos de Colombia. "
                        "Rankings, tendencias y colegios destacados por región."
                    ),
                    "keywords": "ICFES por departamento, ranking departamentos ICFES, pruebas saber 11",
                    "og_image": _default_og_image(_build_base_url(request)),
                },
                "canonical_url": request.build_absolute_uri(request.path),
                "index_error": True,
            },
            status=200,
        )


@cache_page(60 * 60 * 24 * 7)
def department_landing_page(request, departamento_slug):
    try:
        with get_duckdb_connection() as conn:
            departamento = _resolve_departamento(conn, departamento_slug)
            if not departamento:
                raise Http404("Departamento no encontrado")
            canonical_slug = slugify(departamento)
            if canonical_slug != departamento_slug:
                return redirect(f"/icfes/departamento/{canonical_slug}/", permanent=True)
            # Reuse the same connection — avoids opening a second DuckDB connection
            context = _geo_landing_context(request, departamento=departamento, municipio=None, conn=conn)
        return render(request, "icfes_dashboard/geo_landing_simple.html", context)
    except Http404:
        raise
    except Exception as e:
        import traceback
        logger.error("Error in department_landing_page for slug %s: %s\n%s", departamento_slug, e, traceback.format_exc())
        raise Http404("Error al cargar el departamento")


@cache_page(60 * 60 * 24 * 7)
def municipality_landing_page(request, departamento_slug, municipio_slug):
    try:
        with get_duckdb_connection() as conn:
            departamento = _resolve_departamento(conn, departamento_slug)
            if not departamento:
                return HttpResponse(status=410)  # Gone — URL en sitemap viejo, sin datos
            municipio = _resolve_municipio(conn, departamento, municipio_slug)
            if not municipio:
                return HttpResponse(status=410)  # Gone — municipio sin datos suficientes

            canonical_dept = slugify(departamento)
            canonical_muni = slugify(municipio)
            if canonical_dept != departamento_slug or canonical_muni != municipio_slug:
                return redirect(
                    f"/icfes/departamento/{canonical_dept}/municipio/{canonical_muni}/",
                    permanent=True,
                )
            # Reuse the same connection — avoids opening a second DuckDB connection
            context = _geo_landing_context(
                request, departamento=departamento, municipio=municipio, conn=conn
            )
        return render(request, "icfes_dashboard/geo_landing_simple.html", context)
    except Http404:
        # Municipality exists in DB but has no current-year data — redirect to dept page
        logger.warning(
            "Municipality %s/%s has no data — redirecting to dept page",
            departamento_slug, municipio_slug,
        )
        return redirect(f"/icfes/departamento/{departamento_slug}/", permanent=False)
    except Exception as e:
        import traceback
        logger.error(
            "Error in municipality_landing_page for slugs %s/%s: %s\n%s",
            departamento_slug,
            municipio_slug,
            e,
            traceback.format_exc(),
        )
        raise Http404("Error al cargar el municipio")
