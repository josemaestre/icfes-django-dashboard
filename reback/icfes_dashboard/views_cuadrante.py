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

from django.contrib.auth.decorators import login_required
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

DEPT_NAME_CANONICAL = {
    "BOGOTÁ": "Bogotá DC",
    "BOGOTA": "Bogotá DC",
    "BOGOTÁ DC": "Bogotá DC",
    "ANTIOQUIA": "Antioquia",
    "CALDAS": "Caldas",
    "CASANARE": "Casanare",
    "CAUCA": "Cauca",
    "CUNDINAMARCA": "Cundinamarca",
    "LA GUAJIRA": "La Guajira",
    "SANTANDER": "Santander",
}

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


# Variante Inglés: misma lógica pero con avg_punt_ingles (escala 0-100)
# Tendencia calculada inline con self-JOIN de fct_agg_colegios_ano
_QUERY_INGLES = """
WITH base AS (
    SELECT
        a.colegio_bk,
        a.nombre_colegio,
        a.departamento,
        a.municipio,
        a.sector,
        a.avg_punt_ingles,
        a.total_estudiantes,
        s.slug,
        AVG(a.avg_punt_ingles) OVER (
            PARTITION BY a.sector, a.departamento
        ) AS peer_avg
    FROM gold.fct_agg_colegios_ano a
    LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = a.colegio_bk
    WHERE CAST(a.ano AS INTEGER) = ?
      AND a.avg_punt_ingles IS NOT NULL
      AND a.sector IN ('OFICIAL', 'NO OFICIAL')
      {extra_where}
),
tendencia AS (
    SELECT
        a.colegio_bk,
        ROUND(a.avg_punt_ingles - p.avg_punt_ingles, 2) AS cambio_ingles
    FROM gold.fct_agg_colegios_ano a
    JOIN gold.fct_agg_colegios_ano p
        ON p.colegio_bk = a.colegio_bk
       AND CAST(p.ano AS INTEGER) = CAST(a.ano AS INTEGER) - 1
    WHERE CAST(a.ano AS INTEGER) = ?
      AND a.avg_punt_ingles IS NOT NULL
      AND p.avg_punt_ingles IS NOT NULL
)
SELECT
    b.nombre_colegio,
    b.departamento,
    b.municipio,
    b.sector,
    b.slug,
    CAST(b.total_estudiantes AS INTEGER)             AS total_estudiantes,
    ROUND(b.avg_punt_ingles, 1)                      AS puntaje,
    ROUND(b.avg_punt_ingles - b.peer_avg, 2)         AS desempeno_relativo,
    t.cambio_ingles                                  AS tendencia,
    CASE
        WHEN t.cambio_ingles > 0 AND (b.avg_punt_ingles - b.peer_avg) > 0 THEN 'estrella'
        WHEN t.cambio_ingles <= 0 AND (b.avg_punt_ingles - b.peer_avg) > 0 THEN 'consolidada'
        WHEN t.cambio_ingles > 0 AND (b.avg_punt_ingles - b.peer_avg) <= 0 THEN 'emergente'
        ELSE 'alerta'
    END AS cuadrante
FROM base b
JOIN tendencia t ON t.colegio_bk = b.colegio_bk
ORDER BY b.avg_punt_ingles DESC
LIMIT 3000
"""


def _build_query(sector: str, materia: str = "global") -> tuple[str, list]:
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
    template = _QUERY_INGLES if materia == "ingles" else _QUERY
    query = resolve_schema(template.format(extra_where=extra_where))
    return query, extra_params


def _clean_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _clean_school_name(value):
    return _clean_text(value)


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


