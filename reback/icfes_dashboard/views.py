"""
Vistas para el dashboard ICFES.
Conecta con la base de datos DuckDB del proyecto dbt.
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .db_utils import (
    execute_query,
    get_table_data,
    get_anos_disponibles,
    get_departamentos,
    get_estadisticas_generales
)


# ============================================================================
# VISTAS PRINCIPALES
# ============================================================================

def icfes_dashboard(request):
    """Vista principal del dashboard ICFES."""
    context = {
        'anos_disponibles': get_anos_disponibles(),
        'departamentos': get_departamentos(),
    }
    return render(request, 'icfes_dashboard/pages/dashboard-icfes.html', context)


def dashboard_charts(request):
    """Vista del dashboard con gráficos interactivos."""
    context = {
        'anos_disponibles': get_anos_disponibles(),
        'ano_actual': 2023,
    }
    return render(request, 'icfes_dashboard/pages/dashboard-icfes-charts.html', context)


# ============================================================================
# ENDPOINTS API - DATOS GENERALES
# ============================================================================

@require_http_methods(["GET"])
def icfes_estadisticas_generales(request):
    """
    Endpoint: Estadísticas generales del sistema.
    Query params: ?ano=2023 (opcional)
    """
    ano = request.GET.get('ano')
    ano = int(ano) if ano else None
    
    stats = get_estadisticas_generales(ano)
    return JsonResponse(stats, safe=False)


@require_http_methods(["GET"])
def icfes_anos_disponibles(request):
    """Endpoint: Lista de años disponibles."""
    anos = get_anos_disponibles()
    return JsonResponse({'anos': anos})


# ============================================================================
# ENDPOINTS API - TENDENCIAS REGIONALES
# ============================================================================

@require_http_methods(["GET"])
def tendencias_regionales(request):
    """
    Endpoint: Tendencias regionales por año.
    Query params: ?ano=2023&region=ANDINA (opcionales)
    """
    ano = request.GET.get('ano')
    region = request.GET.get('region')
    
    filters = {}
    if ano:
        filters['ano'] = int(ano)
    if region:
        filters['region'] = region
    
    df = get_table_data(
        'gold.tendencias_regionales',
        filters=filters,
        order_by=['ano DESC', 'region']
    )
    
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS API - COLEGIOS
# ============================================================================

@require_http_methods(["GET"])
def colegios_agregados(request):
    """
    Endpoint: Datos agregados de colegios por año.
    Query params: ?ano=2023&departamento=CUNDINAMARCA&sector=OFICIAL (opcionales)
    """
    ano = request.GET.get('ano')
    departamento = request.GET.get('departamento')
    sector = request.GET.get('sector')
    limit = request.GET.get('limit', 100)
    
    filters = {}
    if ano:
        filters['ano'] = int(ano)
    if departamento:
        filters['departamento'] = departamento
    if sector:
        filters['sector'] = sector
    
    df = get_table_data(
        'gold.fct_agg_colegios_ano',
        filters=filters,
        limit=int(limit),
        order_by=['ano DESC', 'avg_punt_global DESC']
    )
    
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def colegios_destacados(request):
    """
    Endpoint: Top colegios destacados.
    Query params: ?ano=2023&limit=50 (opcionales)
    Genera el ranking dinámicamente desde fct_agg_colegios_ano
    """
    ano = request.GET.get('ano', 2023)
    limit = request.GET.get('limit', 50)
    
    # Generar ranking dinámicamente desde fct_agg_colegios_ano
    # Agrupar por colegio_sk para evitar duplicados con variaciones de nombre
    query = f"""
        WITH ranked_colegios AS (
            SELECT 
                colegio_sk,
                MIN(nombre_colegio) as nombre_colegio,
                MIN(departamento) as departamento,
                MIN(municipio) as municipio,
                MIN(sector) as sector,
                AVG(avg_punt_global) as avg_punt_global,
                SUM(total_estudiantes) as total_estudiantes,
                MIN(ranking_nacional) as ranking_nacional
            FROM gold.fct_agg_colegios_ano
            WHERE ano = {ano}
                AND ranking_nacional IS NOT NULL
                AND total_estudiantes >= 10
            GROUP BY colegio_sk
        )
        SELECT 
            colegio_sk,
            nombre_colegio,
            departamento,
            municipio,
            sector,
            avg_punt_global,
            total_estudiantes,
            ranking_nacional
        FROM ranked_colegios
        ORDER BY ranking_nacional
        LIMIT {limit}
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def colegio_detalle(request, colegio_sk):
    """
    Endpoint: Detalle histórico de un colegio específico.
    """
    query = f"""
        SELECT 
            ano,
            nombre_colegio,
            departamento,
            municipio,
            sector,
            total_estudiantes,
            avg_punt_global,
            median_punt_global,
            avg_punt_matematicas,
            avg_punt_c_naturales,
            avg_punt_lectura_critica,
            avg_punt_sociales_ciudadanas,
            avg_punt_ingles,
            ranking_nacional,
            ranking_departamental_general,
            gap_municipio_promedio,
            rendimiento_relativo_municipal
        FROM gold.fct_agg_colegios_ano
        WHERE colegio_sk = {colegio_sk}
        ORDER BY ano DESC
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS API - BRECHAS EDUCATIVAS
# ============================================================================

@require_http_methods(["GET"])
def brechas_educativas(request):
    """
    Endpoint: Análisis de brechas educativas por departamento.
    Query params: ?ano=2023&departamento=CUNDINAMARCA (opcionales)
    """
    ano = request.GET.get('ano')
    departamento = request.GET.get('departamento')
    
    filters = {}
    if ano:
        filters['ano'] = int(ano)
    if departamento:
        filters['departamento'] = departamento
    
    df = get_table_data(
        'gold.brechas_educativas',
        filters=filters,
        order_by=['ano DESC', 'brecha_absoluta DESC']
    )
    
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS API - ANÁLISIS COMPARATIVOS
# ============================================================================

@require_http_methods(["GET"])
def comparacion_sectores(request):
    """
    Endpoint: Comparación entre sector oficial y no oficial.
    Query params: ?ano=2023 (opcional)
    """
    ano = request.GET.get('ano', 2023)
    
    query = f"""
        SELECT 
            sector,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes,
            AVG(avg_punt_global) as promedio_punt_global,
            AVG(avg_punt_matematicas) as promedio_matematicas,
            AVG(avg_punt_c_naturales) as promedio_c_naturales,
            AVG(avg_punt_lectura_critica) as promedio_lectura,
            AVG(avg_punt_sociales_ciudadanas) as promedio_sociales,
            AVG(avg_punt_ingles) as promedio_ingles
        FROM gold.fct_agg_colegios_ano
        WHERE ano = {ano}
        GROUP BY sector
        ORDER BY sector
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def ranking_departamental(request):
    """
    Endpoint: Ranking de departamentos por promedio.
    Query params: ?ano=2023 (opcional)
    """
    ano = request.GET.get('ano', 2023)
    
    query = f"""
        SELECT 
            departamento,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes,
            AVG(avg_punt_global) as promedio_departamental,
            STDDEV(avg_punt_global) as desviacion_estandar,
            MIN(avg_punt_global) as puntaje_minimo,
            MAX(avg_punt_global) as puntaje_maximo
        FROM gold.fct_agg_colegios_ano
        WHERE ano = {ano}
        GROUP BY departamento
        ORDER BY promedio_departamental DESC
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS LEGACY (mantener compatibilidad)
# ============================================================================

@require_http_methods(["GET"])
def icfes_data(request):
    """
    Endpoint legacy: Datos básicos por departamento.
    Mantiene compatibilidad con versión anterior.
    """
    ano = request.GET.get('ano', 2023)
    
    query = f"""
        SELECT 
            departamento as depto,
            AVG(avg_punt_global) as promedio_global,
            SUM(total_estudiantes) as total_estudiantes
        FROM gold.fct_agg_colegios_ano
        WHERE ano = {ano}
        GROUP BY departamento
        ORDER BY promedio_global DESC
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def icfes_resumen(request):
    """
    Endpoint legacy: Resumen general.
    Mantiene compatibilidad con versión anterior.
    """
    query = """
        SELECT 
            ano,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes,
            AVG(avg_punt_global) as promedio_nacional,
            AVG(avg_punt_matematicas) as promedio_matematicas,
            AVG(avg_punt_c_naturales) as promedio_c_naturales,
            AVG(avg_punt_lectura_critica) as promedio_lectura,
            AVG(avg_punt_sociales_ciudadanas) as promedio_sociales,
            AVG(avg_punt_ingles) as promedio_ingles
        FROM gold.fct_agg_colegios_ano
        GROUP BY ano
        ORDER BY ano DESC
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS API - CHARTS DATA
# ============================================================================

@require_http_methods(["GET"])
def api_tendencias_nacionales(request):
    """
    Endpoint: Tendencias nacionales por año (para gráfico de líneas).
    Retorna evolución de puntajes promedio por materia.
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


