"""Simplified but SEO-rich landing page view for schools."""

import json
import logging
import statistics
from datetime import date
from urllib.parse import urljoin

import duckdb
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.utils.text import slugify
from django.views.decorators.cache import cache_page

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
            codigo,
            nombre_colegio,
            municipio,
            departamento,
            sector
        FROM gold.dim_colegios_slugs
        WHERE slug = ?
        LIMIT 1
    """

    try:
        school_result = conn.execute(resolve_schema(school_query), [slug]).fetchone()
        if school_result:
            return school_result
    except duckdb.CatalogException as exc:
        logger.warning("dim_colegios_slugs unavailable, using fallback lookup: %s", exc)

    municipio_hint = _extract_municipio_hint(slug)
    fallback_query = """
        SELECT DISTINCT
            codigo_dane AS codigo,
            nombre_colegio,
            municipio,
            departamento,
            sector
        FROM gold.fct_colegio_historico
        WHERE codigo_dane IS NOT NULL
          AND nombre_colegio IS NOT NULL
          AND municipio IS NOT NULL
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


@cache_page(60 * 60 * 4)
def school_landing_page(request, slug):
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
            }

            codigo = school["codigo"]
            base_url = _build_base_url(request)
            canonical_url = _absolute_url(base_url, request.path)
            og_image = _absolute_url(base_url, static("images/screenshots/dashboard_main.png"))
            dept_slug = slugify(school["departamento"] or "")
            muni_slug = slugify(school["municipio"] or "")

            latest_query = """
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
                    clasificacion_tendencia
                FROM gold.fct_colegio_historico
                WHERE codigo_dane = ?
                ORDER BY CAST(ano AS INTEGER) DESC
                LIMIT 1
            """
            latest_stats = conn.execute(resolve_schema(latest_query), [codigo]).fetchone()

            historical_query = """
                SELECT
                    ano,
                    avg_punt_global,
                    avg_punt_matematicas,
                    avg_punt_lectura_critica,
                    avg_punt_c_naturales,
                    avg_punt_sociales_ciudadanas,
                    avg_punt_ingles
                FROM gold.fct_colegio_historico
                WHERE codigo_dane = ?
                  AND CAST(ano AS INTEGER) >= 2015
                ORDER BY CAST(ano AS INTEGER) ASC
            """
            historical_data = conn.execute(resolve_schema(historical_query), [codigo]).fetchall()

            latest_year = str(latest_stats[0]) if latest_stats else "2024"
            colegio_sk = latest_stats[8] if latest_stats else None

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
                        school["municipio"],
                        school["sector"],
                        latest_stats[1],
                    ],
                ).fetchall()

            has_data = latest_stats is not None
            stats_dict = None
            subject_rows = []
            top_strengths = []
            top_weaknesses = []
            radar_data = {"labels": [], "values": []}
            historical_chart = {"years": [], "scores": [], "has_data": False}
            comparison = None
            indicators = None
            performance_signals = {}
            action_recommendations = []
            narrative_summary = ""
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
                # Compact title: ~60 chars for better SERP CTR
                title_extras = []
                if stats_dict.get("global") is not None:
                    title_extras.append(str(stats_dict["global"]))
                if stats_dict.get("ranking_municipal"):
                    title_extras.append(f"#{stats_dict['ranking_municipal']}")
                if comparison and comparison.get("percentil_municipal") is not None:
                    title_extras.append(f"P{comparison['percentil_municipal']}")
                extras_str = " | ".join(title_extras)
                seo_title = (
                    f"{school['nombre']} ({school['municipio']}) — ICFES {latest_year}: {extras_str}"
                )

                seo_description = (
                    f"Resultados ICFES {latest_year} de {school['nombre']} en {school['municipio']}, "
                    f"{school['departamento']}: puntaje global {stats_dict['global']}, ranking local, "
                    f"brechas por materia, evolución histórica y recomendaciones de mejora."
                )
            else:
                seo_title = f"{school['nombre']} ({school['municipio']}) — ICFES Analytics"
                seo_description = (
                    f"Consulta el perfil ICFES de {school['nombre']} en {school['municipio']}, "
                    f"{school['departamento']}, con comparativos territoriales y tendencias."
                )

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
                    "answer": action_recommendations[0] if action_recommendations else "Revisar brechas por materia y tendencia histórica.",
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
                "performance_signals": performance_signals,
                "action_recommendations": action_recommendations,
                "narrative_summary": narrative_summary,
                "faq_items": faq_items,
                "similar_schools": similar_schools,
                "internal_links": {
                    "municipio_url": _absolute_url(
                        base_url,
                        f"/icfes/departamento/{dept_slug}/municipio/{muni_slug}/",
                    ),
                    "departamento_url": _absolute_url(
                        base_url,
                        f"/icfes/departamento/{dept_slug}/",
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
                "canonical_url": canonical_url,
                "structured_data_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@graph": [schema_school, schema_article, schema_breadcrumb, schema_faq],
                    },
                    ensure_ascii=False,
                ),
            }

            return render(request, "icfes_dashboard/school_landing_simple.html", context)

    except Http404:
        raise
    except Exception as exc:
        logger.error("Error in school_landing_page for slug %s: %s", slug, exc)
        raise Http404("Error al cargar la informacion del colegio")
