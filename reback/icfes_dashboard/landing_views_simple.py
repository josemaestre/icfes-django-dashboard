"""Simplified but SEO-rich landing page view for schools."""

import json
import logging
import statistics
from datetime import date
from urllib.parse import urljoin

import duckdb
from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify

from .db_utils import get_duckdb_connection, resolve_schema
from .landing_utils import generate_school_slug

logger = logging.getLogger(__name__)


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _extract_municipio_hint(slug):
    parts = slug.split("-")
    return parts[-1] if parts else ""


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


def _format_signed(value, suffix=""):
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value}{suffix}"


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
        " Compara su desempeño por materia, tendencia anual y posición frente a su municipio y departamento."
    )
    return _trim_meta(f"{value}{extra}", max_len)


def _build_base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _absolute_url(base_url, path):
    return urljoin(f"{base_url}/", path.lstrip("/"))


def _find_school_by_slug(conn, slug):
    school_query = """
        SELECT
            s.codigo,
            s.nombre_colegio,
            s.municipio,
            s.departamento,
            s.sector,
            d.direccion,
            d.telefono,
            d.email,
            d.rector
        FROM gold.dim_colegios_slugs s
        LEFT JOIN gold.dim_colegios d ON d.colegio_bk = s.codigo
        WHERE s.slug = ?
        LIMIT 1
    """

    try:
        school_result = conn.execute(resolve_schema(school_query), [slug]).fetchone()
        if school_result:
            return school_result
    except duckdb.CatalogException as exc:
        logger.warning("dim_colegios_slugs unavailable, using fallback lookup: %s", exc)

    municipio_hint = _extract_municipio_hint(slug)
    # dim_colegios tiene nombres canónicos completos → generate_school_slug produce el slug correcto.
    # fct_colegio_historico usa abreviaciones (ej: "I.E.") que generan slugs distintos.
    fallback_query = """
        SELECT
            colegio_bk  AS codigo,
            nombre_colegio,
            municipio,
            departamento,
            sector,
            direccion,
            telefono,
            email,
            rector
        FROM gold.dim_colegios
        WHERE nombre_colegio IS NOT NULL
          AND municipio IS NOT NULL
          AND sector != 'SINTETICO'
          AND LOWER(municipio) LIKE ?
    """
    candidates = conn.execute(
        resolve_schema(fallback_query),
        [f"%{_normalize_text(municipio_hint)}%"],
    ).fetchall()

    for candidate in candidates:
        if generate_school_slug(candidate[1], candidate[2]) == slug:
            return candidate

    return None


