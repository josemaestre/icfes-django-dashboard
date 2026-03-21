"""
Dashboard Nacional Motivacional

Expone los datos de análisis motivacional de colegios:
- fct_perfil_motivacional  : KMeans k=6 por colegio (Rezagado→Excepcional)
- fct_momentum_motivacional: tendencia lineal del score ponderado
- fct_polarizacion_academica: HHI + bimodalidad + Gini
- fct_distribucion_niveles : bandas desmotivado→excelencia por sector/género/depto
"""
import logging

import duckdb
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .db_utils import execute_query

logger = logging.getLogger(__name__)
_CACHE_TTL = 60 * 60 * 2  # 2 horas


def _cached(key, timeout, func):
    data = cache.get(key)
    if data is None:
        data = func()
        cache.set(key, data, timeout)
    return data


def _is_table_missing(exc):
    return isinstance(exc, duckdb.CatalogException) or (
        "CatalogException" in type(exc).__name__ or
        "does not exist" in str(exc)
    )


def _build_where(ano, departamento, sector, materia, prefix=""):
    """Construye cláusula WHERE y params para las tablas motivacionales."""
    p = f"{prefix}." if prefix else ""
    clauses, params = [], []
    if ano:
        clauses.append(f"CAST({p}ano AS INTEGER) = ?")
        params.append(int(ano))
    if departamento:
        clauses.append(f"UPPER({p}departamento) = UPPER(?)")
        params.append(departamento)
    if sector:
        clauses.append(f"UPPER({p}sector) = UPPER(?)")
        params.append(sector)
    if materia:
        clauses.append(f"{p}materia = ?")
        params.append(materia)
    return (" AND ".join(clauses) if clauses else "1=1"), params


# ── API: Resumen / KPIs nacionales ──────────────────────────────────────────

@require_GET
def api_motivacional_resumen(request):
    ano       = request.GET.get('ano', '2024')
    materia   = request.GET.get('materia', 'global')

    def fetch():
        try:
            where_m, params_m = _build_where(ano, None, None, materia)
            query = f"""
            SELECT
                COUNT(*) AS total_colegios,
                COUNT(*) FILTER (WHERE direccion = 'mejorando')    AS mejorando,
                COUNT(*) FILTER (WHERE direccion = 'deteriorando') AS deteriorando,
                COUNT(*) FILTER (WHERE direccion = 'estable')      AS estable,
                ROUND(COUNT(*) FILTER (WHERE direccion = 'mejorando')    * 100.0 / NULLIF(COUNT(*), 0), 1) AS pct_mejorando,
                ROUND(COUNT(*) FILTER (WHERE direccion = 'deteriorando') * 100.0 / NULLIF(COUNT(*), 0), 1) AS pct_deteriorando,
                ROUND(COUNT(*) FILTER (WHERE direccion = 'estable')      * 100.0 / NULLIF(COUNT(*), 0), 1) AS pct_estable,
                ROUND(AVG(weighted_score), 3) AS score_promedio,
                ROUND(AVG(momentum_score) FILTER (WHERE momentum_score IS NOT NULL), 4) AS momentum_promedio
            FROM gold.fct_momentum_motivacional
            WHERE {where_m}
            """
            df = execute_query(query, params=params_m)
            return df.to_dict(orient='records')[0] if not df.empty else {}
        except Exception as exc:
            if _is_table_missing(exc):
                return {'error': 'tabla_no_disponible'}
            raise

    key = f"mot_resumen_{ano}_{materia}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_resumen error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Distribución de perfiles (clusters KMeans) ─────────────────────────

@require_GET
def api_motivacional_perfiles(request):
    ano    = request.GET.get('ano', '2024')
    sector = request.GET.get('sector', '')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, None)
            query = f"""
            SELECT
                cluster_nombre,
                sector,
                COUNT(*) AS colegios
            FROM gold.fct_perfil_motivacional
            WHERE {where}
            GROUP BY cluster_nombre, sector
            ORDER BY cluster_nombre, sector
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_perfiles_{ano}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_perfiles error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Momentum por departamento ──────────────────────────────────────────

@require_GET
def api_motivacional_momentum(request):
    ano        = request.GET.get('ano', '2024')
    materia    = request.GET.get('materia', 'global')
    departamento = request.GET.get('departamento', '')

    def fetch():
        try:
            where, params = _build_where(ano, departamento, None, materia)
            query = f"""
            SELECT
                departamento,
                direccion,
                COUNT(*) AS colegios,
                ROUND(AVG(weighted_score), 3) AS score_promedio,
                ROUND(AVG(momentum_score) FILTER (WHERE momentum_score IS NOT NULL), 4) AS momentum_promedio
            FROM gold.fct_momentum_motivacional
            WHERE {where}
            GROUP BY departamento, direccion
            ORDER BY departamento, direccion
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_momentum_{ano}_{materia}_{departamento}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_momentum error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Distribución de bandas motivacionales ──────────────────────────────