def _build_narrative(records, cuadrante, depto_nombre=None, ano=_LANDING_ANO):
    """Build a data-driven narrative string for a given quadrant.

    Uses only the records already fetched (no extra DB query).
    Returns an HTML-safe string (uses <strong> tags).
    """
    from statistics import mean

    scope = depto_nombre or "Colombia"
    ano_ant = ano - 1
    q_records = [r for r in records if r.get("cuadrante") == cuadrante]
    n = len(q_records)

    if not n:
        return f"No se encontraron colegios en el cuadrante {cuadrante} para el filtro actual."

    def safe_float(v):
        try:
            f = float(v)
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    puntajes   = [f for r in q_records if (f := safe_float(r.get("puntaje")))    is not None]
    tendencias = [f for r in q_records if (f := safe_float(r.get("tendencia")))  is not None]
    desempenos = [f for r in q_records if (f := safe_float(r.get("desempeno_relativo"))) is not None]

    avg_p = round(mean(puntajes),   1) if puntajes   else None
    avg_t = round(mean(tendencias), 1) if tendencias else None
    avg_d = round(mean(desempenos), 1) if desempenos else None

    # Top school by puntaje
    top = max(q_records, key=lambda r: safe_float(r.get("puntaje")) or 0, default=None)
    # Most improved (highest tendencia)
    most_imp = max(q_records, key=lambda r: safe_float(r.get("tendencia")) or 0, default=None)
    # Worst decline (lowest tendencia)
    worst = min(q_records, key=lambda r: safe_float(r.get("tendencia")) or 0, default=None)

    def short_name(r):
        if not r:
            return "?"
        name = (r.get("nombre_colegio") or "").strip()
        words = name.split()[:4]
        s = " ".join(words)
        return s[:36] + "…" if len(s) > 36 else s

    def fmt1(v):
        return f"{v:.1f}" if v is not None else "--"

    def abs1(v):
        return f"{abs(v):.1f}" if v is not None else "--"

    n_str = f"{n:,}".replace(",", ".")

    if cuadrante == "estrella":
        return (
            f"En <strong>{scope}</strong>, <strong>{n_str} colegios</strong> mejoran su puntaje "
            f"y superan a sus pares en {ano}. Puntaje promedio: <strong>{fmt1(avg_p)}</strong>, "
            f"<strong>+{abs1(avg_d)} pts</strong> sobre colegios similares. "
            f"El mayor avance lo logró <strong>{short_name(most_imp)}</strong> "
            f"con <strong>+{fmt1(safe_float(most_imp.get('tendencia')) if most_imp else None)} pts</strong> "
            f"vs {ano_ant}."
        )
    if cuadrante == "consolidada":
        return (
            f"<strong>{n_str} colegios consolidados</strong> lideran puntaje en "
            f"<strong>{scope}</strong> — <strong>+{abs1(avg_d)} pts</strong> sobre sus pares. "
            f"Sin embargo, registran una caída promedio de <strong>{abs1(avg_t)} pts</strong> "
            f"vs {ano_ant}, señal de que su ventaja se reduce. "
            f"El puntaje más alto lo tiene <strong>{short_name(top)}</strong> "
            f"con <strong>{fmt1(safe_float(top.get('puntaje')) if top else None)} pts</strong>."
        )
    if cuadrante == "emergente":
        return (
            f"<strong>{n_str} colegios emergentes</strong> registran la mayor mejora en "
            f"<strong>{scope}</strong>: promedio de <strong>+{fmt1(avg_t)} pts</strong> vs {ano_ant}. "
            f"Aunque todavía están <strong>{abs1(avg_d)} pts</strong> por debajo de sus pares, "
            f"su trayectoria es la más prometedora. Destaca <strong>{short_name(most_imp)}</strong> "
            f"con el mayor salto: <strong>+{fmt1(safe_float(most_imp.get('tendencia')) if most_imp else None)} pts</strong>."
        )
    if cuadrante == "alerta":
        return (
            f"<strong>{n_str} colegios</strong> necesitan atención prioritaria en "
            f"<strong>{scope}</strong>. Puntaje promedio: <strong>{fmt1(avg_p)} pts</strong>, "
            f"<strong>{abs1(avg_d)} pts</strong> bajo la media de pares y con una caída de "
            f"<strong>{abs1(avg_t)} pts</strong> vs {ano_ant}. "
            f"El mayor descenso lo registra <strong>{short_name(worst)}</strong> "
            f"con <strong>{fmt1(safe_float(worst.get('tendencia')) if worst else None)} pts</strong>."
        )
    return ""


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

@login_required
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
    materia = request.GET.get("materia", "global").strip()
    if materia not in ("global", "ingles"):
        materia = "global"

    cache_key = f"cuadrante:v2:{ano}:{sector}:{materia}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached, safe=False)

    try:
        query, extra_params = _build_query(sector, materia)
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
        r["nombre_colegio"] = _clean_school_name(r.get("nombre_colegio"))
        r["departamento"] = DEPT_NAME_CANONICAL.get(_clean_text(r.get("departamento")), _clean_text(r.get("departamento")))
        r["municipio"] = _clean_text(r.get("municipio"))
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

    # Data-driven narratives for all 4 quadrants
    narratives = {
        q: _build_narrative(records, q, depto_nombre=depto_nombre, ano=_LANDING_ANO)
        for q in _CUADRANTE_META
    }

    # Department nav list
    try:
        all_deptos = get_departamentos()
        deptos_raw = [DEPT_NAME_CANONICAL.get(_clean_text(d), _clean_text(d)) for d in all_deptos if _clean_text(d)]
        deptos_raw.sort(key=lambda x: (x == x.upper(), x))
        seen_slugs = set()
        deptos_nav = []
        for d in deptos_raw:
            s = slugify(d)
            if s not in seen_slugs:
                seen_slugs.add(s)
                deptos_nav.append({"nombre": d, "slug": s})
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
    public_base = request.build_absolute_uri("/").rstrip("/")

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
        {"@type": "ListItem", "position": i, "name": _clean_school_name(s.get("nombre_colegio", "")),
         "url": f"{public_base}/icfes/colegio/{s['slug']}/"}
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
        "narratives": narratives,
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
