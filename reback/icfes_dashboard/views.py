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
    Endpoint: Análisis de brechas educativas agregadas a nivel nacional.
    Query params: ?ano=2023&tipo_brecha=Sector (opcionales)
    Nota: Esta tabla contiene brechas agregadas (sector, urbano/rural, materias, regional).
    Para análisis por departamento, usar fct_agg_colegios_ano directamente.
    """
    ano = request.GET.get('ano')
    tipo_brecha = request.GET.get('tipo_brecha')
    
    filters = {}
    if ano:
        filters['ano'] = int(ano)
    if tipo_brecha:
        filters['tipo_brecha'] = tipo_brecha
    
    df = get_table_data(
        'gold.brechas_educativas',
        filters=filters,
        order_by=['ano DESC', 'brecha_absoluta_puntos DESC']
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

# ============================================================================
# ENDPOINTS API - SCHOOL INDIVIDUAL VIEW
# ============================================================================

@require_http_methods(['GET'])
def api_search_colegios(request):
    '''Búsqueda/autocomplete de colegios'''
    query_text = request.GET.get('q', '')
    limit = request.GET.get('limit', 20)
    
    if not query_text or len(query_text) < 3:
        return JsonResponse([], safe=False)
    
    query = f'''
        SELECT DISTINCT colegio_sk, codigo_dane, nombre_colegio,
                departamento, municipio, sector
        FROM gold.fct_colegio_historico
        WHERE LOWER(nombre_colegio) LIKE LOWER('%{query_text}%')
           OR codigo_dane LIKE '%{query_text}%'
        ORDER BY nombre_colegio LIMIT {limit}
    '''
    df = execute_query(query)
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_historico(request, colegio_sk):
    """Evolución histórica de un colegio"""
    query = f"""
        WITH ranked_data AS (
            SELECT ano, nombre_colegio, codigo_dane, sector, departamento, municipio,
                   total_estudiantes, avg_punt_global, avg_punt_matematicas,
                   avg_punt_lectura_critica, avg_punt_c_naturales,
                   avg_punt_sociales_ciudadanas, avg_punt_ingles,
                   ranking_nacional, ranking_municipal, percentil_sector,
                   promedio_municipal_global, promedio_departamental_global,
                   promedio_nacional_global, brecha_municipal_global,
                   brecha_departamental_global, brecha_nacional_global,
                   cambio_absoluto_global, cambio_porcentual_global,
                   clasificacion_tendencia,
                   ROW_NUMBER() OVER (PARTITION BY ano ORDER BY ano DESC) as rn
            FROM gold.fct_colegio_historico
            WHERE colegio_sk = '{colegio_sk}'
        )
        SELECT ano, nombre_colegio, codigo_dane, sector, departamento, municipio,
               total_estudiantes, avg_punt_global, avg_punt_matematicas,
               avg_punt_lectura_critica, avg_punt_c_naturales,
               avg_punt_sociales_ciudadanas, avg_punt_ingles,
               ranking_nacional, ranking_municipal, percentil_sector,
               promedio_municipal_global, promedio_departamental_global,
               promedio_nacional_global, brecha_municipal_global,
               brecha_departamental_global, brecha_nacional_global,
               cambio_absoluto_global, cambio_porcentual_global,
               clasificacion_tendencia
        FROM ranked_data
        WHERE rn = 1
        ORDER BY ano ASC
    """
    df = execute_query(query)
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_correlaciones(request, colegio_sk):
    """Correlaciones entre materias y puntaje global"""
    query = f"""
        SELECT *
        FROM gold.fct_colegio_correlaciones
        WHERE colegio_sk = '{colegio_sk}'
    """
    df = execute_query(query)
    if df.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)
    return JsonResponse(df.to_dict(orient='records')[0], safe=False)


@require_http_methods(["GET"])
def api_colegio_fortalezas(request, colegio_sk):
    """Fortalezas y debilidades por materia"""
    query = f"""
        SELECT colegio_sk, codigo_dane, nombre_colegio, sector,
               departamento, municipio, ano,
               materia_mas_fuerte, brecha_materia_fuerte,
               materia_mas_debil, brecha_materia_debil,
               materias_por_encima_promedio, materias_por_debajo_promedio,
               clasificacion_general, perfil_rendimiento,
               urgencia_mejora, recomendacion_principal,
               potencial_mejora_puntos,
               brecha_matematicas, brecha_lectura, brecha_ciencias,
               brecha_sociales, brecha_ingles
        FROM gold.fct_colegio_fortalezas_debilidades
        WHERE colegio_sk = '{colegio_sk}'
        ORDER BY ano DESC
    """
    df = execute_query(query)
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_comparacion(request, colegio_sk):
    """Comparación del colegio vs promedios (último año)"""
    query = f"""
        WITH ultimo_ano AS (
            SELECT MAX(ano) as ano
            FROM gold.fct_colegio_historico
            WHERE colegio_sk = '{colegio_sk}'
        ),
        colegio_data AS (
            SELECT h.ano, h.nombre_colegio, h.codigo_dane, h.sector,
                   h.departamento, h.municipio,
                   h.avg_punt_global as puntaje_colegio,
                   h.promedio_municipal_global, h.promedio_departamental_global,
                   h.promedio_nacional_global, h.brecha_municipal_global,
                   h.brecha_departamental_global, h.brecha_nacional_global,
                   h.ranking_nacional, h.ranking_municipal,
                   h.total_colegios_municipio, h.total_colegios_departamento,
                   h.avg_punt_matematicas, h.avg_punt_lectura_critica,
                   h.avg_punt_c_naturales, h.avg_punt_sociales_ciudadanas,
                   h.avg_punt_ingles
            FROM gold.fct_colegio_historico h
            INNER JOIN ultimo_ano u ON h.ano = u.ano
            WHERE h.colegio_sk = '{colegio_sk}'
        ),
        promedios_contexto AS (
            SELECT 
                c.departamento,
                c.municipio,
                c.ano,
                -- Promedios municipales por materia
                AVG(CASE WHEN f.municipio = c.municipio THEN f.avg_punt_matematicas END) as promedio_municipal_matematicas,
                AVG(CASE WHEN f.municipio = c.municipio THEN f.avg_punt_lectura_critica END) as promedio_municipal_lectura_critica,
                AVG(CASE WHEN f.municipio = c.municipio THEN f.avg_punt_c_naturales END) as promedio_municipal_c_naturales,
                AVG(CASE WHEN f.municipio = c.municipio THEN f.avg_punt_sociales_ciudadanas END) as promedio_municipal_sociales_ciudadanas,
                AVG(CASE WHEN f.municipio = c.municipio THEN f.avg_punt_ingles END) as promedio_municipal_ingles,
                -- Promedios departamentales por materia
                AVG(CASE WHEN f.departamento = c.departamento THEN f.avg_punt_matematicas END) as promedio_departamental_matematicas,
                AVG(CASE WHEN f.departamento = c.departamento THEN f.avg_punt_lectura_critica END) as promedio_departamental_lectura_critica,
                AVG(CASE WHEN f.departamento = c.departamento THEN f.avg_punt_c_naturales END) as promedio_departamental_c_naturales,
                AVG(CASE WHEN f.departamento = c.departamento THEN f.avg_punt_sociales_ciudadanas END) as promedio_departamental_sociales_ciudadanas,
                AVG(CASE WHEN f.departamento = c.departamento THEN f.avg_punt_ingles END) as promedio_departamental_ingles,
                -- Promedios nacionales por materia
                AVG(f.avg_punt_matematicas) as promedio_nacional_matematicas,
                AVG(f.avg_punt_lectura_critica) as promedio_nacional_lectura_critica,
                AVG(f.avg_punt_c_naturales) as promedio_nacional_c_naturales,
                AVG(f.avg_punt_sociales_ciudadanas) as promedio_nacional_sociales_ciudadanas,
                AVG(f.avg_punt_ingles) as promedio_nacional_ingles
            FROM colegio_data c
            CROSS JOIN gold.fct_agg_colegios_ano f
            WHERE f.ano = c.ano
            GROUP BY c.departamento, c.municipio, c.ano
        )
        SELECT 
            c.*,
            p.promedio_municipal_matematicas,
            p.promedio_municipal_lectura_critica,
            p.promedio_municipal_c_naturales,
            p.promedio_municipal_sociales_ciudadanas,
            p.promedio_municipal_ingles,
            p.promedio_departamental_matematicas,
            p.promedio_departamental_lectura_critica,
            p.promedio_departamental_c_naturales,
            p.promedio_departamental_sociales_ciudadanas,
            p.promedio_departamental_ingles,
            p.promedio_nacional_matematicas,
            p.promedio_nacional_lectura_critica,
            p.promedio_nacional_c_naturales,
            p.promedio_nacional_sociales_ciudadanas,
            p.promedio_nacional_ingles
        FROM colegio_data c
        LEFT JOIN promedios_contexto p ON c.departamento = p.departamento 
            AND c.municipio = p.municipio AND c.ano = p.ano
    """
    df = execute_query(query)
    if df.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)
    return JsonResponse(df.to_dict(orient='records')[0], safe=False)


@require_http_methods(["GET"])
def api_colegio_resumen(request, colegio_sk):
    """Resumen ejecutivo del colegio"""
    # Información básica
    query_basico = f"""
        SELECT DISTINCT colegio_sk, codigo_dane, nombre_colegio,
               sector, departamento, municipio
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = '{colegio_sk}'
        LIMIT 1
    """
    
    # Último año
    query_ultimo = f"""
        WITH ultimo_ano AS (
            SELECT MAX(ano) as ano
            FROM gold.fct_colegio_historico
            WHERE colegio_sk = '{colegio_sk}'
        )
        SELECT h.ano, h.total_estudiantes, h.avg_punt_global,
               h.ranking_nacional, h.ranking_municipal,
               h.cambio_absoluto_global, h.cambio_porcentual_global,
               h.clasificacion_tendencia
        FROM gold.fct_colegio_historico h
        INNER JOIN ultimo_ano u ON h.ano = u.ano
        WHERE h.colegio_sk = '{colegio_sk}'
    """
    
    # Rango de años
    query_rango = f"""
        SELECT MIN(ano) as ano_inicio, MAX(ano) as ano_fin,
               COUNT(DISTINCT ano) as total_anos
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = '{colegio_sk}'
    """
    
    # Fortalezas/debilidades
    query_fd = f"""
        SELECT materias_por_encima_promedio, materias_por_debajo_promedio,
               clasificacion_general, perfil_rendimiento
        FROM gold.fct_colegio_fortalezas_debilidades
        WHERE colegio_sk = '{colegio_sk}'
        ORDER BY ano DESC
        LIMIT 1
    """
    
    df_basico = execute_query(query_basico)
    df_ultimo = execute_query(query_ultimo)
    df_rango = execute_query(query_rango)
    df_fd = execute_query(query_fd)
    
    if df_basico.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)
    
    resumen = {
        'info_basica': df_basico.to_dict(orient='records')[0],
        'ultimo_ano': df_ultimo.to_dict(orient='records')[0] if not df_ultimo.empty else {},
        'rango_historico': df_rango.to_dict(orient='records')[0] if not df_rango.empty else {},
        'analisis': df_fd.to_dict(orient='records')[0] if not df_fd.empty else {}
    }
    
    return JsonResponse(resumen, safe=False)


@require_http_methods(["GET"])
def api_colegio_ai_recommendations(request, colegio_sk):
    """Generate AI-powered recommendations for school improvement using Anthropic Claude"""
    try:
        # Get school data
        historico_query = f"""
            SELECT * FROM gold.fct_colegio_historico
            WHERE colegio_sk = '{colegio_sk}'
            ORDER BY ano DESC LIMIT 5
        """
        historico = execute_query(historico_query)
        
        fortalezas_query = f"""
            SELECT * FROM gold.fct_colegio_fortalezas_debilidades
            WHERE colegio_sk = '{colegio_sk}'
            ORDER BY ano DESC LIMIT 1
        """
        fortalezas = execute_query(fortalezas_query)
        
        if historico.empty:
            return JsonResponse({'error': 'No se encontraron datos para este colegio'}, status=404)
        
        # Prepare data for AI
        school_data = {
            'historical_performance': historico.to_dict(orient='records'),
            'strengths_weaknesses': fortalezas.to_dict(orient='records')[0] if not fortalezas.empty else {}
        }
        
        # Check if Anthropic API key is configured
        from django.conf import settings
        if not hasattr(settings, 'ANTHROPIC_API_KEY') or not settings.ANTHROPIC_API_KEY:
            return JsonResponse({
                'error': 'API de IA no configurada',
                'message': 'Por favor, configura ANTHROPIC_API_KEY en settings.py'
            }, status=503)
        
        # Call Anthropic Claude API
        import anthropic
        import json
        
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        prompt = f"""Analiza el siguiente colegio colombiano basado en sus resultados ICFES:

