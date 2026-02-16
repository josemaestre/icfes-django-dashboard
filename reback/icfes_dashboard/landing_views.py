"""
Views for dynamic school landing pages.
"""
import logging
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

            # Get 2024 statistics
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
                AND ano = 2024
                LIMIT 1
            """
            
            # Use context from historico table (latest available year) to avoid format mismatches
            # (e.g., NO_OFICIAL vs NO OFICIAL; Bogotá DC vs BOGOTÁ D.C.)
            current_context_query = """
                SELECT
                    sector,
                    municipio,
                    departamento,
                    avg_punt_global
                FROM gold.fct_colegio_historico
                WHERE codigo_dane = ?
                ORDER BY ano DESC
                LIMIT 1
            """
            current_context = conn.execute(resolve_schema(current_context_query), [codigo]).fetchone()
            
            # Use 2024 stats if available, otherwise just use context from latest year
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
                AND ano = 2024
                LIMIT 1
            """
            
            stats_2024 = conn.execute(resolve_schema(stats_2024_query), [codigo]).fetchone()
            
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
                    AND ano = 2024
                    LIMIT 1
                """
                try:
                    comparacion = conn.execute(resolve_schema(comparacion_query), [colegio_sk]).fetchone()
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
                        AND ano = 2024
                        LIMIT 1
                    """
                    cluster = conn.execute(resolve_schema(cluster_query), [colegio_sk]).fetchone()
                except Exception as e:
                    logger.error(f"Error fetching cluster for {colegio_sk}: {e}")
            
            # Calculate ranking (simplified - using municipal average as proxy)
            ranking_info = {
                'rank': None,
                'total': 15000,  # Approximate
                'percentile': None
            }
            
            if stats_2024 and comparacion:
                # Estimate percentile based on gap from national average
                gap = comparacion[2] if len(comparacion) > 2 else 0  # brecha_global_nacional
                if gap > 20:
                    ranking_info['percentile'] = 95
                elif gap > 10:
                    ranking_info['percentile'] = 80
                elif gap > 0:
                    ranking_info['percentile'] = 60
                elif gap > -10:
                    ranking_info['percentile'] = 40
                else:
                    ranking_info['percentile'] = 20
            
            # --- SEO ENHANCEMENTS: Similar Schools & Best in Class ---
            
            # 1. Colegios Similares
            
            # Define variables needed for queries
            current_score = float(stats_2024[1]) if stats_2024 and len(stats_2024) > 1 and stats_2024[1] is not None else 250
            current_municipio = current_context[1] if current_context and len(current_context) > 1 else school_found['municipio']
            current_departamento = current_context[2] if current_context and len(current_context) > 2 else school_found['departamento']
            current_sector = current_context[0] if current_context and len(current_context) > 0 else school_found['sector']
            
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
                    WHERE h.ano = 2024
                      AND h.sector = ?
                      AND h.municipio = ?
                      AND h.codigo_dane != ?
                    ORDER BY diff ASC
                    LIMIT 6
                """
                sim_muni = conn.execute(resolve_schema(sim_muni_query), 
                                      [current_score, current_sector, current_municipio, codigo]).fetchdf()
                
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
                        WHERE h.ano = 2024
                          AND h.sector = ?
                          AND h.departamento = ?
                          AND h.municipio != ? -- Exclude already searched municipality
                          AND h.codigo_dane != ?
                        ORDER BY diff ASC
                        LIMIT ?
                    """
                     needed = 6 - len(similar_schools)
                     sim_dept = conn.execute(resolve_schema(sim_dept_query), 
                                           [current_score, current_sector, current_departamento, 
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
                    WHERE h.ano = 2024
                      AND h.sector = ?
                      AND h.municipio = ?
                    ORDER BY h.avg_punt_global DESC
                    LIMIT 1
                """
                best_muni_res = conn.execute(resolve_schema(best_muni_query), 
                                           [current_score, current_sector, current_municipio]).fetchone()
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
                    WHERE h.ano = 2024
                      AND h.sector = ?
                      AND h.departamento = ?
                    ORDER BY h.avg_punt_global DESC
                    LIMIT 1
                """
                best_dept_res = conn.execute(resolve_schema(best_dept_query), 
                                           [current_score, current_sector, current_departamento]).fetchone()
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
            def generate_dynamic_description(school, stats, comparacion, ranking, best_muni, best_dept):
                """Generates 2 unique paragraphs based on school data for SEO."""
                if not stats:
                    return ""
                
                # Data extraction
                nombre = school['nombre_colegio']
                municipio = school['municipio']
                departamento = school['departamento']
                sector = school['sector'].lower() if school['sector'] else "desconocido"
                puntaje = float(stats[1]) if len(stats) > 1 and stats[1] is not None else 0
                
                # Determine performance level
                nivel = "promedio"
                if ranking['percentile']:
                    if ranking['percentile'] >= 90: nivel = "muy superior"
                    elif ranking['percentile'] >= 80: nivel = "superior"
                    elif ranking['percentile'] >= 60: nivel = "alto"
                    elif ranking['percentile'] <= 20: nivel = "bajo"
                
                # Determine best subject
                materias = {
                    'Matemáticas': float(stats[2]) if len(stats) > 2 and stats[2] is not None else 0,
                    'Lectura Crítica': float(stats[3]) if len(stats) > 3 and stats[3] is not None else 0,
                    'Ciencias Naturales': float(stats[4]) if len(stats) > 4 and stats[4] is not None else 0,
                    'Sociales y Ciudadanas': float(stats[5]) if len(stats) > 5 and stats[5] is not None else 0,
                    'Inglés': float(stats[6]) if len(stats) > 6 and stats[6] is not None else 0
                }
                mejor_materia = max(materias, key=materias.get)
                puntaje_mejor = materias[mejor_materia]
                
                # Context comparisons
                # comparacion[8] is promedio_municipal
                prom_muni = float(comparacion[8]) if comparacion and len(comparacion) > 8 and comparacion[8] is not None else 0
                diff_muni = puntaje - prom_muni
                
                # Paragraph 1: General Performance & Context
                parrafo1 = f"El {nombre} es una institución educativa del sector {sector} ubicada en {municipio}, {departamento}. "
                
                if diff_muni > 5:
                    parrafo1 += f"Destaca por tener un rendimiento académico {nivel}, situándose {diff_muni:.0f} puntos por encima del promedio municipal. "
                elif diff_muni < -5:
                    parrafo1 += f"Presenta oportunidades de mejora frente al promedio local, aunque mantiene un enfoque educativo importante en la comunidad. "
                else:
                    parrafo1 += f"Su desempeño académico se encuentra alineado con el promedio de las instituciones de {municipio}. "
                
                if ranking['rank']:
                     parrafo1 += f"A nivel nacional, ocupa la posición {ranking['rank']} entre más de {ranking['total']} colegios evaluados. "
                
                # Paragraph 2: Specific Strengths & Competitive Landscape
                parrafo2 = f"En el ámbito académico específico, el colegio muestra fortaleza en {mejor_materia}, alcanzando un puntaje de {puntaje_mejor:.0f}. "
                
                if best_muni and best_muni['slug'] != slug:
                     parrafo2 += f"En su contexto competitivo inmediato, se compara con líderes locales como el {best_muni['nombre']}, referente de calidad en el municipio. "
                elif best_muni and best_muni['slug'] == slug:
                     parrafo2 += f"Es actualmente el colegio con mejor desempeño del sector {sector} en {municipio}, consolidándose como la opción educativa líder de la zona. "
                     
                parrafo2 += "Este análisis se basa en los resultados oficiales de las pruebas Saber 11 del ICFES 2024, permitiendo a padres y estudiantes tomar decisiones informadas sobre la calidad educativa."
                
                return [parrafo1, parrafo2]

            dynamic_description = generate_dynamic_description(school_found, stats_2024, comparacion, ranking_info, best_muni, best_dept)

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
            meta = {
                'title': f"Análisis ICFES - {school_found['nombre_colegio']} | {school_found['municipio']}",
                'description': f"Estadísticas completas del {school_found['nombre_colegio']} en {school_found['municipio']}, {school_found['departamento']}. Ranking, tendencias históricas y comparación con promedios municipales, departamentales y nacionales.",
                'keywords': f"ICFES, {school_found['nombre_colegio']}, {school_found['municipio']}, {school_found['departamento']}, ranking colegios, pruebas saber 11",
            }
            
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
            }
            
            return render(request, 'landing/school.html', context)
        
    except Exception as e:
        logger.error(f"Error in school_landing_page for slug {slug}: {str(e)}")
        raise Http404("Error al cargar la página del colegio")
