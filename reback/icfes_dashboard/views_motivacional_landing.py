"""
Bandas Motivacionales — Landing SEO pública.

Nacional y por departamento (solo materia Global, últimos 10 años).
La historia completa (1996–2024) y el detalle por materia quedan
detrás del login como palanca de conversión.
"""
from __future__ import annotations

import json
import logging

from django.core.cache import cache
from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify

from .db_utils import execute_query

logger = logging.getLogger(__name__)
_CACHE_TTL = 60 * 60 * 12   # 12 h
_ANO_MIN_PUBLIC = 2015       # 10 años públicos (2015-2024)

# Colores por nivel — deben coincidir con el dashboard interno
_NIVEL_COLORS = {
    'Desmotivado':  '#ef4444',
    'Desconectado': '#f97316',
    'Motivado':     '#eab308',
    'Pasaron':      '#94a3b8',
    'Comprometido': '#3b82f6',
    'Dedicado':     '#10b981',
    'Excelencia':   '#22c55e',
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_departamentos() -> list[dict]:
    """Lista de departamentos con datos en fct_distribucion_niveles (cached)."""
    key = "motland_deptos_v2"
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        df = execute_query("""
            SELECT DISTINCT departamento
            FROM gold.fct_distribucion_niveles
            WHERE departamento IS NOT NULL
              AND departamento NOT IN ('', 'EXTERIOR', 'SIN INFORMACION')
            ORDER BY departamento
        """)
        data = df.to_dict(orient='records')
    except Exception as exc:
        logger.warning("motland_deptos error: %s", exc)
        data = []
    cache.set(key, data, _CACHE_TTL)
    return data


def _slug_to_depto(slug: str) -> str | None:
    """Convierte slug URL → nombre de departamento real del DB."""
    deptos = _get_departamentos()
    for d in deptos:
        raw = d['departamento']
        if slugify(raw) == slug:
            return raw
    return None


def _pretty_depto(name: str) -> str:
    """Capitaliza bien el nombre de departamento (maneja DC, del, de la...)."""
    stopwords = {'de', 'del', 'la', 'las', 'los', 'el', 'y'}
    uppercase_words = {'dc', 'nbi'}
    words = name.lower().split()
    result = []
    for i, w in enumerate(words):
        if w in uppercase_words:
            result.append(w.upper())
        elif i > 0 and w in stopwords:
            result.append(w)
        else:
            result.append(w.capitalize())
    return ' '.join(result)


def _get_chart_data(departamento: str | None, ano_min: int = _ANO_MIN_PUBLIC) -> list[dict]:
    """Query histórico de bandas motivacionales por año (materia=global)."""
    cache_key = f"motland_chart_{departamento or 'nacional'}_{ano_min}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        clauses = ["materia = 'global'", f"CAST(ano AS INTEGER) >= {ano_min}"]
        params: list = []
        if departamento:
            clauses.append("UPPER(departamento) = UPPER(?)")
            params.append(departamento)
        where = " AND ".join(clauses)
        df = execute_query(
            f"""
            SELECT
                CAST(ano AS INTEGER) AS ano,
                nivel,
                nivel_orden,
                SUM(estudiantes)     AS estudiantes
            FROM gold.fct_distribucion_niveles
            WHERE {where}
            GROUP BY ano, nivel, nivel_orden
            ORDER BY ano, nivel_orden
            """,
            params=params if params else None,
        )
        data = df.to_dict(orient='records')
    except Exception as exc:
        logger.warning("motland_chart_data error: %s", exc)
        data = []
    cache.set(cache_key, data, _CACHE_TTL)
    return data


def _compute_kpis(data: list[dict]) -> dict:
    """KPIs del año más reciente disponible."""
    if not data:
        return {}
    latest_ano = max(r['ano'] for r in data)
    latest = [r for r in data if r['ano'] == latest_ano]
    total = sum(r['estudiantes'] for r in latest)
    if not total:
        return {'ano': latest_ano}
    kpis: dict = {'ano': latest_ano, 'total': total}
    for r in latest:
        key = r['nivel'].lower().replace(' ', '_')
        kpis[key] = round(r['estudiantes'] * 100 / total, 1)
    return kpis


# ── vista principal ───────────────────────────────────────────────────────────

def motivacional_tendencia_landing(request, departamento_slug: str | None = None):
    """Landing pública: Evolución Histórica de Bandas Motivacionales."""
    departamento_name = None
    departamento_label = None

    if departamento_slug:
        departamento_name = _slug_to_depto(departamento_slug)
        if not departamento_name:
            raise Http404
        departamento_label = _pretty_depto(departamento_name)

    chart_data = _get_chart_data(departamento_name)

    if departamento_slug and not chart_data:
        raise Http404

    kpis = _compute_kpis(chart_data)

    # Nav: lista de departamentos para la página nacional
    depto_links = []
    if not departamento_slug:
        for d in _get_departamentos():
            raw = d['departamento']
            depto_links.append({
                'slug': slugify(raw),
                'label': _pretty_depto(raw),
            })

    # SEO
    pct_dedicado = kpis.get('dedicado', 0)
    pct_desconectado = kpis.get('desconectado', 0)
    ano = kpis.get('ano', 2024)

    if departamento_label:
        title = (
            f"Bandas Motivacionales ICFES {departamento_label} "
            f"{_ANO_MIN_PUBLIC}–{ano} | ICFES Analytics"
        )
        description = (
            f"En {departamento_label}, el {pct_dedicado}% de estudiantes alcanzó "
            f"la banda Dedicado y el {pct_desconectado}% está Desconectado ({ano}). "
            f"Evolución histórica de las 7 bandas motivacionales ICFES."
        )
        canonical = (
            f"https://www.icfes-analytics.com/icfes/bandas-motivacionales/{departamento_slug}/"
        )
    else:
        title = (
            f"Evolución de Bandas Motivacionales ICFES en Colombia "
            f"{_ANO_MIN_PUBLIC}–{ano} | ICFES Analytics"
        )
        description = (
            f"Colombia se polariza: la banda Dedicado creció al {pct_dedicado}% en {ano}, "
            f"pero el Desconectado también sube. Análisis de 7 bandas motivacionales ICFES "
            f"por departamento desde {_ANO_MIN_PUBLIC}."
        )
        canonical = "https://www.icfes-analytics.com/icfes/bandas-motivacionales/"

    return render(
        request,
        'icfes_dashboard/landing/motivacional_tendencia_landing.html',
        {
            'chart_data_json': json.dumps(chart_data),
            'nivel_colors_json': json.dumps(_NIVEL_COLORS),
            'departamento_slug': departamento_slug,
            'departamento_label': departamento_label,
            'kpis': kpis,
            'ano_min_public': _ANO_MIN_PUBLIC,
            'depto_links': depto_links,
            'seo': {'title': title, 'description': description},
            'canonical_url': canonical,
        },
    )
