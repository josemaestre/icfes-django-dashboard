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
            comparacion_query = """
                SELECT 
                    brecha_global_municipal,
                    brecha_global_departamental,
                    brecha_global_nacional,
                    brecha_matematicas_municipal,
                    brecha_lectura_municipal,
                    brecha_ciencias_municipal,
                    brecha_sociales_municipal,
                    brecha_ingles_municipal,
                    promedio_municipal,
                    promedio_departamental,
                    promedio_nacional
                FROM gold.fct_colegio_comparacion_contexto
                WHERE codigo_dane = ?
                AND ano = 2024
                LIMIT 1
            """
            
            comparacion = conn.execute(resolve_schema(comparacion_query), [codigo]).fetchone()
            
            # Get cluster info (if table exists)
            cluster = None
            try:
                # First get colegio_sk from codigo_dane
                sk_query = """
                    SELECT colegio_sk
                    FROM gold.fct_colegio_historico
                    WHERE codigo_dane = ?
                    LIMIT 1
                """
                sk_result = conn.execute(resolve_schema(sk_query), [codigo]).fetchone()
                
                if sk_result:
                    colegio_sk = sk_result[0]
                    
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
            except:
                pass  # Table may not exist yet
            
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
            
            # Generate AI insights
            insights = generate_ai_insights(
                dict(stats_2024._asdict()) if stats_2024 else {},
                dict(comparacion._asdict()) if comparacion else {}
            )
            
            # Prepare chart data
            chart_data = {
                'historico': {
                    'labels': historico['ano'].tolist() if not historico.empty else [],
                    'data': historico['avg_punt_global'].tolist() if not historico.empty else []
                },
                'radar': {
                    'labels': ['Matemáticas', 'Lectura', 'Ciencias', 'Sociales', 'Inglés'],
                    'data': [
                        float(stats_2024[1]) if stats_2024 and len(stats_2024) > 1 else 0,  # matematicas
                        float(stats_2024[2]) if stats_2024 and len(stats_2024) > 2 else 0,  # lectura
                        float(stats_2024[3]) if stats_2024 and len(stats_2024) > 3 else 0,  # ciencias
                        float(stats_2024[4]) if stats_2024 and len(stats_2024) > 4 else 0,  # sociales
                        float(stats_2024[5]) if stats_2024 and len(stats_2024) > 5 else 0,  # ingles
                    ]
                },
                'comparacion': {
                    'labels': ['Colegio', 'Municipal', 'Departamental', 'Nacional'],
                    'data': [
                        float(stats_2024[0]) if stats_2024 else 0,  # punt_global
                        float(comparacion[7]) if comparacion and len(comparacion) > 7 else 0,  # promedio_municipal
                        float(comparacion[8]) if comparacion and len(comparacion) > 8 else 0,  # promedio_departamental
                        float(comparacion[9]) if comparacion and len(comparacion) > 9 else 0,  # promedio_nacional
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
                'stats_2024': dict(stats_2024._asdict()) if stats_2024 else None,
                'historico': historico.to_dict('records') if not historico.empty else [],
                'comparacion': dict(comparacion._asdict()) if comparacion else None,
                'cluster': dict(cluster._asdict()) if cluster else None,
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
