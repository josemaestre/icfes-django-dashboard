"""
Evolución del rendimiento académico — Landing SEO pública.

Nacional y por departamento (materia Global, todos los años 1996-2024).
Los datos anteriores a _ANO_PUBLIC_FROM aparecen con blur en el gráfico
para crear FOMO y convertir a registro. El detalle por materia queda
detrás del login como palanca adicional de conversión.
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
_ANO_PUBLIC_FROM = 2015      # años < este valor aparecen con blur en el gráfico

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


def _get_chart_data(departamento: str | None) -> list[dict]:
    """Query histórico completo de bandas motivacionales por año (materia=global, todos los años)."""
    cache_key = f"motland_chart_v2_{departamento or 'nacional'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        clauses = ["materia = 'global'"]
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

    ano_min_data = min((r['ano'] for r in chart_data), default=1996)

    if departamento_label:
        title = (
            f"Evolución del rendimiento ICFES en {departamento_label} "
            f"({ano_min_data}–{ano}) | ICFES Analytics"
        )
        description = (
            f"¿Está mejorando la educación en {departamento_label}? "
            f"En {ano}, el {pct_dedicado}% de estudiantes alcanzó nivel Dedicado "
            f"y el {pct_desconectado}% está Desconectado. "
            f"Análisis histórico ICFES {ano_min_data}–{ano} por bandas motivacionales."
        )
        canonical = (
            f"https://www.icfes-analytics.com/icfes/bandas-motivacionales/{departamento_slug}/"
        )
    else:
        title = (
            f"Evolución del rendimiento académico en Colombia "
            f"(ICFES {ano_min_data}–{ano}) | ICFES Analytics"
        )
        description = (
            f"¿Está mejorando realmente la educación en Colombia? "
            f"Analiza cómo ha evolucionado el rendimiento ICFES desde {ano_min_data}: "
            f"más estudiantes alcanzan niveles altos… pero también persiste una población desconectada. "
            f"Datos {ano_min_data}–{ano} por departamento."
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
            'ano_public_from': _ANO_PUBLIC_FROM,
            'ano_min_data': ano_min_data,
            'depto_links': depto_links,
            'seo': {'title': title, 'description': description},
            'canonical_url': canonical,
        },
    )