Datos históricos (últimos 5 años):
{json.dumps(school_data['historical_performance'], indent=2, ensure_ascii=False)}

Fortalezas y debilidades actuales:
{json.dumps(school_data['strengths_weaknesses'], indent=2, ensure_ascii=False)}

Proporciona un análisis detallado en formato JSON con la siguiente estructura:
{{
    "evaluacion_general": "Evaluación general del colegio en 2-3 párrafos",
    "fortalezas": ["fortaleza 1", "fortaleza 2", "fortaleza 3", "fortaleza 4", "fortaleza 5"],
    "debilidades": ["debilidad 1", "debilidad 2", "debilidad 3", "debilidad 4", "debilidad 5"],
    "estrategias_5_puntos": [
        "Estrategia específica 1 para aumentar 5 puntos en el puntaje global",
        "Estrategia específica 2",
        "Estrategia específica 3",
        "Estrategia específica 4",
        "Estrategia específica 5"
    ],
    "recomendaciones_materias": {{
        "Matemáticas": "Recomendación específica para matemáticas",
        "Lectura Crítica": "Recomendación específica para lectura",
        "Ciencias Naturales": "Recomendación específica para ciencias",
        "Sociales": "Recomendación específica para sociales",
        "Inglés": "Recomendación específica para inglés"
    }},
    "plan_accion": "Plan de acción prioritario detallado en 1-2 párrafos con pasos concretos"
}}

