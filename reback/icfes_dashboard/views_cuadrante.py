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

import json
import logging
import math

from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from .db_utils import execute_query, get_departamentos, resolve_schema

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60 * 2       # 2 hours  (API endpoint)
_LANDING_CACHE_TTL = 60 * 60 * 24  # 24 hours (landing pages)
_LANDING_ANO = 2024

# ---------------------------------------------------------------------------
# Metadata for landing pages
# ---------------------------------------------------------------------------

_CUADRANTE_META = {
    "estrella": {
        "nombre": "Colegios Estrella",
        "emoji": "⭐",
        "color": "#1a6b3a",
        "color_light": "#e6f4ec",
        "descripcion": (
            "Los colegios estrella son los líderes del sistema educativo colombiano: "
            "mejoran su puntaje ICFES año tras año y se ubican por encima del promedio "
            "de colegios del mismo tipo (oficial o privado) en su departamento. "
            "Son instituciones con tendencia positiva y desempeño académico destacado."
        ),
    },
    "consolidada": {
        "nombre": "Colegios Consolidados",
        "emoji": "🏛️",
        "color": "#1565c0",
        "color_light": "#e3eefa",
        "descripcion": (
            "Los colegios consolidados tienen puntajes por encima del promedio de sus pares, "
            "pero su tendencia es levemente negativa. Son instituciones con alta reputación "
            "que necesitan revisar su estrategia académica para mantener su posición de liderazgo."
        ),
    },
    "emergente": {
        "nombre": "Colegios Emergentes",
        "emoji": "🚀",
        "color": "#e65100",
        "color_light": "#fff3e0",
        "descripcion": (
            "Los colegios emergentes registran la mayor mejora en puntaje ICFES, aunque todavía "
            "están por debajo del promedio de colegios similares en su región. "
            "Son las instituciones más prometedoras: con la trayectoria actual, "
            "pronto alcanzarán a los líderes del sistema."
        ),
    },
    "alerta": {
        "nombre": "Colegios en Alerta",
        "emoji": "⚠️",
        "color": "#7b1fa2",
        "color_light": "#f3e5f5",
        "descripcion": (
            "Los colegios en alerta presentan puntajes por debajo del promedio de sus pares "
            "y una tendencia a la baja. Estas instituciones requieren atención prioritaria "
            "y planes de mejoramiento urgentes para revertir la situación académica."
        ),
    },
}

_DEPTO_SLUG_ALIASES = {
    "bogota": "Bogotá DC",
    "bogota-dc": "Bogotá DC",
    "norte-santander": "Norte de Santander",
    "norte-de-santander": "Norte de Santander",
    "san-andres": "San Andr",
    "valle": "Valle del Cauca",
    "valle-del-cauca": "Valle del Cauca",
    "la-guajira": "La Guajira",
    "amazonas": "Amazonas",
}

# Sort criteria for top-N per quadrant
_SORT_CFG = {
    "estrella":    ("tendencia", False),           # highest tendencia first
    "consolidada": ("desempeno_relativo", False),  # most above peers first
    "emergente":   ("tendencia", False),           # highest tendencia first
    "alerta":      ("tendencia", True),            # lowest tendencia first (worst decline)
}

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
# Landing page helpers
# ---------------------------------------------------------------------------

def _resolve_depto_slug(slug):
    """Map a URL slug to the exact departamento name stored in the DB.
    Returns the DB name string or None if not found.
    """
    slug = (slug or "").strip().lower()
    if not slug:
        return None
    try:
        q = resolve_schema(
            "SELECT DISTINCT departamento FROM gold.fct_agg_colegios_ano "
            "WHERE CAST(ano AS INTEGER) = ? AND departamento IS NOT NULL "
            "ORDER BY departamento"
        )
        df = execute_query(q, params=[_LANDING_ANO])
        deptos = df["departamento"].tolist() if not df.empty else []
    except Exception:
        deptos = []

    for dep in deptos:
        if slugify(dep) == slug:
            return dep

    # Alias fallback (partial fragment match)
    fragment = _DEPTO_SLUG_ALIASES.get(slug)
    if fragment:
        for dep in deptos:
            if fragment.lower() in dep.lower():
                return dep
    return None


def _build_landing_query(depto_name=None):
    """Build SQL query for landing pages (no sector filter, optional depto)."""
    clauses = []
    extra_params: list = []
    if depto_name:
        clauses.append("AND a.departamento = ?")
        extra_params.append(depto_name)
    extra_where = " ".join(clauses)
    query = resolve_schema(_QUERY.format(extra_where=extra_where))
    return query, extra_params


