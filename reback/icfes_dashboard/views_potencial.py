"""
Potencial Educativo — Landing SEO para colegios que superaron su pronóstico ML.

El modelo `fct_potencial_educativo` estima el puntaje esperado de cada colegio
según su contexto (sector, región, calendario, tamaño, ubicación geográfica).
El `exceso` = puntaje real − puntaje esperado.

Clasificaciones elegibles para estas landing pages:
  Excepcional  (percentil_exceso >= 90): supera ampliamente lo esperado
  Notable      (percentil_exceso >= 75): supera claramente lo esperado
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

_LANDING_CACHE_TTL = 60 * 60 * 24   # 24 h
_LANDING_ANO = 2024

_SECTOR_MAP = {
    "oficial": "OFICIAL",
    "privado": "NO OFICIAL",
}

_SECTOR_LABEL = {
    "oficial": "Oficiales",
    "privado": "Privados",
}

# Maps known raw-name variants (ALL-CAPS or short forms from fct_potencial_educativo)
# to the canonical display name used in dim_colegios_slugs.
# Used by nav dedup in views and sitemap_views to avoid duplicate dept buttons/URLs.
DEPT_NAME_CANONICAL = {
    "BOGOTÁ":    "Bogotá DC",
    "BOGOTA":    "Bogotá DC",
    "BOGOTÁ DC": "Bogotá DC",
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
}

_QUERY = """
SELECT
    p.nombre_colegio,
    p.sector,
    COALESCE(s.departamento, p.departamento) AS departamento,
    COALESCE(s.municipio, '')                AS municipio,
    ROUND(p.avg_global, 1)        AS puntaje_real,
    ROUND(p.score_esperado, 1)    AS puntaje_esperado,
    ROUND(p.exceso, 1)            AS exceso,
    ROUND(p.percentil_exceso, 1)  AS percentil_exceso,
    p.ranking_exceso_nacional,
    p.clasificacion,
    s.slug
FROM gold.fct_potencial_educativo p
LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = p.colegio_bk
WHERE p.clasificacion IN ('Excepcional', 'Notable')
  {extra_where}