Asegúrate de que las recomendaciones sean:
1. Específicas y accionables
2. Basadas en los datos proporcionados
3. Realistas y alcanzables
4. Priorizadas por impacto
5. Contextualizadas al sistema educativo colombiano

Responde ÚNICAMENTE con el JSON, sin texto adicional."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse AI response - Claude may wrap JSON in markdown code blocks
        response_text = message.content[0].text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            # Find the actual JSON content between code blocks
            lines = response_text.split('\n')
            json_lines = []
            in_code_block = False
            for line in lines:
                if line.startswith('```'):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.startswith('```') and json_lines):
                    json_lines.append(line)
            response_text = '\n'.join(json_lines).strip()
        
        # Parse JSON
        ai_response = json.loads(response_text)
        return JsonResponse(ai_response)
        
    except json.JSONDecodeError as e:
        return JsonResponse({
            'error': 'Error al parsear respuesta de IA',
            'details': f'La IA no respondió en formato JSON válido. Error: {str(e)}',
            'raw_response': response_text[:500] if 'response_text' in locals() else 'No disponible'
        }, status=500)
    except Exception as e:
        return JsonResponse({
            'error': 'Error al generar recomendaciones',
            'details': str(e)
        }, status=500)


def colegio_detalle_page(request):
    '''Vista de la página de detalle individual del colegio'''
    return render(request, 'icfes_dashboard/pages/colegio-detalle.html')