def school_landing_page(request, slug):
    use_cache = request.method in {"GET", "HEAD"}
    cache_key = f"html:school_landing_simple:v1:{slug}"

    if use_cache:
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            request._cache_status = "HIT"
            return cached_response
    else:
        request._cache_status = "BYPASS"

    try:
        with get_duckdb_connection() as conn:
            school_result = _find_school_by_slug(conn, slug)
            if not school_result:
                raise Http404("Colegio no encontrado")

            school = {
                "codigo": school_result[0],
                "nombre": school_result[1],
                "municipio": school_result[2],
                "departamento": school_result[3],
                "sector": school_result[4],
                "slug": slug,
                "direccion": school_result[5],
                "telefono": school_result[6],
                "email": school_result[7],
                "rector": school_result[8],
            }

            codigo = school["codigo"]

            base_url = _build_base_url(request)
            canonical_url = _absolute_url(base_url, request.path)
            og_image = _absolute_url(base_url, f"/social-card/colegio/{slug}.png")
            dept_slug = slugify(school["departamento"] or "")
            muni_slug = slugify(school["municipio"] or "")

            # Single query for all fct_colegio_historico data (latest + historical + context)
            historico_query = """
                SELECT
                    ano,
                    avg_punt_global,
                    avg_punt_matematicas,
                    avg_punt_lectura_critica,
                    avg_punt_c_naturales,
                    avg_punt_sociales_ciudadanas,
                    avg_punt_ingles,
                    total_estudiantes,
                    colegio_sk,
                    ranking_municipal,
                    total_colegios_municipio,
                    ranking_nacional,
                    percentil_sector,
                    cambio_absoluto_global,
                    cambio_porcentual_global,
                    clasificacion_tendencia,
                    sector,
                    municipio,
                    departamento
                FROM gold.fct_colegio_historico
                WHERE codigo_dane = ?
                ORDER BY CAST(ano AS INTEGER) DESC
            """
            all_rows = conn.execute(resolve_schema(historico_query), [codigo]).fetchall()

            latest_stats = all_rows[0] if all_rows else None
            # Historical: last 6 years public, reverse to ASC order
            min_year_public = int(latest_stats[0]) - 5 if latest_stats else 2019
            historical_data = [r for r in reversed(all_rows) if int(r[0]) >= min_year_public]

            latest_year = str(latest_stats[0]) if latest_stats else "2024"
            colegio_sk = latest_stats[8] if latest_stats else None
            # Context from latest row (sector=16, municipio=17, departamento=18)
            current_sector = latest_stats[16] if latest_stats else school["sector"]
            current_municipio = latest_stats[17] if latest_stats else school["municipio"]
            current_departamento = latest_stats[18] if latest_stats else school["departamento"]
            sector_slug = (
                "oficiales" if _normalize_text(current_sector) == "oficial" else "privados"
            )

            comparison_data = None
            if colegio_sk:
                comparison_query = """
                    SELECT
                        brecha_municipal_global,
                        brecha_departamental_global,
                        brecha_nacional_global,
                        promedio_municipal_global,
                        promedio_departamental_global,
                        promedio_nacional_global,
                        percentil_municipal,
                        percentil_departamental,
                        percentil_nacional,
                        clasificacion_vs_municipal,
                        clasificacion_vs_departamental,
                        clasificacion_vs_nacional,
                        brecha_municipal_lectura,
                        brecha_municipal_matematicas,
                        brecha_municipal_c_naturales,
                        brecha_municipal_sociales,
                        brecha_municipal_ingles
                    FROM gold.fct_colegio_comparacion_contexto
                    WHERE colegio_sk = ?
                      AND ano = ?
                    LIMIT 1
                """
                comparison_data = conn.execute(
                    resolve_schema(comparison_query), [colegio_sk, latest_year]
                ).fetchone()

            indicators_query = """
                SELECT
                    pct_excelencia_integral,
                    pct_competencia_satisfactoria_integral,
                    pct_riesgo_alto,
                    pct_perfil_stem_avanzado,
                    pct_perfil_humanistico_avanzado,
                    mat_pct_en_riesgo,
                    cn_pct_insuficiente,
                    lc_pct_excelencia,
                    ing_pct_b1
                FROM gold.fct_indicadores_desempeno
                WHERE colegio_bk = ?
                  AND ano = ?
                LIMIT 1
            """
            indicators_data = conn.execute(
                resolve_schema(indicators_query), [codigo, latest_year]
            ).fetchone()

            potencial_query = resolve_schema("""
                SELECT exceso, percentil_exceso, score_esperado, avg_global
                FROM gold.fct_potencial_educativo
                WHERE colegio_bk = ?
                  AND clasificacion IN ('Excepcional', 'Notable')
                LIMIT 1
            """)
            potencial_row = conn.execute(potencial_query, [codigo]).fetchone()

            # Opción D: predicción inglés 2025
            prediccion_ingles = None
            try:
                pred_row = conn.execute(resolve_schema("""
                    SELECT avg_ingles_actual, avg_ingles_predicho, cambio_predicho, tendencia
                    FROM gold.fct_prediccion_ingles
                    WHERE colegio_bk = ?
                    LIMIT 1
                """), [codigo]).fetchone()
                if pred_row:
                    prediccion_ingles = {
                        "actual": _to_float(pred_row[0]),
                        "predicho": _to_float(pred_row[1]),
                        "cambio": _to_float(pred_row[2]),
                        "tendencia": pred_row[3] or "estable",
                    }
            except Exception:
                pass

            similar_query = """
                SELECT
                    h.codigo_dane,
                    h.nombre_colegio,
                    h.municipio,
                    h.avg_punt_global,
                    COALESCE(s.slug, '') AS slug
                FROM gold.fct_colegio_historico h
                LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = h.codigo_dane
                WHERE h.ano = ?
                  AND h.codigo_dane != ?
                  AND h.municipio = ?
                  AND h.sector = ?
                  AND h.avg_punt_global IS NOT NULL
                ORDER BY ABS(h.avg_punt_global - ?)
                LIMIT 5
            """
            similar_rows = []
            if latest_stats and latest_stats[1] is not None:
                similar_rows = conn.execute(
                    resolve_schema(similar_query),
                    [
                        latest_year,
                        codigo,
                        current_municipio,
                        current_sector,
                        latest_stats[1],
                    ],
                ).fetchall()

            if len(similar_rows) < 4 and latest_stats and latest_stats[1] is not None:
                similar_dept_query = """
                    SELECT
                        h.codigo_dane,
                        h.nombre_colegio,
                        h.municipio,
                        h.avg_punt_global,
                        COALESCE(s.slug, '') AS slug
                    FROM gold.fct_colegio_historico h
                    LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = h.codigo_dane
                    WHERE h.ano = ?
                      AND h.codigo_dane != ?
                      AND h.departamento = ?
                      AND h.municipio != ?
                      AND h.sector = ?
                      AND h.avg_punt_global IS NOT NULL
                    ORDER BY ABS(h.avg_punt_global - ?)
                    LIMIT ?
                """
                needed = 5 - len(similar_rows)
                dept_rows = conn.execute(
                    resolve_schema(similar_dept_query),
                    [
                        latest_year,
                        codigo,
                        current_departamento,
                        current_municipio,
                        current_sector,
                        latest_stats[1],
                        needed,
                    ],
                ).fetchall()
                similar_rows.extend(dept_rows)

            best_muni = None
            best_dept = None
            if latest_stats and latest_stats[1] is not None:
                best_query = """
                    (SELECT 'muni' AS source,
                            h.nombre_colegio, h.avg_punt_global, h.municipio,
                            h.codigo_dane, COALESCE(s.slug, '') AS slug
                     FROM gold.fct_colegio_historico h
                     LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = h.codigo_dane
                     WHERE h.ano = ? AND h.municipio = ? AND h.sector = ?
                     ORDER BY h.avg_punt_global DESC LIMIT 1)
                    UNION ALL
                    (SELECT 'dept' AS source,
                            h.nombre_colegio, h.avg_punt_global, h.municipio,
                            h.codigo_dane, COALESCE(s.slug, '') AS slug
                     FROM gold.fct_colegio_historico h
                     LEFT JOIN gold.dim_colegios_slugs s ON s.codigo = h.codigo_dane
                     WHERE h.ano = ? AND h.departamento = ? AND h.sector = ?
                     ORDER BY h.avg_punt_global DESC LIMIT 1)
                """
                best_rows = conn.execute(
                    resolve_schema(best_query),
                    [latest_year, current_municipio, current_sector,
                     latest_year, current_departamento, current_sector],
                ).fetchall()
                for row in best_rows:
                    # row: source, nombre, score, municipio, codigo_dane, slug
                    if row[0] == "muni" and row[5]:
                        best_muni = {
                            "name": row[1],
                            "score": _to_float(row[2]),
                            "municipio": current_municipio,
                            "diff": _to_float((row[2] or 0) - (latest_stats[1] or 0)),
                            "url": _absolute_url(base_url, f"/icfes/colegio/{row[5]}/"),
                            "is_current": row[4] == codigo,
                        }
                    elif row[0] == "dept" and row[5]:
                        best_dept = {
                            "name": row[1],
                            "score": _to_float(row[2]),
                            "municipio": row[3],
                            "departamento": current_departamento,
                            "diff": _to_float((row[2] or 0) - (latest_stats[1] or 0)),
                            "url": _absolute_url(base_url, f"/icfes/colegio/{row[5]}/"),
                            "is_current": row[4] == codigo,
                        }

            has_data = latest_stats is not None
            stats_dict = None
            subject_rows = []
            top_strengths = []
            top_weaknesses = []
            radar_data = {"labels": [], "values": []}
            historical_chart = {"years": [], "scores": [], "has_data": False}
            historical_table = []
            comparison = None
            indicators = None
            indicator_badges = []
            performance_signals = {}
            action_recommendations = []
            cuadrante_slug = None
            narrative_summary = ""
            dynamic_description = []
            faq_items = []
            similar_schools = []

            if has_data:
                stats_dict = {
                    "year": latest_year,
                    "global": _to_float(latest_stats[1]),
                    "matematicas": _to_float(latest_stats[2]),
                    "lectura": _to_float(latest_stats[3]),
                    "ciencias": _to_float(latest_stats[4]),
                    "sociales": _to_float(latest_stats[5]),
                    "ingles": _to_float(latest_stats[6]),
                    "estudiantes": _to_int(latest_stats[7]) or 0,
                    "ranking_municipal": _to_int(latest_stats[9]),
                    "total_colegios_municipio": _to_int(latest_stats[10]),
                    "ranking_nacional": _to_int(latest_stats[11]),
                    "percentil_sector": _to_float(latest_stats[12]),
                    "cambio_absoluto_global": _to_float(latest_stats[13]),
                    "cambio_porcentual_global": _to_float(latest_stats[14]),
                    "clasificacion_tendencia": latest_stats[15] or "estable",
                }

                subjects = {
                    "Matemáticas": stats_dict["matematicas"],
                    "Lectura Crítica": stats_dict["lectura"],
                    "Ciencias Naturales": stats_dict["ciencias"],
                    "Sociales y Ciudadanas": stats_dict["sociales"],
                    "Inglés": stats_dict["ingles"],
                }
                valid_subjects = {k: v for k, v in subjects.items() if v is not None}
                sorted_subjects = sorted(valid_subjects.items(), key=lambda x: x[1], reverse=True)
                top_strengths = sorted_subjects[:3]
                top_weaknesses = sorted_subjects[-3:][::-1]

                subject_rows = [
                    {"name": name, "score": score}
                    for name, score in sorted_subjects
                ]

                radar_data = {
                    "labels": ["Matemáticas", "Lectura", "Ciencias", "Sociales", "Inglés"],
                    "values": [
                        stats_dict["matematicas"] or 0,
                        stats_dict["lectura"] or 0,
                        stats_dict["ciencias"] or 0,
                        stats_dict["sociales"] or 0,
                        stats_dict["ingles"] or 0,
                    ],
                }

                if historical_data:
                    years = [str(row[0]) for row in historical_data]
                    global_scores = [_to_float(row[1]) for row in historical_data]
                    historical_chart = {
                        "years": years,
                        "scores": global_scores,
                        "has_data": len(years) > 0,
                    }

                # Opción B: tabla histórica multi-materia (todos los años, primeros 5 libres)
                _FREE_TABLE_ROWS = 5
                historical_table = [
                    {
                        "year": str(row[0]),
                        "global": _to_float(row[1]),
                        "matematicas": _to_float(row[2]),
                        "lectura": _to_float(row[3]),
                        "ciencias": _to_float(row[4]),
                        "sociales": _to_float(row[5]),
                        "ingles": _to_float(row[6]),
                        "locked": i >= _FREE_TABLE_ROWS,
                    }
                    for i, row in enumerate(all_rows)
                    if row[1] is not None
                ]

                if comparison_data:
                    comparison = {
                        "brecha_municipal": _to_float(comparison_data[0]),
                        "brecha_departamental": _to_float(comparison_data[1]),
                        "brecha_nacional": _to_float(comparison_data[2]),
                        "promedio_municipal": _to_float(comparison_data[3]),
                        "promedio_departamental": _to_float(comparison_data[4]),
                        "promedio_nacional": _to_float(comparison_data[5]),
                        "percentil_municipal": _to_float(comparison_data[6]),
                        "percentil_departamental": _to_float(comparison_data[7]),
                        "percentil_nacional": _to_float(comparison_data[8]),
                        "clasificacion_municipal": comparison_data[9] or "Sin clasificar",
                        "clasificacion_departamental": comparison_data[10] or "Sin clasificar",
                        "clasificacion_nacional": comparison_data[11] or "Sin clasificar",
                        "gaps_subjects": {
                            "Lectura Crítica": _to_float(comparison_data[12]),
                            "Matemáticas": _to_float(comparison_data[13]),
                            "Ciencias Naturales": _to_float(comparison_data[14]),
                            "Sociales y Ciudadanas": _to_float(comparison_data[15]),
                            "Inglés": _to_float(comparison_data[16]),
                        },
                    }

                    for scope in ["municipal", "departamental", "nacional"]:
                        value = comparison[f"brecha_{scope}"]
                        comparison[f"brecha_{scope}_display"] = _format_signed(value, " pts")
                        comparison[f"brecha_{scope}_class"] = (
                            "positive" if value is not None and value > 0 else "negative"
                        )

                if indicators_data:
                    indicators = {
                        "excelencia_integral": _to_float(indicators_data[0]),
                        "competencia_satisfactoria": _to_float(indicators_data[1]),
                        "riesgo_alto": _to_float(indicators_data[2]),
                        "perfil_stem": _to_float(indicators_data[3]),
                        "perfil_humanistico": _to_float(indicators_data[4]),
                        "mat_riesgo": _to_float(indicators_data[5]),
                        "cn_insuficiente": _to_float(indicators_data[6]),
                        "lc_excelencia": _to_float(indicators_data[7]),
                        "ing_b1": _to_float(indicators_data[8]),
                    }

                    prev_indicators_query = """
                        SELECT
                            pct_excelencia_integral,
                            pct_competencia_satisfactoria_integral,
                            pct_perfil_stem_avanzado,
                            pct_perfil_humanistico_avanzado
                        FROM gold.fct_indicadores_desempeno
                        WHERE colegio_bk = ?
                          AND ano = ?
                        LIMIT 1
                    """
                    prev_row = conn.execute(
                        resolve_schema(prev_indicators_query), [codigo, str(int(latest_year) - 1)]
                    ).fetchone()

                    percentile_query = """
                        WITH curr AS (
                            SELECT
                                pct_excelencia_integral AS excelencia_integral,
                                pct_competencia_satisfactoria_integral AS competencia_satisfactoria,
                                pct_perfil_stem_avanzado AS perfil_stem,
                                pct_perfil_humanistico_avanzado AS perfil_humanistico
                            FROM gold.fct_indicadores_desempeno
                            WHERE colegio_bk = ?
                              AND ano = ?
                            LIMIT 1
                        ),
                        base AS (
                            SELECT
                                pct_excelencia_integral,
                                pct_competencia_satisfactoria_integral,
                                pct_perfil_stem_avanzado,
                                pct_perfil_humanistico_avanzado
                            FROM gold.fct_indicadores_desempeno
                            WHERE ano = ?
                        )
                        SELECT
                            ROUND(100.0 * SUM(CASE WHEN base.pct_excelencia_integral <= curr.excelencia_integral THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS rank_excelencia,
                            ROUND(100.0 * SUM(CASE WHEN base.pct_competencia_satisfactoria_integral <= curr.competencia_satisfactoria THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS rank_competencia,
                            ROUND(100.0 * SUM(CASE WHEN base.pct_perfil_stem_avanzado <= curr.perfil_stem THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS rank_stem,
                            ROUND(100.0 * SUM(CASE WHEN base.pct_perfil_humanistico_avanzado <= curr.perfil_humanistico THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS rank_humanistico
                        FROM base
                        CROSS JOIN curr
                    """
                    percentile_row = conn.execute(
                        resolve_schema(percentile_query), [codigo, latest_year, latest_year]
                    ).fetchone()

                    def _rank_tag(percentile):
                        if percentile is None:
                            return "Sin ranking nacional"
                        if percentile >= 95:
                            return "Top 5% nacional"
                        if percentile >= 90:
                            return "Top 10% nacional"
                        if percentile >= 80:
                            return "Top 20% nacional"
                        if percentile >= 70:
                            return "Top 30% nacional"
                        return "En desarrollo"

                    badge_defs = [
                        ("Excelencia Integral", "Nivel 4 en todas las materias", "excelencia_integral", 0, 0, "bi-trophy-fill", "#f59e0b"),
                        ("Competencia Satisfactoria", "Nivel 3+ en todas las materias", "competencia_satisfactoria", 1, 1, "bi-patch-check-fill", "#22c55e"),
                        ("Perfil STEM Avanzado", "Nivel 4 en Math & Ciencias", "perfil_stem", 2, 2, "bi-cpu-fill", "#3b82f6"),
                        ("Perfil Humanístico Avanzado", "Nivel 4 en Lectura & Sociales", "perfil_humanistico", 3, 3, "bi-book-fill", "#a855f7"),
                    ]
                    for title, subtitle, key, prev_idx, rank_idx, icon, color in badge_defs:
                        value = indicators.get(key)
                        prev_value = _to_float(prev_row[prev_idx]) if prev_row else None
                        delta = _to_float(value - prev_value) if value is not None and prev_value is not None else None
                        percentile = _to_float(percentile_row[rank_idx]) if percentile_row else None
                        indicator_badges.append(
                            {
                                "title": title,
                                "subtitle": subtitle,
                                "value": value,
                                "delta": delta,
                                "delta_display": _format_signed(delta, " pp") if delta is not None else "Sin histórico",
                                "delta_class": "positive" if delta is not None and delta >= 0 else "negative",
                                "rank_label": _rank_tag(percentile),
                                "icon": icon,
                                "color": color,
                            }
                        )

                    # Este distintivo destaca colegios que rinden por encima de lo esperado
                    # para instituciones con contexto comparable.
                    if potencial_row:
                        exceso_val = _to_float(potencial_row[0])
                        pct_val    = _to_float(potencial_row[1])
                        esp_val    = _to_float(potencial_row[2])
                        real_val   = _to_float(potencial_row[3])
                        indicator_badges.append({
                            "title":         "Superó su rendimiento esperado",
                            "subtitle":      "Obtuvo más puntos de los esperados según su contexto",
                            "value":         exceso_val,
                            "value_suffix":  " pts",
                            "delta":         None,
                            "delta_display": f"Esperado: {esp_val} · Resultado real: {real_val}",
                            "delta_class":   "positive",
                            "rank_label":    _rank_tag(pct_val) if pct_val is not None else "Top potencial",
                            "icon":          "bi-graph-up-arrow",
                            "color":         "#0891b2",
                        })

                # Cuadrante slug (para links de descubrimiento)
                if stats_dict and comparison:
                    _puntaje = stats_dict.get("global") or 0
                    _tendencia = stats_dict.get("cambio_absoluto_global") or 0
                    _prom_nac = comparison.get("promedio_nacional") or 250
                    cuadrante_slug = (
                        ("estrella" if _tendencia >= 0 else "consolidada")
                        if _puntaje >= _prom_nac
                        else ("emergente" if _tendencia >= 0 else "alerta")
                    )
                    _CUADRANTE_META = {
                        "estrella":    ("Cuadrante Estrella",    "Mejorando y sobre sus pares",        "bi-star-fill",                 "#f59e0b"),
                        "consolidada": ("Cuadrante Consolidada", "Sobre sus pares, tendencia baja",    "bi-shield-check",              "#22c55e"),
                        "emergente":   ("Cuadrante Emergente",   "Por debajo de pares pero mejorando", "bi-arrow-up-circle-fill",      "#3b82f6"),
                        "alerta":      ("Cuadrante Alerta",      "Por debajo de pares y bajando",      "bi-exclamation-triangle-fill", "#ef4444"),
                    }
                    _ct, _cs, _ci, _cc = _CUADRANTE_META[cuadrante_slug]
                    indicator_badges.append({
                        "title":         _ct,
                        "subtitle":      _cs,
                        "value":         cuadrante_slug.capitalize(),
                        "value_suffix":  " ",
                        "delta":         None,
                        "delta_display": "Clasificación de posicionamiento",
                        "delta_class":   "",
                        "rank_label":    f"Año {latest_year}",
                        "icon":          _ci,
                        "color":         _cc,
                    })

                global_history = [v for v in historical_chart["scores"] if v is not None]
                if len(global_history) >= 2:
                    trend_3y = None
                    trend_5y = None
                    if len(global_history) >= 3:
                        trend_3y = _to_float(global_history[-1] - global_history[-3])
                    if len(global_history) >= 5:
                        trend_5y = _to_float(global_history[-1] - global_history[-5])
                    stability = _to_float(statistics.pstdev(global_history), 2)
                    performance_signals = {
                        "trend_3y": trend_3y,
                        "trend_5y": trend_5y,
                        "stability_std": stability,
                    }

                if comparison and comparison.get("gaps_subjects"):
                    gap_candidates = [
                        (k, v)
                        for k, v in comparison["gaps_subjects"].items()
                        if v is not None
                    ]
                    if gap_candidates:
                        worst_gap = min(gap_candidates, key=lambda item: item[1])
                        if worst_gap[1] < 0:
                            action_recommendations.append(
                                f"Priorizar {worst_gap[0]}: cerrar {abs(worst_gap[1])} puntos frente al promedio municipal."
                            )

                # Trend-based recommendations
                if performance_signals.get("trend_3y") is not None:
                    t3 = performance_signals["trend_3y"]
                    if t3 < -10:
                        action_recommendations.append(
                            f"Alerta: caída de {abs(t3)} puntos en 3 años. Revisar cambios curriculares y rotación docente reciente."
                        )
                    elif t3 < -5:
                        action_recommendations.append(
                            f"Tendencia descendente ({abs(t3)} pts en 3 años). Considerar diagnóstico institucional para identificar causas."
                        )
                    elif t3 > 10:
                        action_recommendations.append(
                            f"Excelente progreso: +{t3} puntos en 3 años. Documentar las prácticas exitosas para replicarlas."
                        )

                # Percentile-based recommendations
                if comparison and comparison.get("percentil_nacional") is not None:
                    pn = comparison["percentil_nacional"]
                    if pn < 25:
                        action_recommendations.append(
                            "El colegio está por debajo del percentil 25 nacional. Evaluar acceso a recursos pedagógicos y formación docente."
                        )
                    elif pn > 90:
                        action_recommendations.append(
                            f"Percentil {pn} nacional: el colegio se ubica entre los mejores del país. Potenciar áreas STEM para consolidar la excelencia."
                        )

                if stats_dict.get("sociales") is not None and stats_dict["sociales"] < 50:
                    action_recommendations.append(
                        "Refuerzo en Sociales y Ciudadanas con simulacros quincenales y lectura de contexto."
                    )
                if stats_dict.get("matematicas") is not None and stats_dict["matematicas"] < 50:
                    action_recommendations.append(
                        "Enfocar Matemáticas en resolución de problemas y manejo de tiempo por bloque."
                    )
                if indicators and indicators.get("riesgo_alto") is not None and indicators["riesgo_alto"] > 20:
                    action_recommendations.append(
                        "Implementar plan de intervención temprana para estudiantes en riesgo alto."
                    )
                if not action_recommendations:
                    action_recommendations.append(
                        "Mantener la estrategia actual y consolidar seguimiento por cohortes para sostener el desempeño."
                    )

                ranking_fragment = ""
                if stats_dict.get("ranking_municipal") and stats_dict.get("total_colegios_municipio"):
                    ranking_fragment = (
                        f"ocupa la posición {stats_dict['ranking_municipal']} de "
                        f"{stats_dict['total_colegios_municipio']} en {school['municipio']}"
                    )
                else:
                    ranking_fragment = "cuenta con desempeño medible frente a su contexto local"

                percentil_fragment = ""
                if comparison and comparison.get("percentil_municipal") is not None:
                    percentil_fragment = (
                        f"y se ubica en el percentil municipal {comparison['percentil_municipal']}"
                    )

                trend_text = ""
                if performance_signals.get("trend_3y") is not None:
                    direction = "mejora" if performance_signals["trend_3y"] >= 0 else "retroceso"
                    trend_text = (
                        f" En los últimos 3 años registra {direction} de "
                        f"{abs(performance_signals['trend_3y'])} puntos."
                    )

                narrative_summary = (
                    f"{school['nombre']} en {school['municipio']}, {school['departamento']}, "
                    f"obtuvo un puntaje global de {stats_dict['global']} en {latest_year}, {ranking_fragment} "
                    f"{percentil_fragment}. {trend_text}"
                ).strip()

                sector_display = "oficial" if _normalize_text(current_sector) == "oficial" else "privado"

                dynamic_description.append(
                    f"{school['nombre']} es un colegio del sector {sector_display} ubicado en {current_municipio}, {current_departamento}. "
                    f"En {latest_year} obtuvo {stats_dict['global']} puntos globales."
                )
                if comparison and comparison.get("brecha_municipal") is not None:
                    gap = comparison["brecha_municipal"]
                    if gap >= 0:
                        dynamic_description.append(
                            f"Su resultado está {gap} puntos por encima del promedio municipal, mostrando una posición competitiva favorable en su entorno local."
                        )
                    else:
                        dynamic_description.append(
                            f"Actualmente se ubica {abs(gap)} puntos por debajo del promedio municipal, con oportunidad clara de mejora en materias clave."
                        )
                if best_muni:
                    if best_muni["is_current"]:
                        dynamic_description.append(
                            f"Es el colegio con mejor puntaje del municipio dentro de su sector."
                        )
                    else:
                        dynamic_description.append(
                            f"El líder municipal de su sector es {best_muni['name']} con {best_muni['score']} puntos."
                        )

                for row in similar_rows:
                    if not row[4]:
                        continue
                    similar_schools.append(
                        {
                            "name": row[1],
                            "score": _to_float(row[3]),
                            "url": _absolute_url(base_url, f"/icfes/colegio/{row[4]}/"),
                        }
                    )

            thin_content = (not has_data) or (stats_dict and stats_dict["estudiantes"] < 5)
            robots_meta = "noindex, follow" if thin_content else (
                "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1"
            )

            if has_data and stats_dict:
                # Build title: prefer full form with municipio; drop it if needed to avoid truncation
                _t_full = f"Resultados ICFES {latest_year}: {school['nombre']} ({school['municipio']})"
                _t_short = f"Resultados ICFES {latest_year}: {school['nombre']}"
                if len(_meta_compact(_t_full)) <= 60:
                    seo_title = _meta_compact(_t_full)
                elif len(_meta_compact(_t_short)) <= 60:
                    seo_title = _meta_compact(_t_short)
                else:
                    seo_title = _trim_meta(_t_short, 60)

                seo_description = (
                    f"Resultados ICFES {latest_year} de {school['nombre']} en {school['municipio']}, "
                    f"{school['departamento']}: puntaje global {stats_dict['global']}, ranking local, "
                    f"brechas por materia, evolución histórica y recomendaciones de mejora."
                )
            else:
                _t_full = f"Resultados ICFES: {school['nombre']} ({school['municipio']})"
                _t_short = f"Resultados ICFES: {school['nombre']}"
                if len(_meta_compact(_t_full)) <= 60:
                    seo_title = _meta_compact(_t_full)
                elif len(_meta_compact(_t_short)) <= 60:
                    seo_title = _meta_compact(_t_short)
                else:
                    seo_title = _trim_meta(_t_short, 60)

                seo_description = (
                    f"Consulta el perfil ICFES de {school['nombre']} en {school['municipio']}, "
                    f"{school['departamento']}, con comparativos territoriales y tendencias."
                )
            seo_description = _fit_meta_description(seo_description, min_len=110, max_len=155)

            if top_weaknesses:
                weakest_subjects = ", ".join(subject for subject, _ in top_weaknesses[:2])
                improvement_answer = f"Las materias con mayor oportunidad de mejora son {weakest_subjects}."
            else:
                improvement_answer = "Revisar brechas por materia y tendencia histórica."

            faq_items = [
                {
                    "question": f"¿Cuál fue el puntaje global ICFES de {school['nombre']} en {latest_year}?",
                    "answer": (
                        f"El puntaje global reportado es {stats_dict['global']}."
                        if stats_dict and stats_dict.get("global") is not None
                        else "No hay puntaje global disponible para el último corte."
                    ),
                },
                {
                    "question": f"¿Cómo se compara {school['nombre']} frente al promedio de {school['municipio']}?",
                    "answer": (
                        f"La brecha municipal global es {comparison['brecha_municipal_display']}."
                        if comparison
                        else "No hay comparación municipal disponible en este momento."
                    ),
                },
                {
                    "question": "¿Qué áreas tienen mayor oportunidad de mejora?",
                    "answer": improvement_answer,
                },
            ]

            breadcrumb_items = [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Inicio",
                    "item": _absolute_url(base_url, "/"),
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": "Colegios ICFES",
                    "item": _absolute_url(base_url, "/icfes/colegio/"),
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": school["nombre"],
                    "item": canonical_url,
                },
            ]

            today_iso = date.today().isoformat()

            schema_school = {
                "@type": "School",
                "@id": f"{canonical_url}#school",
                "name": school["nombre"],
                "description": seo_description,
                "url": canonical_url,
                "mainEntityOfPage": canonical_url,
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": school["municipio"],
                    "addressRegion": school["departamento"],
                    "addressCountry": "CO",
                },
            }
            if stats_dict and stats_dict.get("global") is not None:
                schema_school["additionalProperty"] = [
                    {
                        "@type": "PropertyValue",
                        "name": f"Puntaje global ICFES {latest_year}",
                        "value": stats_dict["global"],
                    }
                ]

            schema_article = {
                "@type": "Article",
                "@id": f"{canonical_url}#article",
                "headline": seo_title,
                "description": seo_description,
                "url": canonical_url,
                "inLanguage": "es-CO",
                "datePublished": f"{latest_year}-06-01",
                "dateModified": today_iso,
                "about": {"@id": f"{canonical_url}#school"},
                "publisher": {
                    "@type": "Organization",
                    "name": "ICFES Analytics",
                    "url": _absolute_url(base_url, "/"),
                },
            }

            schema_breadcrumb = {
                "@type": "BreadcrumbList",
                "itemListElement": breadcrumb_items,
            }

            schema_faq = {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": item["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
                    }
                    for item in faq_items
                ],
            }

            context = {
                "school": school,
                "sector_display": "Oficial" if _normalize_text(current_sector) == "oficial" else "Privado",
                "has_data": has_data,
                "stats": stats_dict,
                "top_strengths": top_strengths,
                "top_weaknesses": top_weaknesses,
                "subject_rows": subject_rows,
                "radar_data": {
                    "labels": json.dumps(radar_data["labels"], ensure_ascii=False),
                    "values": json.dumps(radar_data["values"], ensure_ascii=False),
                },
                "historical_chart": {
                    "years": json.dumps(historical_chart["years"], ensure_ascii=False),
                    "scores": json.dumps(historical_chart["scores"], ensure_ascii=False),
                    "has_data": historical_chart["has_data"],
                },
                "comparison": comparison,
                "indicators": indicators,
                "indicator_badges": indicator_badges,
                "performance_signals": performance_signals,
                "action_recommendations": action_recommendations,
                "narrative_summary": narrative_summary,
                "dynamic_description": dynamic_description,
                "faq_items": faq_items,
                "similar_schools": similar_schools,
                "best_muni": best_muni,
                "best_dept": best_dept,
                "discovery_links": {
                    "cuadrante_url": (
                        f"/icfes/cuadrante/{cuadrante_slug}/{dept_slug}/"
                        if cuadrante_slug else "/icfes/cuadrante/"
                    ),
                    "cuadrante_label": {
                        "estrella": "Estrella",
                        "consolidada": "Consolidada",
                        "emergente": "Emergente",
                        "alerta": "En Alerta",
                    }.get(cuadrante_slug, ""),
                    "cuadrante_slug": cuadrante_slug or "",
                    "potencial_url": f"/icfes/supero-prediccion/{dept_slug}/",
                    "has_potencial": potencial_row is not None,
                    "motivacional_url": f"/icfes/bandas-motivacionales/{dept_slug}/",
                },
                "internal_links": {
                    "municipio_url": _absolute_url(
                        base_url,
                        f"/icfes/departamento/{dept_slug}/municipio/{muni_slug}/",
                    ),
                    "departamento_url": _absolute_url(
                        base_url,
                        f"/icfes/departamento/{dept_slug}/",
                    ),
                    "ranking_municipal_url": _absolute_url(
                        base_url,
                        f"/icfes/departamento/{dept_slug}/municipio/{muni_slug}/",
                    ),
                    "ranking_departamental_url": _absolute_url(
                        base_url,
                        f"/icfes/departamento/{dept_slug}/",
                    ),
                    "ranking_nacional_url": _absolute_url(
                        base_url,
                        f"/icfes/ranking/colegios/{latest_year}/",
                    ),
                    "ranking_sector_nacional_url": _absolute_url(
                        base_url,
                        f"/icfes/ranking/sector/{sector_slug}/colombia/",
                    ),
                    "ranking_sector_departamental_url": _absolute_url(
                        base_url,
                        f"/icfes/ranking/sector/{sector_slug}/departamento/{dept_slug}/",
                    ),
                    "ranking_sector_municipal_url": _absolute_url(
                        base_url,
                        f"/icfes/ranking/sector/{sector_slug}/departamento/{dept_slug}/municipio/{muni_slug}/",
                    ),
                    "ranking_matematicas_url": _absolute_url(
                        base_url,
                        f"/icfes/ranking/matematicas/{latest_year}/",
                    ),
                    "mejor_municipio_url": (
                        best_muni["url"]
                        if best_muni and best_muni.get("url")
                        else _absolute_url(
                            base_url,
                            f"/icfes/departamento/{dept_slug}/municipio/{muni_slug}/",
                        )
                    ),
                },
                "seo": {
                    "year": latest_year,
                    "title": seo_title,
                    "description": seo_description,
                    "keywords": "",
                    "og_image": og_image,
                    "robots": robots_meta,
                },
                "historical_table": historical_table,
                "prediccion_ingles": prediccion_ingles,
                "canonical_url": canonical_url,
                "structured_data_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@graph": [schema_school, schema_article, schema_breadcrumb, schema_faq],
                    },
                    ensure_ascii=False,
                ),
            }

            response = render(request, "icfes_dashboard/school_landing_simple.html", context)
            if use_cache and response.status_code == 200:
                cache.set(cache_key, response, timeout=60 * 60 * 6)
                request._cache_status = "MISS"
            else:
                request._cache_status = "BYPASS"
            return response

    except Http404:
        request._cache_status = "BYPASS"
        raise
    except Exception as exc:
        request._cache_status = "BYPASS"
        logger.error("Error in school_landing_page for slug %s: %s", slug, exc)
        raise Http404("Error al cargar la informacion del colegio")
