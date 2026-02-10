"""
API views for enhanced user profile features.
Provides endpoints for school search and geographic data.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from icfes_dashboard.db_utils import get_duckdb_connection

logger = logging.getLogger(__name__)


@login_required
@require_GET
def search_schools(request):
    """
    Search schools by name or DANE code.
    Returns JSON with school suggestions for autocomplete.
    
    Query params:
        q: Search query (min 3 characters)
    
    Returns:
        JSON: {
            'results': [
                {
                    'code': 'DANE code',
                    'name': 'School name',
                    'department': 'Department',
                    'municipality': 'Municipality',
                    'label': 'Full display label'
                },
                ...
            ]
        }
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 3:
        return JsonResponse({'results': []})
    
    try:
        with get_duckdb_connection() as conn:
            sql = """
                SELECT DISTINCT
                    cole_codigo_dane as code,
                    cole_nombre_establecimiento as name,
                    cole_depto_ubicacion as department,
                    cole_mcpio_ubicacion as municipality
                FROM gold.dim_colegios
                WHERE cole_nombre_establecimiento ILIKE ?
                   OR CAST(cole_codigo_dane AS VARCHAR) LIKE ?
                ORDER BY cole_nombre_establecimiento
                LIMIT 20
            """
            results = conn.execute(sql, [f'%{query}%', f'%{query}%']).fetchall()
            
            schools = [
                {
                    'code': str(r[0]) if r[0] else '',
                    'name': r[1] or '',
                    'department': r[2] or '',
                    'municipality': r[3] or '',
                    'label': f"{r[1]} - {r[2]}, {r[3]}"
                }
                for r in results
            ]
            
            logger.info(f"School search: '{query}' returned {len(schools)} results")
            return JsonResponse({'results': schools})
            
    except Exception as e:
        logger.error(f"Error searching schools: {e}")
        return JsonResponse({'error': 'Error searching schools'}, status=500)


@login_required
@require_GET
def get_departments(request):
    """
    Get list of all departments in Colombia.
    
    Returns:
        JSON: {
            'departments': ['ANTIOQUIA', 'ATLANTICO', ...]
        }
    """
    try:
        with get_duckdb_connection() as conn:
            sql = """
                SELECT DISTINCT cole_depto_ubicacion as department
                FROM gold.dim_colegios
                WHERE cole_depto_ubicacion IS NOT NULL
                ORDER BY cole_depto_ubicacion
            """
            results = conn.execute(sql).fetchall()
            
            departments = [r[0] for r in results if r[0]]
            
            logger.info(f"Departments list returned: {len(departments)} departments")
            return JsonResponse({'departments': departments})
            
    except Exception as e:
        logger.error(f"Error getting departments: {e}")
        return JsonResponse({'error': 'Error getting departments'}, status=500)


@login_required
@require_GET
def get_municipalities(request):
    """
    Get list of municipalities for a given department.
    
    Query params:
        dept: Department name
    
    Returns:
        JSON: {
            'municipalities': ['MEDELLIN', 'BELLO', ...]
        }
    """
    department = request.GET.get('dept', '').strip()
    
    if not department:
        return JsonResponse({'municipalities': []})
    
    try:
        with get_duckdb_connection() as conn:
            sql = """
                SELECT DISTINCT cole_mcpio_ubicacion as municipality
                FROM gold.dim_colegios
                WHERE cole_depto_ubicacion = ?
                  AND cole_mcpio_ubicacion IS NOT NULL
                ORDER BY cole_mcpio_ubicacion
            """
            results = conn.execute(sql, [department]).fetchall()
            
            municipalities = [r[0] for r in results if r[0]]
            
            logger.info(f"Municipalities for {department}: {len(municipalities)} found")
            return JsonResponse({'municipalities': municipalities})
            
    except Exception as e:
        logger.error(f"Error getting municipalities: {e}")
        return JsonResponse({'error': 'Error getting municipalities'}, status=500)