@require_GET
def api_motivacional_distribucion(request):
    ano    = request.GET.get('ano', '2024')
    materia = request.GET.get('materia', 'global')
    sector  = request.GET.get('sector', '')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, materia)
            query = f"""
            SELECT
                sector,
                materia,
                nivel,
                nivel_orden,
                SUM(estudiantes) AS estudiantes
            FROM gold.fct_distribucion_niveles
            WHERE {where}
            GROUP BY sector, materia, nivel, nivel_orden
            ORDER BY sector, nivel_orden
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_distribucion_{ano}_{materia}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_distribucion error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Polarización por departamento ──────────────────────────────────────

@require_GET
def api_motivacional_polarizacion(request):
    ano        = request.GET.get('ano', '2024')
    materia    = request.GET.get('materia', 'global')
    departamento = request.GET.get('departamento', '')

    def fetch():
        try:
            where, params = _build_where(ano, departamento, None, materia)
            query = f"""
            SELECT
                departamento,
                categoria_polarizacion,
                COUNT(*) AS colegios,
                ROUND(AVG(hhi), 4)         AS hhi_promedio,
                ROUND(AVG(bimodalidad), 4) AS bimodalidad_promedio,
                ROUND(AVG(gini), 4)        AS gini_promedio
            FROM gold.fct_polarizacion_academica
            WHERE {where}
            GROUP BY departamento, categoria_polarizacion
            ORDER BY departamento, categoria_polarizacion
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_polarizacion_{ano}_{materia}_{departamento}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_polarizacion error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Tendencia histórica de bandas motivacionales (todos los años) ────────

@require_GET
def api_motivacional_tendencia(request):
    materia = request.GET.get('materia', 'global')
    sector  = request.GET.get('sector', '')

    def fetch():
        try:
            clauses, params = [], []
            if materia:
                clauses.append("materia = ?")
                params.append(materia)
            if sector:
                clauses.append("UPPER(sector) = UPPER(?)")
                params.append(sector)
            where = " AND ".join(clauses) if clauses else "1=1"
            query = f"""
            SELECT
                CAST(ano AS INTEGER)  AS ano,
                nivel,
                nivel_orden,
                SUM(estudiantes)      AS estudiantes
            FROM gold.fct_distribucion_niveles
            WHERE {where}
            GROUP BY ano, nivel, nivel_orden
            ORDER BY ano, nivel_orden
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_tendencia_{materia}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_tendencia error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Colegios por perfil/cluster (tabla interactiva) ─────────────────────

@require_GET
def api_motivacional_colegios_perfil(request):
    ano          = request.GET.get('ano', '2024')
    cluster      = request.GET.get('cluster', '')
    departamento = request.GET.get('departamento', '')
    sector       = request.GET.get('sector', '')

    def fetch():
        try:
            clauses, params = [], []
            if ano:
                clauses.append("CAST(ano AS INTEGER) = ?")
                params.append(int(ano))
            if cluster:
                clauses.append("cluster_nombre = ?")
                params.append(cluster)
            if departamento:
                clauses.append("UPPER(departamento) = UPPER(?)")
                params.append(departamento)
            if sector:
                clauses.append("UPPER(sector) = UPPER(?)")
                params.append(sector)
            where = " AND ".join(clauses) if clauses else "1=1"
            query = f"""
            SELECT
                colegio_bk, nombre_colegio, departamento, sector,
                cluster_nombre, materia_fortaleza, materia_debilidad
            FROM gold.fct_perfil_motivacional
            WHERE {where}
            ORDER BY cluster_nombre, departamento, nombre_colegio
            LIMIT 500
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_colegios_perfil_{ano}_{cluster}_{departamento}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_colegios_perfil error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Distribución de clusters por departamento ────────────────────────────

@require_GET
def api_motivacional_clusters_depto(request):
    ano    = request.GET.get('ano', '2024')
    sector = request.GET.get('sector', '')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, None)
            query = f"""
            SELECT
                departamento,
                cluster_nombre,
                COUNT(*) AS colegios
            FROM gold.fct_perfil_motivacional
            WHERE {where}
            GROUP BY departamento, cluster_nombre
            ORDER BY departamento, cluster_nombre
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_clusters_depto_{ano}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_clusters_depto error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Fortalezas y debilidades por cluster (heatmap) ──────────────────────

@require_GET
def api_motivacional_fortalezas(request):
    ano    = request.GET.get('ano', '2024')
    sector = request.GET.get('sector', '')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, None)
            query = f"""
            SELECT cluster_nombre, materia_fortaleza AS materia,
                   COUNT(*) AS n_fortaleza, 0 AS n_debilidad
            FROM gold.fct_perfil_motivacional
            WHERE {where} AND materia_fortaleza IS NOT NULL
            GROUP BY cluster_nombre, materia_fortaleza
            UNION ALL
            SELECT cluster_nombre, materia_debilidad AS materia,
                   0 AS n_fortaleza, COUNT(*) AS n_debilidad
            FROM gold.fct_perfil_motivacional
            WHERE {where} AND materia_debilidad IS NOT NULL
            GROUP BY cluster_nombre, materia_debilidad
            ORDER BY cluster_nombre, materia
            """
            df = execute_query(query, params=params + params)  # UNION ALL needs params twice
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_fortalezas_{ano}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_fortalezas error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Scatter score vs momentum (4 cuadrantes) ────────────────────────────

@require_GET
def api_motivacional_scatter_momentum(request):
    ano     = request.GET.get('ano', '2024')
    materia = request.GET.get('materia', 'global')
    sector  = request.GET.get('sector', '')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, materia)
            query = f"""
            SELECT
                nombre_colegio, departamento, sector,
                ROUND(weighted_score, 3) AS weighted_score,
                ROUND(momentum_score, 4) AS momentum_score
            FROM gold.fct_momentum_motivacional
            WHERE {where} AND momentum_score IS NOT NULL
            ORDER BY momentum_score DESC
            LIMIT 5000
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_scatter_momentum_{ano}_{materia}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_scatter_momentum error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Heatmap momentum por departamento × materia ─────────────────────────

