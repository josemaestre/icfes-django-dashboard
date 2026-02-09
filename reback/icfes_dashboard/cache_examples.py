"""
Ejemplo de cómo agregar caché a endpoints críticos.
Copiar estos ejemplos a icfes_dashboard/views.py
"""
from django.views.decorators.cache import cache_page
from django.core.cache import cache

# ============================================================================
# EJEMPLO 1: Cache de página completa (más simple)
# ============================================================================

@cache_page(60 * 60)  # 1 hora
@require_http_methods(["GET"])
def api_tendencias_nacionales(request):
    """
    Endpoint: Tendencias nacionales por año (para gráfico de líneas).
    Retorna evolución de puntajes promedio por materia.
    
    CACHED: 1 hora (datos históricos no cambian)
    """
    query = """
        SELECT 
            ano,
            AVG(avg_punt_global) as punt_global,
            AVG(avg_punt_matematicas) as punt_matematicas,
            AVG(avg_punt_c_naturales) as punt_c_naturales,
            AVG(avg_punt_lectura_critica) as punt_lectura,
            AVG(avg_punt_sociales_ciudadanas) as punt_sociales,
            AVG(avg_punt_ingles) as punt_ingles
        FROM gold.fct_agg_colegios_ano
        GROUP BY ano
        ORDER BY ano
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# EJEMPLO 2: Cache manual con key dinámica (más control)
# ============================================================================

@require_http_methods(["GET"])
def hierarchy_regions(request):
    """
    Endpoint: Regiones con estadísticas agregadas y Z-scores.
    Query params: ?ano=2024
    
    CACHED: 1 hora por año
    """
    try:
        ano = int(request.GET.get('ano', 2024))
        ano_anterior = ano - 1
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    # Intentar obtener de caché
    cache_key = f'hierarchy_regions_{ano}'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        # Cache hit - retornar inmediatamente
        return JsonResponse(cached_data, safe=False)
    
    # Cache miss - ejecutar query
    query = """
        WITH current_year AS (
            SELECT
                region,
                AVG(avg_punt_global) as punt_global,
                AVG(avg_punt_matematicas) as punt_matematicas,
                AVG(avg_punt_lectura_critica) as punt_lectura,
                AVG(avg_punt_c_naturales) as punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas) as punt_sociales,
                AVG(avg_punt_ingles) as punt_ingles,
                SUM(total_estudiantes) as total_estudiantes
            FROM gold.vw_fct_colegios_region
            WHERE ano = ? AND region IS NOT NULL
            GROUP BY region
        ),
        previous_year AS (
            SELECT
                region,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.vw_fct_colegios_region
            WHERE ano = ? AND region IS NOT NULL
            GROUP BY region
        ),
        national_stats AS (
            SELECT
                AVG(punt_global) as media_nacional,
                STDDEV(punt_global) as std_nacional
            FROM current_year
        )
        SELECT
            c.region,
            c.punt_global,
            c.punt_matematicas,
            c.punt_lectura,
            c.punt_c_naturales,
            c.punt_sociales,
            c.punt_ingles,
            ROW_NUMBER() OVER (ORDER BY c.punt_global DESC) as ranking,
            COALESCE(((c.punt_global - p.punt_global_anterior) / NULLIF(p.punt_global_anterior, 0) * 100), 0) as cambio_anual,
            COALESCE(((c.punt_global - n.media_nacional) / NULLIF(n.std_nacional, 0)), 0) as z_score,
            COALESCE(PERCENT_RANK() OVER (ORDER BY c.punt_global) * 100, 0) as percentil
        FROM current_year c
        LEFT JOIN previous_year p ON c.region = p.region
        CROSS JOIN national_stats n
        ORDER BY c.punt_global DESC
    """
    
    df = execute_query(query, params=[ano, ano_anterior])
    data = df.to_dict(orient='records')
    
    # Guardar en caché por 1 hora
    cache.set(cache_key, data, 60 * 60)
    
    return JsonResponse(data, safe=False)


# ============================================================================
# EJEMPLO 3: Cache condicional (solo para años antiguos)
# ============================================================================

@require_http_methods(["GET"])
def api_ranking_departamentos(request):
    """
    Endpoint: Ranking de departamentos para gráfico de barras.
    Query params: ?ano=2023&limit=10 (opcionales)
    
    CACHED: Solo años < 2024 (datos históricos no cambian)
    """
    try:
        ano = int(request.GET.get('ano', 2024))
        limit = int(request.GET.get('limit', 10))
        limit = min(limit, 100)  # Limitar máximo
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    # Solo cachear años antiguos (< 2024)
    should_cache = ano < 2024
    cache_key = f'ranking_departamentos_{ano}_{limit}'
    
    if should_cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            return JsonResponse(cached_data, safe=False)

    query = """
        SELECT
            departamento,
            AVG(avg_punt_global) as promedio,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes
        FROM gold.fct_agg_colegios_ano
        WHERE ano = ?
        GROUP BY departamento
        ORDER BY promedio DESC
        LIMIT ?
    """

    df = execute_query(query, params=[ano, limit])
    data = df.to_dict(orient='records')
    
    # Cachear solo si es año antiguo
    if should_cache:
        cache.set(cache_key, data, 60 * 60 * 24)  # 24 horas
    
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS PRIORITARIOS PARA CACHEAR
# ============================================================================

# Alta prioridad (datos históricos, no cambian):
# - api_tendencias_nacionales → @cache_page(60 * 60 * 24)  # 24h
# - api_distribucion_regional → @cache_page(60 * 60)  # 1h
# - hierarchy_regions → cache manual con key por año

# Media prioridad (agregados estables):
# - api_ranking_departamentos → cache condicional (solo años < 2024)
# - api_comparacion_sectores_chart → @cache_page(60 * 30)  # 30min
# - comparacion_sectores → @cache_page(60 * 30)  # 30min

# Baja prioridad (datos dinámicos):
# - colegios_destacados → No cachear (ranking puede cambiar)
# - colegio_detalle → Cache corto @cache_page(60 * 5)  # 5min
