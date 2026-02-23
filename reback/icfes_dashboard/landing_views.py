"""
Views for dynamic school landing pages.
"""
import logging
import hashlib
from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.http import Http404

from icfes_dashboard.db_utils import get_duckdb_connection, resolve_schema
from icfes_dashboard.landing_utils import (
    generate_school_slug,
    calculate_ranking,
    generate_ai_insights
)

logger = logging.getLogger(__name__)


@cache_page(60 * 60 * 24)  # Cache for 24 hours
def school_landing_page(request, slug):
    """
    Dynamic landing page for individual schools.
    
    URL: /colegio/<slug>/
    Example: /colegio/colegio-san-jose-bogota/
    """
    try:
        with get_duckdb_connection() as conn:
            # Find school by slug from dedicated table
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
            
            school_result = conn.execute(resolve_schema(school_query), [slug]).fetchone()
            
            if not school_result:
                raise Http404("Colegio no encontrado")
            
            # Convert to dict
            school_found = {
                'codigo': school_result[0],
                'nombre_colegio': school_result[1],
                'municipio': school_result[2],
                'departamento': school_result[3],
                'sector': school_result[4],
            }
            
            
            codigo = school_found['codigo']
            
            # Fetch colegio_sk first (needed for comparison and cluster)
            colegio_sk = None
            try:
                sk_query = """
                    SELECT colegio_sk
                    FROM gold.fct_colegio_historico
                    WHERE codigo_dane = ?
                    LIMIT 1
                """
                sk_result = conn.execute(resolve_schema(sk_query), [codigo]).fetchone()
                if sk_result:
                    colegio_sk = sk_result[0]
            except Exception as e:
                logger.error(f"Error fetching colegio_sk for {codigo}: {e}")

            # Use context from historico table (latest available year) to avoid format mismatches
            # (e.g., NO_OFICIAL vs NO OFICIAL; Bogotá DC vs BOGOTÁ D.C.)
            current_context_query = """
                SELECT
                    sector,
                    municipio,
                    departamento,
                    avg_punt_global,
                    CAST(ano AS INTEGER) AS ano
                FROM gold.fct_colegio_historico
                WHERE codigo_dane = ?
                ORDER BY ano DESC
                LIMIT 1
            """
            current_context = conn.execute(resolve_schema(current_context_query), [codigo]).fetchone()
            report_year = int(current_context[4]) if current_context and len(current_context) > 4 and current_context[4] is not None else 2024

            # Use latest available year for this school
            stats_2024_query = """
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
                AND CAST(ano AS INTEGER) = ?
                LIMIT 1
            """
            
            stats_2024 = conn.execute(resolve_schema(stats_2024_query), [codigo, report_year]).fetchone()
            
            # Get historical data (last 10 years)
            historico_query = """
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
                ORDER BY ano ASC
            """
            
            historico = conn.execute(resolve_schema(historico_query), [codigo]).fetchdf()
            
            # Get comparison data
            comparacion = None
            if colegio_sk:
                comparacion_query = """
                    SELECT 
                        brecha_municipal_global,
                        brecha_departamental_global,
                        brecha_nacional_global,
                        brecha_municipal_matematicas,
                        brecha_municipal_lectura,
                        brecha_municipal_c_naturales,
                        brecha_municipal_sociales,
                        brecha_municipal_ingles,
                        promedio_municipal_global,
                        promedio_departamental_global,
                        promedio_nacional_global,
                        promedio_municipal_matematicas,
                        promedio_municipal_lectura,
                        promedio_municipal_c_naturales,
                        promedio_municipal_sociales,
                        promedio_municipal_ingles
                    FROM gold.fct_colegio_comparacion_contexto
                    WHERE colegio_sk = ?
                    AND CAST(ano AS INTEGER) = ?
                    LIMIT 1
                """
                try:
                    comparacion = conn.execute(resolve_schema(comparacion_query), [colegio_sk, report_year]).fetchone()
                except Exception as e:
                    logger.error(f"Error fetching comparison data for {colegio_sk}: {e}")
            
            # Get cluster info (if table exists)
            cluster = None
            if colegio_sk:
                try:
                    cluster_query = """
                        SELECT 
                            cluster_id,
                            cluster_name
                        FROM gold.dim_colegios_cluster
                        WHERE colegio_sk = ?
                        AND CAST(ano AS INTEGER) = ?
                        LIMIT 1
                    """
                    cluster = conn.execute(resolve_schema(cluster_query), [colegio_sk, report_year]).fetchone()
                except Exception as e:
                    logger.error(f"Error fetching cluster for {colegio_sk}: {e}")
            
            # Calculate ranking with direct position estimates for selected year.
            ranking_info = {
                'rank': None,
                'total': 15000,  # Approximate
                'percentile': None,
                'municipal_rank': None,
                'municipal_total': None,
                'municipal_percentile': None,
            }

            # --- SEO ENHANCEMENTS: Similar Schools & Best in Class ---
            
            # 1. Colegios Similares
            
            # Define variables needed for queries
            current_score = float(stats_2024[1]) if stats_2024 and len(stats_2024) > 1 and stats_2024[1] is not None else 250
            current_municipio = current_context[1] if current_context and len(current_context) > 1 else school_found['municipio']
            current_departamento = current_context[2] if current_context and len(current_context) > 2 else school_found['departamento']
            current_sector = current_context[0] if current_context and len(current_context) > 0 else school_found['sector']

            if stats_2024:
                try:
                    national_rank_query = """
                        SELECT
                            1 + SUM(CASE WHEN avg_punt_global > ? THEN 1 ELSE 0 END) AS rank_nacional,
                            COUNT(*) AS total_nacional
                        FROM gold.fct_colegio_historico
                        WHERE CAST(ano AS INTEGER) = ?
                          AND avg_punt_global IS NOT NULL
                    """
                    national_rank_res = conn.execute(
                        resolve_schema(national_rank_query), [current_score, report_year]
                    ).fetchone()

                    if national_rank_res and national_rank_res[1]:
                        rank_nacional = int(national_rank_res[0]) if national_rank_res[0] else None
                        total_nacional = int(national_rank_res[1])
                        ranking_info['rank'] = rank_nacional
                        ranking_info['total'] = total_nacional
                        if rank_nacional and total_nacional > 0:
                            ranking_info['percentile'] = round(
                                ((total_nacional - rank_nacional + 1) / total_nacional) * 100, 1
                            )
                except Exception as e:
                    logger.error(f"Error calculating national rank for {slug}: {e}")

                try:
                    municipal_rank_query = """
                        SELECT
                            1 + SUM(CASE WHEN avg_punt_global > ? THEN 1 ELSE 0 END) AS rank_municipal,
                            COUNT(*) AS total_municipal
                        FROM gold.fct_colegio_historico
                        WHERE CAST(ano AS INTEGER) = ?
                          AND avg_punt_global IS NOT NULL
                          AND municipio = ?
                          AND sector = ?
                    """
                    municipal_rank_res = conn.execute(
                        resolve_schema(municipal_rank_query),
                        [current_score, report_year, current_municipio, current_sector],
                    ).fetchone()

                    if municipal_rank_res and municipal_rank_res[1]:
                        rank_municipal = int(municipal_rank_res[0]) if municipal_rank_res[0] else None
                        total_municipal = int(municipal_rank_res[1])
                        ranking_info['municipal_rank'] = rank_municipal
                        ranking_info['municipal_total'] = total_municipal
                        if rank_municipal and total_municipal > 0:
                            ranking_info['municipal_percentile'] = round(
                                ((total_municipal - rank_municipal + 1) / total_municipal) * 100, 1
                            )
                except Exception as e:
                    logger.error(f"Error calculating municipal rank for {slug}: {e}")
            
            similar_schools = []
            try:
                # Search in same municipality first
                sim_muni_query = """
                    SELECT 
                        s.slug,
                        h.nombre_colegio,
                        h.municipio,
                        h.avg_punt_global,
                        ABS(h.avg_punt_global - ?) as diff
                    FROM gold.fct_colegio_historico h
                    JOIN gold.dim_colegios_slugs s ON h.codigo_dane = s.codigo
                    WHERE CAST(h.ano AS INTEGER) = ?
                      AND h.sector = ?
                      AND h.municipio = ?
                      AND h.codigo_dane != ?
                    ORDER BY diff ASC
                    LIMIT 6
                """
                sim_muni = conn.execute(resolve_schema(sim_muni_query), 
                                      [current_score, report_year, current_sector, current_municipio, codigo]).fetchdf()
                
                if not sim_muni.empty:
                    similar_schools = sim_muni.to_dict('records')
                
                # If distinct comparable schools are few (< 4), look in department
                if len(similar_schools) < 4:
                     sim_dept_query = """
                        SELECT 
                            s.slug,
                            h.nombre_colegio,
                            h.municipio,
                            h.avg_punt_global,
                            ABS(h.avg_punt_global - ?) as diff
                        FROM gold.fct_colegio_historico h
                        JOIN gold.dim_colegios_slugs s ON h.codigo_dane = s.codigo
                        WHERE CAST(h.ano AS INTEGER) = ?
                          AND h.sector = ?
                          AND h.departamento = ?
                          AND h.municipio != ? -- Exclude already searched municipality
                          AND h.codigo_dane != ?
                        ORDER BY diff ASC
                        LIMIT ?
                    """
                     needed = 6 - len(similar_schools)
                     sim_dept = conn.execute(resolve_schema(sim_dept_query), 
                                           [current_score, report_year, current_sector, current_departamento, 
                                            current_municipio, codigo, needed]).fetchdf()
                     
                     if not sim_dept.empty:
                         similar_schools.extend(sim_dept.to_dict('records'))
                         
            except Exception as e:
                logger.error(f"Error fetching similar schools for {slug}: {e}")

            # 2. Best in Municipality (Same Sector)
            best_muni = None
            try:
                best_muni_query = """
                    SELECT 
                        s.slug,
                        h.nombre_colegio,
                        h.avg_punt_global,
                        (h.avg_punt_global - ?) as diff_vs_me
                    FROM gold.fct_colegio_historico h
                    JOIN gold.dim_colegios_slugs s ON h.codigo_dane = s.codigo
                    WHERE CAST(h.ano AS INTEGER) = ?
                      AND h.sector = ?
                      AND h.municipio = ?
                    ORDER BY h.avg_punt_global DESC
                    LIMIT 1
                """
                best_muni_res = conn.execute(resolve_schema(best_muni_query), 
                                           [current_score, report_year, current_sector, current_municipio]).fetchone()
                if best_muni_res:
                    best_muni = {
                        'slug': best_muni_res[0],
                        'nombre': best_muni_res[1],
                        'municipio': current_municipio,
                        'puntaje': best_muni_res[2],
                        'diff': best_muni_res[3]
                    }
            except Exception as e:
                logger.error(f"Error fetching best in municipality for {slug}: {e}")

            # 3. Best in Department (Same Sector)
            best_dept = None
            try:
                best_dept_query = """
                    SELECT 
                        s.slug,
                        h.nombre_colegio,
                        h.municipio,
                        h.avg_punt_global,
                        (h.avg_punt_global - ?) as diff_vs_me
                    FROM gold.fct_colegio_historico h
                    JOIN gold.dim_colegios_slugs s ON h.codigo_dane = s.codigo
                    WHERE CAST(h.ano AS INTEGER) = ?
                      AND h.sector = ?
                      AND h.departamento = ?
                    ORDER BY h.avg_punt_global DESC
                    LIMIT 1
                """
                best_dept_res = conn.execute(resolve_schema(best_dept_query), 
                                           [current_score, report_year, current_sector, current_departamento]).fetchone()
                if best_dept_res:
                    best_dept = {
                        'slug': best_dept_res[0],
                        'nombre': best_dept_res[1],
                        'municipio': best_dept_res[2],
                        'departamento': current_departamento,
                        'puntaje': best_dept_res[3],
                        'diff': best_dept_res[4]
                    }
            except Exception as e:
                logger.error(f"Error fetching best in department for {slug}: {e}")
            

            # --- Dynamic SEO Description Generation ---
            def generate_dynamic_description(school, stats, comparacion, ranking, best_muni, best_dept, historico_df, report_year):
                """Generates semantically diverse analysis blocks for school SEO pages."""
                if not stats:
                    return ""

                nombre = school['nombre_colegio']
                municipio = school['municipio']
                departamento = school['departamento']
                sector = school['sector'].lower() if school['sector'] else "desconocido"
                puntaje = float(stats[1]) if len(stats) > 1 and stats[1] is not None else 0

                prom_muni = float(comparacion[8]) if comparacion and len(comparacion) > 8 and comparacion[8] is not None else 0
                prom_dept = float(comparacion[9]) if comparacion and len(comparacion) > 9 and comparacion[9] is not None else 0
                prom_nac = float(comparacion[10]) if comparacion and len(comparacion) > 10 and comparacion[10] is not None else 0
                diff_muni = puntaje - prom_muni
                diff_dept = puntaje - prom_dept
                diff_nac = puntaje - prom_nac

                materias = {
                    'Matemáticas': float(stats[2]) if len(stats) > 2 and stats[2] is not None else 0,
                    'Lectura Crítica': float(stats[3]) if len(stats) > 3 and stats[3] is not None else 0,
                    'Ciencias Naturales': float(stats[4]) if len(stats) > 4 and stats[4] is not None else 0,
                    'Sociales y Ciudadanas': float(stats[5]) if len(stats) > 5 and stats[5] is not None else 0,
                    'Inglés': float(stats[6]) if len(stats) > 6 and stats[6] is not None else 0
                }
                mejor_materia = max(materias, key=materias.get)
                puntaje_mejor = materias[mejor_materia]

                historical_scores = []
                if not historico_df.empty and 'avg_punt_global' in historico_df:
                    historical_scores = [
                        float(v) for v in historico_df['avg_punt_global'].tolist() if v is not None
                    ]
                trend_delta = 0.0
                if len(historical_scores) >= 2:
                    trend_delta = historical_scores[-1] - historical_scores[0]

                def classify_performance(percentile, gap_local):
                    if percentile is not None:
                        if percentile >= 95:
                            return "élite municipal"
                        if percentile >= 80:
                            return "competitivo alto"
                        if percentile >= 60:
                            return "desempeño sólido"
                        if percentile >= 40:
                            return "desempeño medio"
                        return "rendimiento en consolidación"
                    if gap_local >= 10:
                        return "competitivo alto"
                    if gap_local >= 0:
                        return "desempeño sólido"
                    if gap_local <= -10:
                        return "rendimiento en consolidación"
                    return "desempeño medio"

                def classify_gap_label(gap_points):
                    if gap_points <= 15:
                        return "brecha leve"
                    if gap_points <= 40:
                        return "brecha moderada"
                    return "brecha amplia"

                def classify_trend(delta_points):
                    if delta_points >= 18:
                        return "mejora acelerada"
                    if delta_points >= 8:
                        return "crecimiento sostenido"
                    if delta_points >= 2:
                        return "avance gradual"
                    if delta_points <= -12:
                        return "retroceso marcado"
                    if delta_points <= -4:
                        return "estancamiento con sesgo a la baja"
                    return "trayectoria estable"

                seed_input = f"{school.get('codigo', '')}-{nombre}-{municipio}"
                seed_int = int(hashlib.md5(seed_input.encode("utf-8")).hexdigest(), 16)

                def pick(options, offset=0):
                    return options[(seed_int + offset) % len(options)]

                perf_label = classify_performance(
                    ranking.get('municipal_percentile'),
                    diff_muni,
                )
                trend_label = classify_trend(trend_delta)

                leader_gap = None
                gap_label = None
                if best_muni and best_muni.get('puntaje') is not None:
                    leader_gap = max(0.0, float(best_muni['puntaje']) - puntaje)
                    gap_label = classify_gap_label(leader_gap)

                municipal_percentile = ranking.get('municipal_percentile')
                national_percentile = ranking.get('percentile')
                municipal_rank = ranking.get('municipal_rank')
                municipal_total = ranking.get('municipal_total')

                intro_variants = [
                    f"{nombre} registra un puntaje global de {puntaje:.1f} en Saber 11 ({report_year}), dentro del sector {sector} en {municipio}, {departamento}.",
                    f"En el corte ICFES {report_year}, {nombre} alcanza {puntaje:.1f} puntos globales y se posiciona como un actor {perf_label} del sector {sector} en {municipio}.",
                    f"Con {puntaje:.1f} puntos globales en {report_year}, {nombre} presenta un perfil {perf_label} dentro del ecosistema educativo de {municipio}, {departamento}.",
                ]
                p1 = pick(intro_variants, offset=0)

                local_context = []
                if municipal_percentile is not None:
                    local_context.append(
                        f"Se ubica en el percentil {municipal_percentile:.1f} del municipio"
                    )
                if municipal_rank and municipal_total:
                    local_context.append(
                        f"(puesto {municipal_rank} de {municipal_total} en su sector)"
                    )
                if diff_muni >= 0:
                    local_context.append(f"y supera el promedio municipal por {abs(diff_muni):.1f} puntos")
                else:
                    local_context.append(f"y se encuentra {abs(diff_muni):.1f} puntos por debajo del promedio municipal")
                if local_context:
                    p1 += " " + " ".join(local_context) + "."

                p2_options = []
                if best_muni and best_muni.get('slug') == slug:
                    p2_options = [
                        f"Actualmente lidera su municipio en el sector {sector}, lo que reduce a cero la brecha frente al referente local.",
                        f"Es el líder municipal de su sector en {municipio}; su ventaja competitiva local lo convierte en punto de comparación para otros colegios.",
                    ]
                elif best_muni and leader_gap is not None:
                    p2_options = [
                        f"Frente al líder municipal ({best_muni['nombre']}), conserva una {gap_label} de {leader_gap:.1f} puntos.",
                        f"En comparación con {best_muni['nombre']}, referente del municipio, mantiene una {gap_label} de {leader_gap:.1f} puntos.",
                    ]
                if not p2_options:
                    p2_options = [
                        "No fue posible estimar una brecha robusta frente al líder municipal en este corte, pero el posicionamiento local se mantiene trazable con los promedios del contexto.",
                    ]
                p2 = pick(p2_options, offset=2)

                p3 = (
                    f"En trayectoria histórica, el colegio muestra {trend_label}"
                    f" ({trend_delta:+.1f} puntos entre su primer y último dato reciente)."
                    f" Su área más fuerte en {report_year} es {mejor_materia} con {puntaje_mejor:.1f} puntos."
                )

                national_line = ""
                if national_percentile is not None and ranking.get('rank') and ranking.get('total'):
                    national_line = (
                        f" A escala nacional se ubica en el percentil {national_percentile:.1f}, "
                        f"posición {ranking['rank']} entre {ranking['total']} colegios evaluados."
                    )

                p4 = (
                    f"Respecto al promedio departamental ({prom_dept:.1f}) y nacional ({prom_nac:.1f}), "
                    f"la institución presenta diferencias de {diff_dept:+.1f} y {diff_nac:+.1f} puntos, respectivamente."
                    f"{national_line} Este perfil facilita comparar resultados de forma contextual y no solo por puntaje absoluto."
                )

                return [p1, p2, p3, p4]

            dynamic_description = generate_dynamic_description(
                school_found,
                stats_2024,
                comparacion,
                ranking_info,
                best_muni,
                best_dept,
                historico,
                report_year,
            )

            # Prepare dictionaries for context (tuples to dicts)
            stats_dict = {}
            if stats_2024:
                stats_dict = {
                    'ano': stats_2024[0],
                    'avg_punt_global': stats_2024[1],
                    'avg_punt_matematicas': stats_2024[2],
                    'avg_punt_lectura_critica': stats_2024[3],
                    'avg_punt_c_naturales': stats_2024[4],
                    'avg_punt_sociales_ciudadanas': stats_2024[5],
                    'avg_punt_ingles': stats_2024[6],
                }
                
            comp_dict = {}
            if comparacion:
                comp_dict = {
                    'brecha_global_municipal': comparacion[0],
                    'brecha_global_departamental': comparacion[1],
                    'brecha_global_nacional': comparacion[2],
                    'brecha_matematicas_municipal': comparacion[3],
                    'brecha_lectura_municipal': comparacion[4],
                    'brecha_ciencias_municipal': comparacion[5],
                    'brecha_sociales_municipal': comparacion[6],
                    'brecha_ingles_municipal': comparacion[7],
                    'promedio_municipal': comparacion[8],
                    'promedio_departamental': comparacion[9],
                    'promedio_nacional': comparacion[10],
                }
            
            cluster_dict = {}
            if cluster:
                cluster_dict = {
                    'cluster_id': cluster[0],
                    'cluster_name': cluster[1]
                }

            # Generate AI insights
            insights = generate_ai_insights(stats_dict, comp_dict)
            
            # Prepare chart data
            chart_data = {
                'historico': {
                    'labels': historico['ano'].tolist() if not historico.empty else [],
                    'data': historico['avg_punt_global'].tolist() if not historico.empty else []
                },
                'radar': {
                    'labels': ['Matemáticas', 'Lectura', 'Ciencias', 'Sociales', 'Inglés'],
                    'data': [
                        float(stats_2024[2]) if stats_2024 and len(stats_2024) > 2 else 0,  # matematicas
                        float(stats_2024[3]) if stats_2024 and len(stats_2024) > 3 else 0,  # lectura
                        float(stats_2024[4]) if stats_2024 and len(stats_2024) > 4 else 0,  # ciencias
                        float(stats_2024[5]) if stats_2024 and len(stats_2024) > 5 else 0,  # sociales
                        float(stats_2024[6]) if stats_2024 and len(stats_2024) > 6 else 0,  # ingles
                    ]
                },
                'comparacion': {
                    'labels': ['Colegio', 'Municipal', 'Departamental', 'Nacional'],
                    'data': [
                        float(stats_2024[1]) if stats_2024 else 0,  # punt_global
                        float(comparacion[8]) if comparacion and len(comparacion) > 8 else 0,  # promedio_municipal
                        float(comparacion[9]) if comparacion and len(comparacion) > 9 else 0,  # promedio_departamental
                        float(comparacion[10]) if comparacion and len(comparacion) > 10 else 0,  # promedio_nacional
                    ]
                }
            }
            
            # SEO metadata
            score_value = float(stats_2024[1]) if stats_2024 and len(stats_2024) > 1 and stats_2024[1] is not None else None
            gap_muni = float(comparacion[0]) if comparacion and len(comparacion) > 0 and comparacion[0] is not None else None
            rank_txt = (
                f"puesto {ranking_info['rank']} de {ranking_info['total']:,}"
                if ranking_info.get('rank') and ranking_info.get('total')
                else "sin ranking nacional consolidado"
            )
            percentile_txt = (
                f"percentil nacional {ranking_info['percentile']:.1f}"
                if ranking_info.get('percentile') is not None
                else "percentil nacional no disponible"
            )
            muni_gap_txt = (
                f"{gap_muni:+.1f} vs promedio municipal"
                if gap_muni is not None
                else "comparación municipal no disponible"
            )

            meta = {
                'title': f"Análisis ICFES - {school_found['nombre_colegio']} | {school_found['municipio']}",
                'description': (
                    f"{school_found['nombre_colegio']} en {school_found['municipio']} ({school_found['departamento']}): "
                    f"puntaje global {score_value:.1f} en {report_year} ({muni_gap_txt}), {rank_txt}, {percentile_txt}. "
                    f"Consulta tendencia histórica, fortalezas por materia y comparación con colegios del mismo sector."
                    if score_value is not None
                    else (
                        f"Análisis ICFES de {school_found['nombre_colegio']} en {school_found['municipio']} "
                        f"({school_found['departamento']}): ranking, tendencia histórica y comparación contextual "
                        f"con instituciones del mismo sector."
                    )
                ),
                'keywords': f"ICFES, {school_found['nombre_colegio']}, {school_found['municipio']}, {school_found['departamento']}, ranking colegios, pruebas saber 11",
            }

            faq_items = []
            if score_value is not None:
                faq_items.append({
                    'question': f"¿Cuál fue el puntaje global de {school_found['nombre_colegio']} en ICFES {report_year}?",
                    'answer': f"El puntaje global reportado fue {score_value:.1f} puntos en el corte {report_year}.",
                })
            if gap_muni is not None:
                if gap_muni >= 0:
                    faq_items.append({
                        'question': f"¿{school_found['nombre_colegio']} está por encima del promedio municipal?",
                        'answer': (
                            f"Sí. En {report_year}, el colegio se ubicó {abs(gap_muni):.1f} puntos por encima del promedio municipal "
                            f"de {school_found['municipio']}."
                        ),
                    })
                else:
                    faq_items.append({
                        'question': f"¿{school_found['nombre_colegio']} está por debajo del promedio municipal?",
                        'answer': (
                            f"Sí. En {report_year}, el colegio se ubicó {abs(gap_muni):.1f} puntos por debajo del promedio municipal "
                            f"de {school_found['municipio']}."
                        ),
                    })
            if ranking_info.get('rank') and ranking_info.get('total'):
                faq_items.append({
                    'question': f"¿Qué posición nacional tiene {school_found['nombre_colegio']}?",
                    'answer': (
                        f"Para {report_year}, el colegio aparece en la posición {ranking_info['rank']} "
                        f"entre {ranking_info['total']:,} instituciones evaluadas a nivel nacional."
                    ),
                })
            faq_items.append({
                'question': f"¿Con qué colegios se compara {school_found['nombre_colegio']} en esta landing?",
                'answer': (
                    "La comparación se realiza con instituciones del mismo sector en el municipio y departamento, "
                    "usando resultados oficiales de Saber 11 para contexto local y nacional."
                ),
            })
            
            context = {
                'school': school_found,
                'stats_2024': stats_dict,
                'historico': historico.to_dict('records') if not historico.empty else [],
                'comparacion': comp_dict,
                'cluster': cluster_dict,
                'similar_schools': similar_schools,
                'best_muni': best_muni,
                'best_dept': best_dept,
                'dynamic_description': dynamic_description,
                'ranking': ranking_info,
                'insights': insights,
                'chart_data': chart_data,
                'meta': meta,
                'slug': slug,
                'report_year': report_year,
                'faq_items': faq_items,
            }
            
            return render(request, 'landing/school.html', context)
        
    except Exception as e:
        logger.error(f"Error in school_landing_page for slug {slug}: {str(e)}")
        raise Http404("Error al cargar la página del colegio")