ORDER BY p.exceso DESC
LIMIT 500
"""


def _resolve_depto_slug(slug: str):
    """Slug → nombre canónico (de fct_agg_colegios_ano) o None si no existe."""
    slug = (slug or "").strip().lower()
    if not slug:
        return None
    try:
        # Use canonical names from fct_agg_colegios_ano (same as views_cuadrante)
        q = resolve_schema(
            "SELECT DISTINCT departamento FROM gold.fct_agg_colegios_ano "
            "WHERE CAST(ano AS INTEGER) = 2024 AND departamento IS NOT NULL "
            "ORDER BY departamento"
        )
        df = execute_query(q)
        deptos = df["departamento"].tolist() if not df.empty else []
    except Exception:
        deptos = []

    for dep in deptos:
        if slugify(dep) == slug:
            return dep

    fragment = _DEPTO_SLUG_ALIASES.get(slug)
    if fragment:
        for dep in deptos:
            if fragment.lower() in dep.lower():
                return dep
    return None


def _safe_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _build_query(depto_name=None, sector_db=None):
    clauses = []
    params = []
    if depto_name:
        # Filter using canonical dept name from the JOIN (s.departamento)
        clauses.append("AND COALESCE(s.departamento, p.departamento) = ?")
        params.append(depto_name)
    if sector_db:
        clauses.append("AND p.sector = ?")
        params.append(sector_db)
    extra_where = " ".join(clauses)
    query = resolve_schema(_QUERY.format(extra_where=extra_where))
    return query, params


# ---------------------------------------------------------------------------
# Landing page view
# ---------------------------------------------------------------------------

@cache_page(_LANDING_CACHE_TTL)
def potencial_landing(request, first_slug=None, sector_slug=None):
    """
    Handles 4 URL patterns:
      /supero-prediccion/                          first_slug=None, sector_slug=None
      /supero-prediccion/<sector>/                 first_slug='oficial'/'privado', sector_slug=None
      /supero-prediccion/<depto>/                  first_slug=<depto>, sector_slug=None
      /supero-prediccion/<depto>/<sector>/         first_slug=<depto>, sector_slug='oficial'/'privado'
    """
    # Determine if first_slug is a sector or a depto
    depto_nombre = None
    canonical_depto_slug = None
    sector_db = None
    sector_label = None

    if first_slug:
        if first_slug in _SECTOR_MAP:
            # /supero-prediccion/oficial/ or /supero-prediccion/privado/
            sector_db = _SECTOR_MAP[first_slug]
            sector_label = _SECTOR_LABEL[first_slug]
        else:
            # /supero-prediccion/<depto>/ or /supero-prediccion/<depto>/<sector>/
            depto_nombre = _resolve_depto_slug(first_slug)
            if depto_nombre is None:
                raise Http404("Departamento no encontrado")
            canonical_depto_slug = slugify(depto_nombre)
            if canonical_depto_slug != first_slug:
                suffix = f"{sector_slug}/" if sector_slug else ""
                return redirect(
                    f"/icfes/supero-prediccion/{canonical_depto_slug}/{suffix}",
                    permanent=True,
                )

    if sector_slug is not None:
        if sector_slug not in _SECTOR_MAP:
            raise Http404("Sector no válido")
        sector_db = _SECTOR_MAP[sector_slug]
        sector_label = _SECTOR_LABEL[sector_slug]

    # Fetch data
    try:
        query, params = _build_query(depto_nombre, sector_db)
        df = execute_query(query, params=params)
        records = df.to_dict(orient="records") if not df.empty else []
    except Exception as exc:
        logger.error("potencial_landing data error: %s", exc)
        records = []

    # Sanitize NaN
    for r in records:
        for k in ("puntaje_real", "puntaje_esperado", "exceso", "percentil_exceso"):
            r[k] = _safe_float(r.get(k))

    # KPIs
    n_excepcionales = sum(1 for r in records if r.get("clasificacion") == "Excepcional")
    n_notables = sum(1 for r in records if r.get("clasificacion") == "Notable")
    excesos = [r["exceso"] for r in records if r.get("exceso") is not None]
    avg_exceso = round(sum(excesos) / len(excesos), 1) if excesos else None

    # Top 20 for server-rendered table
    tabla = records[:20]
    hidden_count = max(0, len(records) - 20)

    # Dept nav — use canonical names from the join, only depts with potencial data
    try:
        nav_q = resolve_schema("""
            SELECT DISTINCT COALESCE(s.departamento, p.departamento) AS dep
            FROM gold.fct_potencial_educativo p
            LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = p.colegio_bk
            WHERE p.clasificacion IN ('Excepcional', 'Notable')
              AND COALESCE(s.departamento, p.departamento) IS NOT NULL
            ORDER BY 1
        """)
        nav_df = execute_query(nav_q)
        # Deduplicate by slug preferring title-case names over ALL-CAPS ones
        # (COALESCE returns dim_colegios_slugs name when join succeeds, uppercase
        #  from fct_potencial_educativo when it doesn't — same dept, two formats)
        deptos_raw = [
            DEPT_NAME_CANONICAL.get(d.strip(), d)
            for d in nav_df["dep"].tolist() if d and d.strip()
        ]
        deptos_raw.sort(key=lambda x: (x == x.upper(), x))  # title-case first
        seen_slugs: set = set()
        deptos_nav = []
        for d in deptos_raw:
            s = slugify(d)
            if s not in seen_slugs:
                seen_slugs.add(s)
                deptos_nav.append({"nombre": d, "slug": s})
    except Exception:
        deptos_nav = []

    # SEO
    geo_label = f"en {depto_nombre}" if depto_nombre else "en Colombia"
    sector_str = f" — {sector_label}" if sector_label else ""
    seo_title = f"Colegios que Superaron su Pronóstico ML {geo_label}{sector_str} — ICFES {_LANDING_ANO}"
    seo_description = (
        f"{n_excepcionales + n_notables} colegios {geo_label} superaron las expectativas del modelo ML "
        f"en el ICFES {_LANDING_ANO}: obtuvieron más puntaje del esperado según su contexto socioeconómico "
        f"y geográfico. Ver ranking, exceso de puntaje y perfil de cada institución."
    )
    canonical = request.build_absolute_uri(request.path)

    # Schema.org ItemList
    schema_items = [
        {
            "@type": "ListItem",
            "position": i,
            "name": s.get("nombre_colegio", ""),
            "url": f"https://icfes-analytics.com/icfes/colegio/{s['slug']}/",
        }
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
        "depto_nombre": depto_nombre,
        "depto_slug": canonical_depto_slug,
        "sector_slug": sector_slug or first_slug if (first_slug in _SECTOR_MAP) else sector_slug,
        "sector_label": sector_label,
        "tabla": tabla,
        "n_excepcionales": n_excepcionales,
        "n_notables": n_notables,
        "avg_exceso": avg_exceso,
        "hidden_count": hidden_count,
        "deptos_nav": deptos_nav,
        "ano": _LANDING_ANO,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "canonical": canonical,
        "structured_data_json": json.dumps(structured_data, ensure_ascii=False),
    }
    return render(request, "icfes_dashboard/landing/potencial_landing.html", context)
