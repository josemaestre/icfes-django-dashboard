"""
Simplified landing page view for schools
Shows basic information and 2024 statistics
"""
import duckdb
from django.shortcuts import render
from django.http import Http404
from .db_utils import get_duckdb_connection, resolve_schema
from .landing_utils import generate_school_slug
import logging

logger = logging.getLogger(__name__)


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _extract_municipio_hint(slug):
    parts = slug.split("-")
    # Last token generally matches municipality in generated slugs.
    return parts[-1] if parts else ""


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
    except duckdb.CatalogException as e:
        # Fallback when slugs table does not exist in the running DB.
        logger.warning("dim_colegios_slugs unavailable, using fallback lookup: %s", e)

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


def school_landing_page(request, slug):
    """
    Simplified landing page for a school
    Shows basic info and 2024 stats only
    """
    try:
        with get_duckdb_connection() as conn:
            school_result = _find_school_by_slug(conn, slug)
            
            if not school_result:
                raise Http404("Colegio no encontrado")
            
            # Convert to dict
            school = {
                'codigo': school_result[0],
                'nombre': school_result[1],
                'municipio': school_result[2],
                'departamento': school_result[3],
                'sector': school_result[4],
                'slug': slug,
            }
            
            codigo = school['codigo']
            
            # Get 2024 statistics - simplified query
            stats_query = """
                SELECT 
                    avg_punt_global,
                    avg_punt_matematicas,
                    avg_punt_lectura_critica,
                    avg_punt_c_naturales,
                    avg_punt_sociales_ciudadanas,
                    avg_punt_ingles,
                    total_estudiantes,
                    colegio_sk
                FROM gold.fct_colegio_historico
                WHERE codigo_dane = ?
                AND ano = '2024'
                LIMIT 1
            """
            
            stats = conn.execute(resolve_schema(stats_query), [codigo]).fetchone()
            
            # Get historical data (last 10 years)
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
                ORDER BY ano ASC
            """
            
            historical_data = conn.execute(resolve_schema(historical_query), [codigo]).fetchall()
            
            colegio_sk = stats[7] if stats else None
            comparison_data = None
            
            if colegio_sk:
                # Get comparison data with averages
                comparison_query = """
                    SELECT 
                        brecha_municipal_global,
                        brecha_departamental_global,
                        brecha_nacional_global,
                        promedio_municipal_global,
                        promedio_departamental_global,
                        promedio_nacional_global
                    FROM gold.fct_colegio_comparacion_contexto
                    WHERE colegio_sk = ?
                    AND ano = '2024'
                    LIMIT 1
                """
                
                comparison_data = conn.execute(resolve_schema(comparison_query), [colegio_sk]).fetchone()
            
            # Prepare context
            context = {
                'school': school,
                'has_data': stats is not None,
            }
            
            if stats:
                # Prepare stats dict
                stats_dict = {
                    'global': round(stats[0], 1) if stats[0] else None,
                    'matematicas': round(stats[1], 1) if stats[1] else None,
                    'lectura': round(stats[2], 1) if stats[2] else None,
                    'ciencias': round(stats[3], 1) if stats[3] else None,
                    'sociales': round(stats[4], 1) if stats[4] else None,
                    'ingles': round(stats[5], 1) if stats[5] else None,
                    'estudiantes': int(stats[6]) if stats[6] else 0,
                }
                
                context['stats'] = stats_dict
                
                # Calculate top 3 strengths and weaknesses
                subjects = {
                    'Matemáticas': stats_dict['matematicas'],
                    'Lectura Crítica': stats_dict['lectura'],
                    'Ciencias Naturales': stats_dict['ciencias'],
                    'Sociales y Ciudadanas': stats_dict['sociales'],
                    'Inglés': stats_dict['ingles'],
                }
                
                # Filter out None values and sort
                valid_subjects = {k: v for k, v in subjects.items() if v is not None}
                
                if valid_subjects:
                    sorted_subjects = sorted(valid_subjects.items(), key=lambda x: x[1], reverse=True)
                    
                    context['top_strengths'] = sorted_subjects[:3]  # Top 3
                    context['top_weaknesses'] = sorted_subjects[-3:][::-1]  # Bottom 3, reversed
                
                # Prepare data for radar chart (Chart.js format)
                context['radar_data'] = {
                    'labels': ['Matemáticas', 'Lectura', 'Ciencias', 'Sociales', 'Inglés'],
                    'values': [
                        stats_dict['matematicas'] or 0,
                        stats_dict['lectura'] or 0,
                        stats_dict['ciencias'] or 0,
                        stats_dict['sociales'] or 0,
                        stats_dict['ingles'] or 0,
                    ]
                }
                
                # Prepare historical evolution data
                if historical_data:
                    years = [row[0] for row in historical_data]
                    global_scores = [round(row[1], 1) if row[1] else None for row in historical_data]
                    
                    context['historical_chart'] = {
                        'years': years,
                        'scores': global_scores,
                        'has_data': len(years) > 0
                    }
                
                # Prepare comparison data
                if comparison_data:
                    context['comparison'] = {
                        'brecha_municipal': round(comparison_data[0], 1) if comparison_data[0] else None,
                        'brecha_departamental': round(comparison_data[1], 1) if comparison_data[1] else None,
                        'brecha_nacional': round(comparison_data[2], 1) if comparison_data[2] else None,
                        'promedio_municipal': round(comparison_data[3], 1) if comparison_data[3] else None,
                        'promedio_departamental': round(comparison_data[4], 1) if comparison_data[4] else None,
                        'promedio_nacional': round(comparison_data[5], 1) if comparison_data[5] else None,
                    }
                    
                    # Helper to format brechas logic for template (avoids HTML formatter issues)
                    for scope in ['municipal', 'departamental', 'nacional']:
                        val = context['comparison'][f'brecha_{scope}']
                        if val is not None:
                            context['comparison'][f'brecha_{scope}_display'] = f"{'+' if val > 0 else ''}{val} pts"
                            context['comparison'][f'brecha_{scope}_class'] = 'positive' if val > 0 else 'negative'
                        else:
                             context['comparison'][f'brecha_{scope}_display'] = "N/A"
                             context['comparison'][f'brecha_{scope}_class'] = 'neutral'
            
            return render(request, 'icfes_dashboard/school_landing_simple.html', context)
            
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in school_landing_page for slug {slug}: {e}")
        raise Http404("Error al cargar la información del colegio")
