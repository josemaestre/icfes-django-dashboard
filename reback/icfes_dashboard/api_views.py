"""
API views for enhanced user profile features.
Provides endpoints for school search and geographic data.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.cache import cache
import statistics as _stats
import unicodedata

from icfes_dashboard.db_utils import (
    get_duckdb_connection,
    get_brecha_kpis,
    get_brecha_por_materia,
    get_tendencia_historica_sector,
    get_niveles_desempeno_sector,
    get_brecha_departamental,
    get_niveles_por_materia_sector,
    get_convergencia_regional,
    get_tendencia_brecha_sector,
    get_fortalezas_sector,
    get_distribucion_zscore_sector,
    get_historia_tendencia_nacional,
    get_historia_regiones,
    get_historia_brechas,
    get_historia_convergencia,
    get_historia_riesgo,
)

logger = logging.getLogger(__name__)

_BRECHA_CACHE_TTL = 60 * 60 * 2  # 2 horas

def normalize_departamento(name):
    """
    Normaliza el nombre del departamento del frontend (dim_colegios) 
    para que coincida con icfes_master_resumen.
    Retorna una lista de posibles variaciones (ej: BOGOTA y BOGOTÁ) para
    evitar pérdida de datos por inconsistencias en la base de datos.
    """
    if not name:
        return name

    raw = str(name).strip()
    original = raw.upper()
    no_accents = ''.join(
        c for c in unicodedata.normalize('NFD', original)
        if unicodedata.category(c) != 'Mn'
    )
    # Remueve puntuación para cubrir variantes como "D.C." vs "DC"
    no_punct = ''.join(ch if ch.isalnum() or ch.isspace() else ' ' for ch in no_accents)
    no_punct = ' '.join(no_punct.split())

    # Incluye variante original (con mayúsculas/minúsculas) por si la BD guarda title case.
    values = set([raw, original, no_accents, no_punct])

    # Casos especiales de alta variación
    if 'BOGOTA' in no_punct:
        values.update([
            'BOGOTA', 'BOGOTÁ',
            'BOGOTA D.C.', 'BOGOTÁ D.C.',
            'BOGOTA DC', 'BOGOTÁ DC',
        ])
    if 'VALLE DEL CAUCA' in no_punct:
        values.update(['VALLE', 'VALLE DEL CAUCA'])
    if 'NORTE DE SANTANDER' in no_punct:
        values.update(['NORTE DE SANTANDER', 'NORTE SANTANDER'])
    if 'SAN ANDRES' in no_punct:
        values.update([
            'SAN ANDRES',
            'SAN ANDRES PROVIDENCIA Y SANTA CATALINA',
            'ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA',
        ])
    if 'NARINO' in no_punct:
        values.update(['NARIÑO', 'NARINO'])

    # Lista ordenada para estabilidad de caché
    return sorted(values)

def _cached(key, timeout, func):
    """Helper method para cachear resultados de bd."""
    data = cache.get(key)
    if data is None:
        data = func()
        cache.set(key, data, timeout)
    return data

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
                    colegio_bk as code,
                    nombre_colegio as name,
                    departamento as department,
                    municipio as municipality
                FROM gold.dim_colegios
                WHERE nombre_colegio ILIKE ?
                   OR CAST(colegio_bk AS VARCHAR) LIKE ?
                ORDER BY nombre_colegio
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
                SELECT DISTINCT departamento as department
                FROM gold.dim_colegios
                WHERE departamento IS NOT NULL
                ORDER BY departamento
            """
            results = conn.execute(sql).fetchall()
            
            departments = [r[0] for r in results if r[0]]
            
            logger.info(f"Departments list returned: {len(departments)} departments")
            return JsonResponse({'departments': departments})
            
    except Exception as e:
        logger.error(f"Error getting departments: {e}")
        return JsonResponse({'error': 'Error getting departments'}, status=500)


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
                SELECT DISTINCT municipio as municipality
                FROM gold.dim_colegios
                WHERE departamento = ?
                  AND municipio IS NOT NULL
                ORDER BY municipio
            """
            results = conn.execute(sql, [department]).fetchall()
            
            municipalities = [r[0] for r in results if r[0]]
            
            logger.info(f"Municipalities for {department}: {len(municipalities)} found")
            return JsonResponse({'municipalities': municipalities})
            
    except Exception as e:
        logger.error(f"Error getting municipalities: {e}")
        return JsonResponse({'error': 'Error getting municipalities'}, status=500)


# =============================================================================
# BRECHA EDUCATIVA API ENDPOINTS
# =============================================================================

import statistics as _stats
from django.core.cache import cache as _cache
from icfes_dashboard.db_utils import (
    get_brecha_kpis, get_brecha_por_materia, get_tendencia_historica_sector,
    get_niveles_desempeno_sector, get_brecha_departamental, get_anos_disponibles,
    get_convergencia_regional, get_tendencia_brecha_sector,
    get_fortalezas_sector, get_distribucion_zscore_sector,
)

# TTL para caché de consultas analíticas (datos históricos, cambian poco)
_BRECHA_CACHE_TTL = 60 * 30   # 30 minutos


def _cached(key, ttl, fn):
    """Helper: retorna caché si existe, si no ejecuta fn(), guarda y retorna."""
    result = _cache.get(key)
    if result is None:
        result = fn()
        _cache.set(key, result, ttl)
    return result


@require_GET
def brecha_kpis(request):
    """KPI cards: puntajes promedio y brecha entre sectores."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_kpis_{departamento_orig or "nacional"}_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_brecha_kpis(ano=ano, departamento=departamento_list))
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"brecha_kpis error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_por_materia(request):
    """Puntajes por materia separados por sector."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_por_materia_{departamento_orig or "nacional"}_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_brecha_por_materia(ano=ano, departamento=departamento_list))
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"brecha_por_materia error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_tendencia_historica(request):
    """Tendencia histórica de puntaje global por sector."""
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    ano = request.GET.get('ano')
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)
            
    try:
        cache_key = f'brecha_tendencia_{departamento_orig or "nacional"}_{ano}'
        def _fetch():
            return {'data': get_tendencia_historica_sector(departamento=departamento_list, ano=ano),
                    'anos': get_anos_disponibles()}
        payload = _cached(cache_key, _BRECHA_CACHE_TTL, _fetch)
        return JsonResponse(payload)
    except Exception as e:
        logger.error(f"brecha_tendencia_historica error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_niveles_desempeno(request):
    """Distribución de niveles de desempeño por sector."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_niveles_desempeno_{departamento_orig or "nacional"}_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_niveles_desempeno_sector(ano=ano, departamento=departamento_list))
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"brecha_niveles_desempeno error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_departamental(request):
    """Brecha oficial/no oficial por departamento, con z-score."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_departamental_{departamento_orig or "nacional"}_{ano}'

        def _fetch():
            data = get_brecha_departamental(ano=ano, departamento=departamento_list)
            # ── Z-score de la brecha departamental ──
            brechas_validas = [d['brecha'] for d in data if d.get('brecha') is not None]
            media = None
            if len(brechas_validas) >= 2:
                media = _stats.mean(brechas_validas)
                sigma = _stats.stdev(brechas_validas)
                for d in data:
                    if d.get('brecha') is not None and sigma > 0:
                        d['z_score'] = round((d['brecha'] - media) / sigma, 2)
                    else:
                        d['z_score'] = None
            else:
                for d in data:
                    d['z_score'] = None
            return {'data': data, 'meta': {'media_brecha': round(media, 2) if media is not None else None}}

        payload = _cached(cache_key, _BRECHA_CACHE_TTL, _fetch)
        return JsonResponse(payload)
    except Exception as e:
        logger.error(f"brecha_departamental error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_niveles_por_materia(request):
    """Distribución de niveles de desempeño (A/S/M/I) por materia y sector."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_niveles_por_materia_{departamento_orig or "nacional"}_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_niveles_por_materia_sector(ano=ano, departamento=departamento_list))
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"brecha_niveles_por_materia error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_convergencia_regional(request):
    """Brecha y estado de convergencia entre regiones geográficas."""
    ano = request.GET.get('ano')
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_convergencia_regional_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_convergencia_regional(ano=ano))
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"brecha_convergencia_regional error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_tendencia_brecha_sector(request):
    """Evolución histórica de la brecha absoluta entre sector público y privado."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_tendencia_brecha_sector_{departamento_orig or "nacional"}_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_tendencia_brecha_sector(ano=ano, departamento=departamento_list))
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"brecha_tendencia_brecha_sector error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_area_fortalezas(request):
    """Distribución de mejor y peor área académica por sector."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_area_fortalezas_{departamento_orig or "nacional"}_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_fortalezas_sector(ano=ano, departamento=departamento_list))
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"brecha_area_fortalezas error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def brecha_zscore_distribucion(request):
    """Distribución de z-scores de puntaje global por sector (buckets)."""
    ano = request.GET.get('ano')
    departamento_orig = request.GET.get('departamento', '').strip() or None
    departamento_list = normalize_departamento(departamento_orig) if departamento_orig else None
    if ano:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'ano inválido'}, status=400)

    try:
        cache_key = f'brecha_zscore_distribucion_{departamento_orig or "nacional"}_{ano}'
        data = _cached(cache_key, _BRECHA_CACHE_TTL, lambda: get_distribucion_zscore_sector(ano=ano, departamento=departamento_list))
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"brecha_zscore_distribucion error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# HISTORIA DE LA EDUCACIÓN - Story API Endpoints
# ============================================================================