@require_http_methods(["GET"])
def api_comparacion_sectores_chart(request):
    """
    Endpoint: Comparación de sectores para gráfico de barras.
    Query params: ?ano=2023 (opcional)
    """
    ano = request.GET.get('ano', 2023)
    
    query = f"""
        SELECT 
            sector,
            AVG(avg_punt_global) as punt_global,
            AVG(avg_punt_matematicas) as punt_matematicas,
            AVG(avg_punt_c_naturales) as punt_c_naturales,
            AVG(avg_punt_lectura_critica) as punt_lectura,
            AVG(avg_punt_sociales_ciudadanas) as punt_sociales,
            AVG(avg_punt_ingles) as punt_ingles,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes
        FROM gold.fct_agg_colegios_ano
        WHERE ano = {ano}
        GROUP BY sector
        ORDER BY sector
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def api_ranking_departamentos(request):
    """
    Endpoint: Ranking de departamentos para gráfico de barras.
    Query params: ?ano=2023&limit=10 (opcionales)
    """
    ano = request.GET.get('ano', 2023)
    limit = request.GET.get('limit', 10)
    
    query = f"""
        SELECT 
            departamento,
            AVG(avg_punt_global) as promedio,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes
        FROM gold.fct_agg_colegios_ano
        WHERE ano = {ano}
        GROUP BY departamento
        ORDER BY promedio DESC
        LIMIT {limit}
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def api_distribucion_regional(request):
    """
    Endpoint: Distribución de estudiantes por región.
    Query params: ?ano=2023 (opcional)
    """
    ano = request.GET.get('ano', 2023)
    
    query = f"""
        SELECT 
            region,
            SUM(total_estudiantes) as total_estudiantes,
            AVG(avg_punt_global) as promedio
        FROM gold.vw_fct_colegios_region
        WHERE ano = {ano} AND region IS NOT NULL
        GROUP BY region
        ORDER BY total_estudiantes DESC
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS API - HIERARCHICAL EXPLORER
# ============================================================================

@require_http_methods(["GET"])
def hierarchy_regions(request):
    """
    Endpoint: Regiones con estadísticas agregadas y Z-scores.
    Query params: ?ano=2024
    """
    ano = int(request.GET.get('ano', 2024))
    ano_anterior = int(ano) - 1
    
    query = f"""
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
            WHERE ano = {ano} AND region IS NOT NULL
            GROUP BY region
        ),
        previous_year AS (
            SELECT 
                region,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.vw_fct_colegios_region
            WHERE ano = {ano_anterior} AND region IS NOT NULL
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
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def hierarchy_departments(request):
    """
    Endpoint: Departamentos de una región con estadísticas y Z-scores.
    Query params: ?region=ANDINA&ano=2024
    """
    region = request.GET.get('region', '')
    ano = request.GET.get('ano', 2024)
    ano_anterior = int(ano) - 1
    
    # Obtener departamentos de la región desde la base de datos
    query_deptos = f"""
        SELECT DISTINCT departamento
        FROM gold.dim_colegios
        WHERE region = '{region}'
        ORDER BY departamento
    """
    deptos_df = execute_query(query_deptos)
    deptos = tuple(deptos_df['departamento'].tolist()) if not deptos_df.empty else ()
    
    if not deptos:
        return JsonResponse([], safe=False)
    
    if not region:
        return JsonResponse([], safe=False)
    
    query = f"""
        WITH current_year AS (
            SELECT 
                departamento,
                AVG(avg_punt_global) as punt_global,
                AVG(avg_punt_matematicas) as punt_matematicas,
                AVG(avg_punt_lectura_critica) as punt_lectura,
                AVG(avg_punt_c_naturales) as punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas) as punt_sociales,
                AVG(avg_punt_ingles) as punt_ingles,
                SUM(total_estudiantes) as total_estudiantes
            FROM gold.vw_fct_colegios_region
            WHERE ano = {ano} AND region = '{region}'
            GROUP BY departamento
        ),
        previous_year AS (
            SELECT 
                departamento,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.vw_fct_colegios_region
            WHERE ano = {ano_anterior} AND region = '{region}'
            GROUP BY departamento
        ),
        regional_stats AS (
            SELECT 
                AVG(punt_global) as media_regional,
                STDDEV(punt_global) as std_regional
            FROM current_year
        )
        SELECT 
            c.departamento as id,
            c.departamento as nombre,
            c.punt_global,
            c.punt_matematicas,
            c.punt_lectura,
            c.punt_c_naturales,
            c.punt_sociales,
            c.punt_ingles,
            ROW_NUMBER() OVER (ORDER BY c.punt_global DESC) as ranking,
            COALESCE(((c.punt_global - p.punt_global_anterior) / NULLIF(p.punt_global_anterior, 0) * 100), 0) as cambio_anual,
            COALESCE(((c.punt_global - r.media_regional) / NULLIF(r.std_regional, 0)), 0) as z_score,
            COALESCE(PERCENT_RANK() OVER (ORDER BY c.punt_global) * 100, 0) as percentil
        FROM current_year c
        LEFT JOIN previous_year p ON c.departamento = p.departamento
        CROSS JOIN regional_stats r
        ORDER BY c.punt_global DESC
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def hierarchy_municipalities(request):
    """
    Endpoint: Municipios de un departamento con estadísticas y Z-scores.
    Query params: ?department=CUNDINAMARCA&ano=2024
    """
    department = request.GET.get('department', '')
    ano = request.GET.get('ano', 2024)
    ano_anterior = int(ano) - 1
    
    if not department:
        return JsonResponse([], safe=False)
    
    query = f"""
        WITH current_year AS (
            SELECT 
                municipio,
                AVG(avg_punt_global) as punt_global,
                AVG(avg_punt_matematicas) as punt_matematicas,
                AVG(avg_punt_lectura_critica) as punt_lectura,
                AVG(avg_punt_c_naturales) as punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas) as punt_sociales,
                AVG(avg_punt_ingles) as punt_ingles,
                SUM(total_estudiantes) as total_estudiantes
            FROM gold.fct_agg_colegios_ano
            WHERE ano = {ano} AND departamento = '{department}'
            GROUP BY municipio
        ),
        previous_year AS (
            SELECT 
                municipio,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.fct_agg_colegios_ano
            WHERE ano = {ano_anterior} AND departamento = '{department}'
            GROUP BY municipio
        ),
        departmental_stats AS (
            SELECT 
                AVG(punt_global) as media_departamental,
                STDDEV(punt_global) as std_departamental
            FROM current_year
        )
        SELECT 
            c.municipio as id,
            c.municipio as nombre,
            c.punt_global,
            c.punt_matematicas,
            c.punt_lectura,
            c.punt_c_naturales,
            c.punt_sociales,
            c.punt_ingles,
            ROW_NUMBER() OVER (ORDER BY c.punt_global DESC) as ranking,
            COALESCE(((c.punt_global - p.punt_global_anterior) / NULLIF(p.punt_global_anterior, 0) * 100), 0) as cambio_anual,
            COALESCE(((c.punt_global - d.media_departamental) / NULLIF(d.std_departamental, 0)), 0) as z_score,
            COALESCE(PERCENT_RANK() OVER (ORDER BY c.punt_global) * 100, 0) as percentil
        FROM current_year c
        LEFT JOIN previous_year p ON c.municipio = p.municipio
        CROSS JOIN departmental_stats d
        ORDER BY c.punt_global DESC
        LIMIT 100
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def hierarchy_schools(request):
    """
    Endpoint: Colegios de un municipio con estadísticas y Z-scores.
    Query params: ?municipality=BOGOTA&ano=2024
    """
    municipality = request.GET.get('municipality', '')
    ano = request.GET.get('ano', 2024)
    ano_anterior = int(ano) - 1
    
    if not municipality:
        return JsonResponse([], safe=False)
    
    query = f"""
        WITH current_year AS (
            SELECT 
                colegio_sk,
                MIN(nombre_colegio) as nombre_colegio,
                AVG(avg_punt_global) as punt_global,
                AVG(avg_punt_matematicas) as punt_matematicas,
                AVG(avg_punt_lectura_critica) as punt_lectura,
                AVG(avg_punt_c_naturales) as punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas) as punt_sociales,
                AVG(avg_punt_ingles) as punt_ingles,
                SUM(total_estudiantes) as total_estudiantes
            FROM gold.fct_agg_colegios_ano
            WHERE ano = {ano} AND municipio = '{municipality}'
            GROUP BY colegio_sk
        ),
        previous_year AS (
            SELECT 
                colegio_sk,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.fct_agg_colegios_ano
            WHERE ano = {ano_anterior} AND municipio = '{municipality}'
            GROUP BY colegio_sk
        ),
        municipal_stats AS (
            SELECT 
                AVG(punt_global) as media_municipal,
                STDDEV(punt_global) as std_municipal
            FROM current_year
        )
        SELECT 
            c.colegio_sk as id,
            c.nombre_colegio as nombre,
            c.punt_global,
            c.punt_matematicas,
            c.punt_lectura,
            c.punt_c_naturales,
            c.punt_sociales,
            c.punt_ingles,
            ROW_NUMBER() OVER (ORDER BY c.punt_global DESC) as ranking,
            COALESCE(((c.punt_global - p.punt_global_anterior) / NULLIF(p.punt_global_anterior, 0) * 100), 0) as cambio_anual,
            COALESCE(((c.punt_global - m.media_municipal) / NULLIF(m.std_municipal, 0)), 0) as z_score,
            COALESCE(PERCENT_RANK() OVER (ORDER BY c.punt_global) * 100, 0) as percentil
        FROM current_year c
        LEFT JOIN previous_year p ON c.colegio_sk = p.colegio_sk
        CROSS JOIN municipal_stats m
        WHERE c.total_estudiantes >= 5
        ORDER BY c.punt_global DESC
        LIMIT 200
    """
    
    df = execute_query(query)
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)
