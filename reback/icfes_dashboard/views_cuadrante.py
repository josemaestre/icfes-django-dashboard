"""
Cuadrante Educativo — Magic Quadrant de colegios colombianos.

Ejes:
  X = Tendencia: cambio absoluto de puntaje global vs año anterior
  Y = Desempeño relativo: puntaje del colegio vs promedio de su grupo par
      (mismo sector + mismo departamento)

Cuadrantes:
  Estrella    (+X, +Y): mejorando y por encima de sus pares
  Consolidada (-X, +Y): por encima de pares pero perdiendo puntaje
  Emergente   (+X, -Y): por debajo de pares pero mejorando
  En Alerta   (-X, -Y): por debajo de pares y empeorando
"""
from __future__ import annotations

import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .db_utils import execute_query, get_departamentos, resolve_schema

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60 * 2  # 2 hours

_QUERY = """
WITH base AS (
    SELECT
        a.colegio_bk,
        a.nombre_colegio,
        a.departamento,
        a.municipio,
        a.sector,
        a.avg_punt_global,
        a.total_estudiantes,
        s.slug,
        AVG(a.avg_punt_global) OVER (
            PARTITION BY a.sector, a.departamento
        ) AS peer_avg
    FROM gold.fct_agg_colegios_ano a
    LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = a.colegio_bk
    WHERE CAST(a.ano AS INTEGER) = ?
      AND a.avg_punt_global IS NOT NULL
      AND a.sector IN ('OFICIAL', 'NO OFICIAL')
      {extra_where}
),
tendencia AS (
    SELECT
        codigo_dane,
        cambio_absoluto_global
    FROM gold.fct_colegio_historico
    WHERE CAST(ano AS INTEGER) = ?
      AND cambio_absoluto_global IS NOT NULL
)
SELECT
    b.nombre_colegio,
    b.departamento,
    b.municipio,
    b.sector,
    b.slug,
    CAST(b.total_estudiantes AS INTEGER)            AS total_estudiantes,
    ROUND(b.avg_punt_global, 1)                     AS puntaje,
    ROUND(b.avg_punt_global - b.peer_avg, 2)        AS desempeno_relativo,
    ROUND(t.cambio_absoluto_global, 2)              AS tendencia,
    CASE
        WHEN t.cambio_absoluto_global > 0 AND (b.avg_punt_global - b.peer_avg) > 0 THEN 'estrella'
        WHEN t.cambio_absoluto_global <= 0 AND (b.avg_punt_global - b.peer_avg) > 0 THEN 'consolidada'
        WHEN t.cambio_absoluto_global > 0 AND (b.avg_punt_global - b.peer_avg) <= 0 THEN 'emergente'
        ELSE 'alerta'
    END AS cuadrante
FROM base b
JOIN tendencia t ON t.codigo_dane = b.colegio_bk
ORDER BY b.avg_punt_global DESC
LIMIT 3000
"""


def _build_query(sector: str) -> tuple[str, list]:
    """Return (query_with_placeholders, extra_params_for_base_cte).

    Departamento filtering is intentionally done client-side in JS to avoid
    mismatches between dim_colegios and fct_agg_colegios_ano department names.
    """
    clauses = []
    extra_params: list = []
    if sector and sector in ("OFICIAL", "NO OFICIAL"):
        clauses.append("AND a.sector = ?")
        extra_params.append(sector)
    extra_where = " ".join(clauses)
    query = resolve_schema(_QUERY.format(extra_where=extra_where))
    return query, extra_params


# ---------------------------------------------------------------------------
# Page view
# ---------------------------------------------------------------------------

def cuadrante_dashboard(request):
    try:
        departamentos = get_departamentos()
    except Exception:
        departamentos = []
    return render(
        request,
        "icfes_dashboard/pages/dashboard-cuadrante.html",
        {
            "anos_disponibles": list(range(2020, 2025)),
            "departamentos": departamentos,
        },
    )


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------

@require_GET
def api_cuadrante_data(request):
    try:
        ano = int(request.GET.get("ano", 2024))
    except ValueError:
        ano = 2024
    ano = max(2015, min(ano, 2024))

    sector = request.GET.get("sector", "").strip()

    cache_key = f"cuadrante:v2:{ano}:{sector}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached, safe=False)

    try:
        query, extra_params = _build_query(sector)
        # params order: ano (for base CTE WHERE), then extra_where params, then ano (for tendencia CTE WHERE)
        params = [ano, *extra_params, ano]
        df = execute_query(query, params=params)

        if df.empty:
            result = {"data": [], "counts": {}, "ano": ano}
            cache.set(cache_key, result, _CACHE_TTL)
            return JsonResponse(result)

        records = df.to_dict(orient="records")

        counts = {
            "estrella": int((df["cuadrante"] == "estrella").sum()),
            "consolidada": int((df["cuadrante"] == "consolidada").sum()),
            "emergente": int((df["cuadrante"] == "emergente").sum()),
            "alerta": int((df["cuadrante"] == "alerta").sum()),
        }

        result = {"data": records, "counts": counts, "ano": ano}
        cache.set(cache_key, result, _CACHE_TTL)
        return JsonResponse(result)

    except Exception as exc:
        logger.error("api_cuadrante_data error: %s", exc)
        return JsonResponse({"error": str(exc)}, status=500)