@require_GET
def api_motivacional_heatmap_momentum(request):
    ano    = request.GET.get('ano', '2024')
    sector = request.GET.get('sector', '')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, None)
            query = f"""
            SELECT
                departamento, materia,
                ROUND(AVG(momentum_score) FILTER (WHERE momentum_score IS NOT NULL), 4) AS momentum_promedio,
                COUNT(*) FILTER (WHERE direccion = 'mejorando')    AS n_mejorando,
                COUNT(*) FILTER (WHERE direccion = 'deteriorando') AS n_deteriorando,
                COUNT(*) AS total_colegios
            FROM gold.fct_momentum_motivacional
            WHERE {where}
            GROUP BY departamento, materia
            ORDER BY departamento, materia
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_heatmap_momentum_{ano}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_heatmap_momentum error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Ranking top colegios por momentum ───────────────────────────────────

@require_GET
def api_motivacional_ranking_momentum(request):
    ano       = request.GET.get('ano', '2024')
    materia   = request.GET.get('materia', 'global')
    sector    = request.GET.get('sector', '')
    direccion = request.GET.get('direccion', 'mejorando')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, materia)
            order = "DESC" if direccion == 'mejorando' else "ASC"
            query = f"""
            SELECT
                nombre_colegio, departamento, sector,
                ROUND(weighted_score, 3) AS weighted_score,
                ROUND(momentum_score, 4) AS momentum_score,
                direccion
            FROM gold.fct_momentum_motivacional
            WHERE {where} AND momentum_score IS NOT NULL AND direccion = ?
            ORDER BY momentum_score {order}
            LIMIT 20
            """
            params.append(direccion)
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_ranking_momentum_{ano}_{materia}_{sector}_{direccion}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_ranking_momentum error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Scatter HHI vs bimodalidad por departamento ─────────────────────────

@require_GET
def api_motivacional_scatter_polarizacion(request):
    ano     = request.GET.get('ano', '2024')
    materia = request.GET.get('materia', 'global')
    sector  = request.GET.get('sector', '')

    def fetch():
        try:
            where, params = _build_where(ano, None, sector, materia)
            query = f"""
            SELECT
                departamento, categoria_polarizacion,
                ROUND(AVG(hhi), 4)         AS hhi,
                ROUND(AVG(bimodalidad), 4) AS bimodalidad,
                ROUND(AVG(gini), 4)        AS gini,
                COUNT(*) AS colegios
            FROM gold.fct_polarizacion_academica
            WHERE {where}
            GROUP BY departamento, categoria_polarizacion
            ORDER BY departamento
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_scatter_polar_{ano}_{materia}_{sector}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_scatter_polarizacion error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)


# ── API: Ranking departamentos por polarización ───────────────────────────────

@require_GET
def api_motivacional_ranking_polarizacion(request):
    ano     = request.GET.get('ano', '2024')
    materia = request.GET.get('materia', 'global')

    def fetch():
        try:
            where, params = _build_where(ano, None, None, materia)
            query = f"""
            SELECT
                departamento,
                ROUND(AVG(hhi), 4)         AS hhi_promedio,
                ROUND(AVG(bimodalidad), 4) AS bimodalidad_promedio,
                ROUND(AVG(gini), 4)        AS gini_promedio,
                COUNT(*) FILTER (WHERE categoria_polarizacion = 'polarizado')  AS n_polarizado,
                COUNT(*) FILTER (WHERE categoria_polarizacion = 'concentrado') AS n_concentrado,
                COUNT(*) FILTER (WHERE categoria_polarizacion = 'distribuido') AS n_distribuido,
                COUNT(*) AS total_colegios
            FROM gold.fct_polarizacion_academica
            WHERE {where}
            GROUP BY departamento
            ORDER BY hhi_promedio DESC
            """
            df = execute_query(query, params=params)
            return df.to_dict(orient='records')
        except Exception as exc:
            if _is_table_missing(exc):
                return []
            raise

    key = f"mot_ranking_polar_{ano}_{materia}"
    try:
        return JsonResponse({'data': _cached(key, _CACHE_TTL, fetch)})
    except Exception as exc:
        logger.error("api_motivacional_ranking_polarizacion error: %s", exc)
        return JsonResponse({'error': str(exc)}, status=500)