_HISTORIA_CACHE_TTL = 60 * 60 * 6  # 6 horas (datos históricos raramente cambian)


@require_GET
def historia_tendencia_nacional(request):
    """Serie anual nacional 2000-2024: promedio, estudiantes, colegios."""
    try:
        data = _cached('historia_tendencia_nacional', _HISTORIA_CACHE_TTL,
                       get_historia_tendencia_nacional)
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"historia_tendencia_nacional error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def historia_regiones(request):
    """Scores y tendencias por región (año más reciente)."""
    try:
        data = _cached('historia_regiones', _HISTORIA_CACHE_TTL,
                       get_historia_regiones)
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"historia_regiones error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def historia_brechas(request):
    """Evolución histórica de brechas urbano/rural y regional."""
    try:
        data = _cached('historia_brechas', _HISTORIA_CACHE_TTL,
                       get_historia_brechas)
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"historia_brechas error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def historia_convergencia(request):
    """Convergencia/divergencia regional año a año."""
    try:
        data = _cached('historia_convergencia', _HISTORIA_CACHE_TTL,
                       get_historia_convergencia)
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"historia_convergencia error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def historia_riesgo(request):
    """Distribución de riesgo de declive para el año más reciente."""
    try:
        data = _cached('historia_riesgo', _HISTORIA_CACHE_TTL,
                       get_historia_riesgo)
        return JsonResponse({'data': data})
    except Exception as e:
        logger.error(f"historia_riesgo error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