def _safe_float(v):
    """Return float or None — guards against NaN from DuckDB."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _top_n_per_quadrant(records, n=30):
    """Return top-N records per quadrant sorted by the appropriate criterion."""
    result = []
    for q, (sort_key, ascending) in _SORT_CFG.items():
        q_recs = [r for r in records if r.get("cuadrante") == q]
        q_sorted = sorted(q_recs, key=lambda x: (x.get(sort_key) or 0), reverse=not ascending)
        result.extend(q_sorted[:n])
    return result


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


# ---------------------------------------------------------------------------
# SEO Landing page  — /cuadrante/<cuadrante>/[<depto_slug>/]
# ---------------------------------------------------------------------------

@cache_page(_LANDING_CACHE_TTL)
def cuadrante_landing(request, cuadrante, depto_slug=None):
    """Public SEO landing page for a quadrant, nationally or by department."""
    if cuadrante not in _CUADRANTE_META:
        raise Http404("Cuadrante no encontrado")

    meta = _CUADRANTE_META[cuadrante]

    # Resolve departamento slug → exact DB name
    depto_nombre = None
    canonical_depto_slug = None
    if depto_slug:
        depto_nombre = _resolve_depto_slug(depto_slug)
        if depto_nombre is None:
            raise Http404("Departamento no encontrado")
        canonical_depto_slug = slugify(depto_nombre)
        if canonical_depto_slug != depto_slug:
            return redirect(f"/icfes/cuadrante/{cuadrante}/{canonical_depto_slug}/", permanent=True)

    # Fetch data from DB
    try:
        query, extra_params = _build_landing_query(depto_nombre)
        params = [_LANDING_ANO, *extra_params, _LANDING_ANO]
        df = execute_query(query, params=params)
        records = df.to_dict(orient="records") if not df.empty else []
    except Exception as exc:
        logger.error("cuadrante_landing data error: %s", exc)
        records = []

    # Sanitize NaN floats → None (safe for JSON)
    for r in records:
        for k in ("tendencia", "desempeno_relativo", "puntaje"):
            r[k] = _safe_float(r.get(k))

    # Server-rendered table: top 20 of protagonist quadrant
    sort_key, ascending = _SORT_CFG[cuadrante]
    protagonist_records = [r for r in records if r.get("cuadrante") == cuadrante]
    tabla = sorted(
        protagonist_records,
        key=lambda x: (x.get(sort_key) or 0),
        reverse=not ascending,
    )[:20]

    # Chart data: top 30 per quadrant embedded as JSON (~120 pts)
    chart_records = _top_n_per_quadrant(records, n=30)
    chart_data_json = json.dumps(chart_records, ensure_ascii=False, default=str)

    # Quadrant counts (for the page)
    counts = {q: sum(1 for r in records if r.get("cuadrante") == q) for q in _CUADRANTE_META}

    # Department nav list
    try:
        all_deptos = get_departamentos()
        deptos_nav = [{"nombre": d, "slug": slugify(d)} for d in all_deptos]
    except Exception:
        deptos_nav = []

    # SEO metadata
    geo_label = f"en {depto_nombre}" if depto_nombre else "en Colombia"
    seo_title = f"{meta['emoji']} {meta['nombre']} {geo_label} — ICFES {_LANDING_ANO}"
    n_prot = counts.get(cuadrante, 0)
    seo_description = (
        f"Los {n_prot} {meta['nombre'].lower()} {geo_label} según el ICFES {_LANDING_ANO}. "
        f"Ver ranking completo, puntajes y tendencias de mejora colegio por colegio."
    )
    canonical = request.build_absolute_uri(request.path)

    # Breadcrumb
    breadcrumb = [{"nombre": "Colombia", "url": f"/icfes/cuadrante/{cuadrante}/"}]
    if depto_nombre:
        breadcrumb.append({
            "nombre": depto_nombre,
            "url": f"/icfes/cuadrante/{cuadrante}/{canonical_depto_slug}/",
        })
    breadcrumb.append({"nombre": meta["nombre"], "url": None})

    # Schema.org ItemList
    schema_items = [
        {"@type": "ListItem", "position": i, "name": s.get("nombre_colegio", ""),
         "url": f"https://icfes-analytics.com/icfes/colegio/{s['slug']}/"}
        for i, s in enumerate(tabla, 1) if s.get("slug")
    ]
    structured_data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": seo_title,
        "description": seo_description,
        "itemListElement": schema_items,
    }

    context = {
        "cuadrante": cuadrante,
        "meta": meta,
        "depto_nombre": depto_nombre,
        "depto_slug": canonical_depto_slug,
        "tabla": tabla,
        "counts": counts,
        "chart_data_json": chart_data_json,
        "deptos_nav": deptos_nav,
        "otros_cuadrantes": [
            {"key": k, "meta": v, "count": counts.get(k, 0)} for k, v in _CUADRANTE_META.items() if k != cuadrante
        ],
        "ano": _LANDING_ANO,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "canonical": canonical,
        "breadcrumb": breadcrumb,
        "structured_data_json": json.dumps(structured_data, ensure_ascii=False),
    }
    return render(request, "icfes_dashboard/landing/cuadrante_landing.html", context)