# ============================================================================
# ENDPOINTS API - COMPARACIÓN CON CONTEXTO (usando modelo gold)
# ============================================================================

@require_http_methods(["GET"])
def api_colegio_comparacion_contexto(request, colegio_sk):
    """
    Comparación del colegio con contexto municipal, departamental y nacional.
    Usa el modelo pre-calculado gold.fct_colegio_comparacion_contexto
    
    Query params: ?ano=2022 (opcional, retorna todos los años si no se especifica)
    
    Retorna:
    - Puntajes del colegio en todas las materias
    - Promedios municipal, departamental y nacional
    - Brechas (diferencias) vs cada nivel
    - Percentiles (posición relativa)
    - Clasificaciones de rendimiento
    """
    ano = request.GET.get('ano')
    
    query = f"""
        SELECT 
            ano,
            colegio_sk,
            nombre_colegio,
            departamento,
            municipio,
            sector,
            total_estudiantes,
            
            -- Puntajes del colegio
            colegio_lectura,
            colegio_matematicas,
            colegio_c_naturales,
            colegio_sociales,
            colegio_ingles,
            colegio_global,
            
            -- Contexto municipal
            total_colegios_municipio,
            total_estudiantes_municipio,
            promedio_municipal_lectura,
            promedio_municipal_matematicas,
            promedio_municipal_c_naturales,
            promedio_municipal_sociales,
            promedio_municipal_ingles,
            promedio_municipal_global,
            brecha_municipal_global,
            percentil_municipal,
            clasificacion_vs_municipal,
            
            -- Contexto departamental
            total_colegios_departamento,
            total_estudiantes_departamento,
            promedio_departamental_lectura,
            promedio_departamental_matematicas,
            promedio_departamental_c_naturales,
            promedio_departamental_sociales,
            promedio_departamental_ingles,
            promedio_departamental_global,
            brecha_departamental_global,
            percentil_departamental,
            clasificacion_vs_departamental,
            
            -- Contexto nacional
            total_colegios_nacional,
            total_estudiantes_nacional,
            promedio_nacional_lectura,
            promedio_nacional_matematicas,
            promedio_nacional_c_naturales,
            promedio_nacional_sociales,
            promedio_nacional_ingles,
            promedio_nacional_global,
            brecha_nacional_global,
            percentil_nacional,
            clasificacion_vs_nacional
            
        FROM gold.fct_colegio_comparacion_contexto
        WHERE colegio_sk = '{colegio_sk}'
        {f"AND ano = {ano}" if ano else ""}
        ORDER BY ano DESC
    """
    
    df = execute_query(query)
    
    if df.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)
    
    # Si se pidió un año específico, retornar solo ese registro
    if ano:
        return JsonResponse(df.to_dict(orient='records')[0], safe=False)
    
    # Si no, retornar todos los años (histórico)
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_comparacion_chart_data(request, colegio_sk):
    """
    Datos formateados específicamente para gráficos de comparación.
    Retorna estructura optimizada para Chart.js o similar.
    
    Query params: ?ano=2022 (requerido)
    """
    ano = request.GET.get('ano')
    
    if not ano:
        return JsonResponse({'error': 'Parámetro ano es requerido'}, status=400)
    
    query = f"""
        SELECT 
            nombre_colegio,
            
            -- Puntajes por materia
            colegio_lectura,
            colegio_matematicas,
            colegio_c_naturales,
            colegio_sociales,
            colegio_ingles,
            
            -- Promedios para comparación
            promedio_municipal_lectura,
            promedio_municipal_matematicas,
            promedio_municipal_c_naturales,
            promedio_municipal_sociales,
            promedio_municipal_ingles,
            
            promedio_departamental_lectura,
            promedio_departamental_matematicas,
            promedio_departamental_c_naturales,
            promedio_departamental_sociales,
            promedio_departamental_ingles,
            
            promedio_nacional_lectura,
            promedio_nacional_matematicas,
            promedio_nacional_c_naturales,
            promedio_nacional_sociales,
            promedio_nacional_ingles,
            
            municipio,
            departamento
            
        FROM gold.fct_colegio_comparacion_contexto
        WHERE colegio_sk = '{colegio_sk}'
            AND ano = {ano}
    """
    
    df = execute_query(query)
    
    if df.empty:
        return JsonResponse({'error': 'Datos no encontrados'}, status=404)
    
    row = df.iloc[0]
    
    # Formatear para Chart.js (radar chart)
    result = {
        'labels': ['Lectura Crítica', 'Matemáticas', 'C. Naturales', 'Sociales', 'Inglés'],
        'datasets': [
            {
                'label': row['nombre_colegio'],
                'data': [
                    float(row['colegio_lectura']),
                    float(row['colegio_matematicas']),
                    float(row['colegio_c_naturales']),
                    float(row['colegio_sociales']),
                    float(row['colegio_ingles'])
                ]
            },
            {
                'label': f"Promedio {row['municipio']}",
                'data': [
                    float(row['promedio_municipal_lectura']),
                    float(row['promedio_municipal_matematicas']),
                    float(row['promedio_municipal_c_naturales']),
                    float(row['promedio_municipal_sociales']),
                    float(row['promedio_municipal_ingles'])
                ]
            },
            {
                'label': f"Promedio {row['departamento']}",
                'data': [
                    float(row['promedio_departamental_lectura']),
                    float(row['promedio_departamental_matematicas']),
                    float(row['promedio_departamental_c_naturales']),
                    float(row['promedio_departamental_sociales']),
                    float(row['promedio_departamental_ingles'])
                ]
            },
            {
                'label': 'Promedio Nacional',
                'data': [
                    float(row['promedio_nacional_lectura']),
                    float(row['promedio_nacional_matematicas']),
                    float(row['promedio_nacional_c_naturales']),
                    float(row['promedio_nacional_sociales']),
                    float(row['promedio_nacional_ingles'])
                ]
            }
        ]
    }
    
    return JsonResponse(result, safe=False)
