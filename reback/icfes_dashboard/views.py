"""
Vistas para el dashboard ICFES.
Conecta con la base de datos DuckDB del proyecto dbt.
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
import pandas as pd
import json
import unicodedata
from .db_utils import (
    execute_query,
    get_table_data,
    get_anos_disponibles,
    get_departamentos,
    get_estadisticas_generales,
    get_promedios_ubicacion
)
from .views_school_endpoints import *


def _normalize_departamento_variants(name):
    """Retorna variantes para filtrar departamento de forma robusta."""
    if not name:
        return None

    raw = str(name).strip()
    original = raw.upper()
    no_accents = ''.join(
        c for c in unicodedata.normalize('NFD', original)
        if unicodedata.category(c) != 'Mn'
    )
    no_punct = ''.join(ch if ch.isalnum() or ch.isspace() else ' ' for ch in no_accents)
    no_punct = ' '.join(no_punct.split())

    values = set([raw, original, no_accents, no_punct])

    if 'BOGOTA' in no_punct:
        values.update([
            'BOGOTA', 'BOGOTÁ',
            'BOGOTA D.C.', 'BOGOTÁ D.C.',
            'BOGOTA DC', 'BOGOTÁ DC',
            'Bogotá DC', 'Bogotá D.C.', 'BOGOTA D C',
        ])
    if 'VALLE DEL CAUCA' in no_punct:
        values.update(['VALLE', 'VALLE DEL CAUCA', 'Valle del Cauca'])
    if 'NORTE DE SANTANDER' in no_punct:
        values.update(['NORTE DE SANTANDER', 'NORTE SANTANDER'])
    if 'SAN ANDRES' in no_punct:
        values.update([
            'SAN ANDRES',
            'SAN ANDRES PROVIDENCIA Y SANTA CATALINA',
            'ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA',
            'Archipiélago de San Andrés, Providencia y Santa Catalina',
        ])

    return sorted(values)


def _dept_key(value):
    """Clave de comparación robusta para nombres de departamento."""
    if value is None:
        return ""
    s = str(value).strip().upper()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = ''.join(ch if ch.isalnum() or ch.isspace() else ' ' for ch in s)
    return ' '.join(s.split())


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


def brecha_educativa_dashboard(request):
    """Vista del dashboard de brechas educativas: Oficial vs No Oficial."""
    context = {
        'anos_disponibles': get_anos_disponibles(),
        'departamentos': get_departamentos(),
    }
    return render(request, 'icfes_dashboard/pages/dashboard-brecha.html', context)


def resumen_ejecutivo_dashboard(request):
    """Vista de resumen ejecutivo de storytelling ICFES."""
    context = {
        'anos_disponibles': get_anos_disponibles(),
        'departamentos': get_departamentos(),
    }
    return render(request, 'icfes_dashboard/pages/resumen-ejecutivo-icfes.html', context)


def historia_educacion_dashboard(request):
    """Vista de storytelling: Historia de la Educación Colombiana."""
    return render(request, 'icfes_dashboard/pages/dashboard-historia.html', {})


def inteligencia_educativa_dashboard(request):
    """Vista de Inteligencia Educativa: 4 narrativas ML-driven."""
    return render(request, 'icfes_dashboard/pages/dashboard-inteligencia.html', {})


def ingles_dashboard(request):
    """Vista del dashboard de Bilingüismo/Inglés."""
    context = {
        'anos_disponibles': get_anos_disponibles(),
        'departamentos': get_departamentos(),
    }
    return render(request, 'icfes_dashboard/pages/dashboard-ingles.html', context)


# ============================================================================
# ENDPOINTS API - DATOS GENERALES
# ============================================================================

@cache_page(60 * 15)  # 15 minutos - estadísticas generales
@require_http_methods(["GET"])
def icfes_estadisticas_generales(request):
    """
    Endpoint: Estadísticas generales del sistema.
    Query params: ?ano=2023 (opcional)
    CACHED: 15 minutos
    """
    ano = request.GET.get('ano')
    ano = int(ano) if ano else None
    
    stats = get_estadisticas_generales(ano)
    return JsonResponse(stats, safe=False)


@cache_page(60 * 60 * 24)  # 24 horas - lista de años cambia raramente
@require_http_methods(["GET"])
def icfes_anos_disponibles(request):
    """Endpoint: Lista de años disponibles.
    CACHED: 24 horas
    """
    anos = get_anos_disponibles()
    return JsonResponse({'anos': anos})


# ============================================================================
# ENDPOINTS API - TENDENCIAS REGIONALES
# ============================================================================

@cache_page(60 * 60)  # 1 hora - tendencias regionales
@require_http_methods(["GET"])
def tendencias_regionales(request):
    """
    Endpoint: Tendencias regionales por año.
    Query params: ?ano=2023&region=ANDINA (opcionales)
    CACHED: 1 hora
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


@cache_page(60 * 30)  # 30 minutos - top colegios
@require_http_methods(["GET"])
def colegios_destacados(request):
    """
    Endpoint: Top colegios destacados.
    Query params: ?ano=2023&limit=50 (opcionales)
    Genera el ranking dinámicamente desde fct_agg_colegios_ano
    CACHED: 30 minutos
    """
    # Validar y sanitizar parámetros
    try:
        ano = int(request.GET.get('ano', 2023))
        limit = int(request.GET.get('limit', 50))
        # Limitar el máximo de resultados
        limit = min(limit, 500)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    # Generar ranking dinámicamente desde fct_agg_colegios_ano
    # Agrupar por colegio_sk para evitar duplicados con variaciones de nombre
    query = """
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
            WHERE ano = ?
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
        LIMIT ?
    """

    df = execute_query(query, params=[ano, limit])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def colegio_detalle(request, colegio_sk):
    """
    Endpoint: Detalle histórico de un colegio específico.
    """
    # Validar colegio_sk (debe ser string alfanumérico)
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    query = """
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
        WHERE colegio_sk = ?
        ORDER BY ano DESC
    """

    df = execute_query(query, params=[str(colegio_sk)])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


# ============================================================================
# ENDPOINTS API - BRECHAS EDUCATIVAS
# ============================================================================

@cache_page(60 * 60)  # 1 hora - brechas educativas
@require_http_methods(["GET"])
def brechas_educativas(request):
    """
    Endpoint: Análisis de brechas educativas agregadas a nivel nacional.
    Query params: ?ano=2023&tipo_brecha=Sector (opcionales)
    Nota: Esta tabla contiene brechas agregadas (sector, urbano/rural, materias, regional).
    Para análisis por departamento, usar fct_agg_colegios_ano directamente.
    CACHED: 1 hora
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

@cache_page(60 * 30)  # 30 minutos - comparación sectores
@require_http_methods(["GET"])
def comparacion_sectores(request):
    """
    Endpoint: Comparación entre sector oficial y no oficial.
    Query params: ?ano=2023 (opcional)
    CACHED: 30 minutos
    """
    try:
        ano = int(request.GET.get('ano', 2023))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
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
        WHERE ano = ?
        GROUP BY sector
        ORDER BY sector
    """

    df = execute_query(query, params=[ano])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@cache_page(60 * 60)  # 1 hora - ranking departamental
@require_http_methods(["GET"])
def ranking_departamental(request):
    """
    Endpoint: Ranking de departamentos por promedio.
    Query params: ?ano=2023 (opcional)
    CACHED: 1 hora
    """
    try:
        ano = int(request.GET.get('ano', 2023))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
        SELECT
            departamento,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes,
            AVG(avg_punt_global) as promedio_departamental,
            STDDEV(avg_punt_global) as desviacion_estandar,
            MIN(avg_punt_global) as puntaje_minimo,
            MAX(avg_punt_global) as puntaje_maximo
        FROM gold.fct_agg_colegios_ano
        WHERE ano = ?
        GROUP BY departamento
        ORDER BY promedio_departamental DESC
    """

    df = execute_query(query, params=[ano])
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
    try:
        ano = int(request.GET.get('ano', 2023))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
        SELECT
            departamento as depto,
            AVG(avg_punt_global) as promedio_global,
            SUM(total_estudiantes) as total_estudiantes
        FROM gold.fct_agg_colegios_ano
        WHERE ano = ?
        GROUP BY departamento
        ORDER BY promedio_global DESC
    """

    df = execute_query(query, params=[ano])
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
# ENDPOINTS API - STORYTELLING EJECUTIVO
# ============================================================================

@cache_page(60 * 30)  # 30 minutos
@require_http_methods(["GET"])
def api_story_resumen_ejecutivo(request):
    """
    Endpoint: KPIs ejecutivos para un año específico.
    Query params: ?ano=2024 (opcional, default último disponible)
    """
    try:
        ano_param = request.GET.get('ano')
        ano_objetivo = int(ano_param) if ano_param else int(
            execute_query("SELECT MAX(CAST(ano AS INTEGER)) AS ano FROM gold.icfes_master_resumen").iloc[0]['ano']
        )
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    departamento = request.GET.get('departamento')
    depto_vals = _normalize_departamento_variants(departamento) if departamento else None

    where_clauses = ["m.estudiantes > 0", "CAST(m.ano AS INTEGER) = ?"]
    params = [ano_objetivo]
    if depto_vals:
        ph = ", ".join(["?"] * len(depto_vals))
        where_clauses.append(f"m.cole_depto_ubicacion IN ({ph})")
        params.extend(depto_vals)
    where_stmt = " AND ".join(where_clauses)

    riesgo_where = ["ano = ?"]
    riesgo_params = [ano_objetivo]
    if depto_vals:
        ph = ", ".join(["?"] * len(depto_vals))
        riesgo_where.append(f"departamento IN ({ph})")
        riesgo_params.extend(depto_vals)
    riesgo_where_stmt = " AND ".join(riesgo_where)

    query = f"""
        WITH base AS (
          SELECT
            m.cole_cod_dane_establecimiento AS codigo_dane,
            m.avg_global,
            m.estudiantes,
            CASE
              WHEN UPPER(m.cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN 'NO_OFICIAL'
              WHEN UPPER(m.cole_naturaleza) = 'OFICIAL' OR m.cole_naturaleza = '1' THEN 'OFICIAL'
              ELSE NULL
            END AS sector_norm
          FROM gold.icfes_master_resumen m
          WHERE {where_stmt}
        ),
        kpi AS (
          SELECT
            ROUND(SUM(avg_global * estudiantes) / NULLIF(SUM(estudiantes), 0), 2) AS promedio_nacional,
            SUM(estudiantes) AS total_estudiantes,
            COUNT(DISTINCT codigo_dane) AS total_colegios,
            ROUND(STDDEV_SAMP(avg_global), 2) AS desviacion_estandar,
            ROUND(
              (SUM(CASE WHEN sector_norm = 'NO_OFICIAL' THEN avg_global * estudiantes ELSE 0 END)
               / NULLIF(SUM(CASE WHEN sector_norm = 'NO_OFICIAL' THEN estudiantes ELSE 0 END), 0))
              -
              (SUM(CASE WHEN sector_norm = 'OFICIAL' THEN avg_global * estudiantes ELSE 0 END)
               / NULLIF(SUM(CASE WHEN sector_norm = 'OFICIAL' THEN estudiantes ELSE 0 END), 0))
            , 2) AS brecha_sector_publico_privado
          FROM base
          WHERE sector_norm IS NOT NULL
        ),
        riesgo AS (
          SELECT
            AVG(prob_declive) AS prob_declive_prom,
            SUM(CASE WHEN nivel_riesgo = 'Alto' THEN 1 ELSE 0 END) AS colegios_alto_riesgo,
            COUNT(*) AS total_colegios_riesgo
          FROM gold.fct_riesgo_colegios
          WHERE {riesgo_where_stmt}
        )
        SELECT
          ? AS ano,
          k.promedio_nacional,
          k.total_estudiantes,
          k.total_colegios,
          k.desviacion_estandar,
          COALESCE(k.brecha_sector_publico_privado, 0) AS brecha_sector_publico_privado,
          r.prob_declive_prom,
          r.colegios_alto_riesgo,
          r.total_colegios_riesgo
        FROM kpi k
        CROSS JOIN riesgo r
    """

    df = execute_query(query, params=params + riesgo_params + [ano_objetivo])
    if df.empty:
        return JsonResponse({'error': 'No hay datos para el año solicitado'}, status=404)
    return JsonResponse(df.to_dict(orient='records')[0], safe=False)


@cache_page(60 * 60)  # 1 hora
@require_http_methods(["GET"])
def api_story_serie_anual(request):
    """Endpoint: Serie anual consolidada (promedio, brecha y riesgo)."""
    departamento = request.GET.get('departamento')
    depto_vals = _normalize_departamento_variants(departamento) if departamento else None

    where_clauses = ["m.estudiantes > 0"]
    params = []
    if depto_vals:
        ph = ", ".join(["?"] * len(depto_vals))
        where_clauses.append(f"m.cole_depto_ubicacion IN ({ph})")
        params.extend(depto_vals)
    where_stmt = " AND ".join(where_clauses)

    riesgo_where = []
    riesgo_params = []
    if depto_vals:
        ph = ", ".join(["?"] * len(depto_vals))
        riesgo_where.append(f"departamento IN ({ph})")
        riesgo_params.extend(depto_vals)
    riesgo_where_stmt = ("WHERE " + " AND ".join(riesgo_where)) if riesgo_where else ""

    query = f"""
        WITH serie AS (
          SELECT
            CAST(m.ano AS INTEGER) AS ano,
            COUNT(DISTINCT m.cole_cod_dane_establecimiento) AS total_colegios,
            SUM(m.estudiantes) AS total_estudiantes,
            ROUND(SUM(m.avg_global * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS promedio_nacional,
            ROUND(STDDEV_SAMP(m.avg_global), 2) AS desviacion_estandar,
            ROUND(SUM(m.avg_matematicas * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS promedio_matematicas,
            ROUND(SUM(m.avg_lectura * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS promedio_lectura,
            ROUND(
              (SUM(CASE WHEN UPPER(m.cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN m.avg_global * m.estudiantes ELSE 0 END)
               / NULLIF(SUM(CASE WHEN UPPER(m.cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN m.estudiantes ELSE 0 END), 0))
              -
              (SUM(CASE WHEN UPPER(m.cole_naturaleza) = 'OFICIAL' OR m.cole_naturaleza = '1' THEN m.avg_global * m.estudiantes ELSE 0 END)
               / NULLIF(SUM(CASE WHEN UPPER(m.cole_naturaleza) = 'OFICIAL' OR m.cole_naturaleza = '1' THEN m.estudiantes ELSE 0 END), 0))
            , 2) AS brecha_sector_publico_privado
          FROM gold.icfes_master_resumen m
          WHERE {where_stmt}
          GROUP BY CAST(m.ano AS INTEGER)
        ),
        riesgo AS (
          SELECT
            ano,
            SUM(CASE WHEN nivel_riesgo = 'Alto' THEN 1 ELSE 0 END) AS colegios_alto_riesgo,
            COUNT(*) AS total_colegios_riesgo
          FROM gold.fct_riesgo_colegios
          {riesgo_where_stmt}
          GROUP BY ano
        )
        SELECT
          s.ano,
          s.total_estudiantes,
          s.total_colegios,
          s.promedio_nacional,
          s.desviacion_estandar,
          s.promedio_matematicas,
          s.promedio_lectura,
          COALESCE(s.brecha_sector_publico_privado, 0) AS brecha_sector_publico_privado,
          COALESCE(r.colegios_alto_riesgo, 0) AS colegios_alto_riesgo,
          COALESCE(r.total_colegios_riesgo, 0) AS total_colegios_riesgo
        FROM serie s
        LEFT JOIN riesgo r ON r.ano = s.ano
        ORDER BY s.ano DESC
    """
    df = execute_query(query, params=params + riesgo_params if (params or riesgo_params) else None)
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@cache_page(60 * 30)  # 30 minutos
@require_http_methods(["GET"])
def api_story_brechas_clave(request):
    """
    Endpoint: Brechas clave del año (incluye convergencia regional).
    Query params: ?ano=2024 (opcional, default último disponible)
    """
    try:
        ano_param = request.GET.get('ano')
        if ano_param:
            ano_objetivo = int(ano_param)
        else:
            dfa = execute_query("SELECT MAX(CAST(ano AS INTEGER)) AS ano FROM gold.brechas_educativas")
            ano_objetivo = int(dfa.iloc[0]['ano'])
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    departamento = request.GET.get('departamento')
    depto_vals = _normalize_departamento_variants(departamento) if departamento else None

    q_brechas = """
        SELECT
            CAST(ano AS INTEGER) AS ano,
            tipo_brecha,
            brecha_absoluta_puntos,
            brecha_relativa_pct,
            cambio_brecha_yoy,
            tendencia_brecha,
            magnitud_brecha
        FROM gold.brechas_educativas
        WHERE CAST(ano AS INTEGER) = ?
        ORDER BY tipo_brecha
    """
    q_conv = """
        SELECT
            CAST(ano AS INTEGER) AS ano,
            promedio_nacional,
            brecha_lider_rezagado,
            estado_convergencia,
            tendencia_brecha
        FROM gold.convergencia_regional
        WHERE CAST(ano AS INTEGER) = ?
    """
    brechas_df = execute_query(q_brechas, params=[ano_objetivo])
    # Fallback al último año disponible si no hay brechas para el año solicitado.
    if brechas_df.empty:
        max_df = execute_query("SELECT MAX(CAST(ano AS INTEGER)) AS ano FROM gold.brechas_educativas")
        if not max_df.empty and max_df.iloc[0]['ano'] is not None:
            ano_objetivo = int(max_df.iloc[0]['ano'])
            brechas_df = execute_query(q_brechas, params=[ano_objetivo])

    brechas = brechas_df.to_dict(orient='records')
    # Si hay filtro departamental, recalcula al menos la brecha de sector para ese contexto.
    if depto_vals:
        ph = ", ".join(["?"] * len(depto_vals))
        q_sector_local = f"""
            SELECT
              ? AS ano,
              'Sector Público vs Privado' AS tipo_brecha,
              ROUND(
                (SUM(CASE WHEN UPPER(m.cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN m.avg_global * m.estudiantes ELSE 0 END)
                 / NULLIF(SUM(CASE WHEN UPPER(m.cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN m.estudiantes ELSE 0 END), 0))
                -
                (SUM(CASE WHEN UPPER(m.cole_naturaleza) = 'OFICIAL' OR m.cole_naturaleza = '1' THEN m.avg_global * m.estudiantes ELSE 0 END)
                 / NULLIF(SUM(CASE WHEN UPPER(m.cole_naturaleza) = 'OFICIAL' OR m.cole_naturaleza = '1' THEN m.estudiantes ELSE 0 END), 0))
              , 2) AS brecha_absoluta_puntos,
              NULL AS brecha_relativa_pct,
              NULL AS cambio_brecha_yoy,
              NULL AS tendencia_brecha,
              NULL AS magnitud_brecha
            FROM gold.icfes_master_resumen m
            WHERE m.estudiantes > 0
              AND CAST(m.ano AS INTEGER) = ?
              AND m.cole_depto_ubicacion IN ({ph})
        """
        local_df = execute_query(q_sector_local, params=[ano_objetivo, ano_objetivo] + depto_vals)
        local_rows = local_df.to_dict(orient='records')
        if local_rows and local_rows[0].get('brecha_absoluta_puntos') is not None:
            brechas = [b for b in brechas if b.get('tipo_brecha') != 'Sector Público vs Privado']
            brechas.append(local_rows[0])

    conv_df = execute_query(q_conv, params=[ano_objetivo])
    convergencia = conv_df.to_dict(orient='records')[0] if not conv_df.empty else {}

    return JsonResponse({
        'ano': ano_objetivo,
        'brechas': brechas,
        'convergencia_regional': convergencia,
    }, safe=False)


@cache_page(60 * 15)  # 15 minutos
@require_http_methods(["GET"])
def api_story_priorizacion(request):
    """
    Endpoint: Ranking de priorización accionable.
    Query params: ?ano=2024&departamento=BOGOTA%20D.C.&limit=30
    """
    try:
        ano_objetivo = int(request.GET.get('ano', 2024))
        limit = int(request.GET.get('limit', 30))
        limit = min(max(limit, 1), 200)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    departamento = request.GET.get('departamento')
    depto_vals = _normalize_departamento_variants(departamento) if departamento else None

    # El modelo de riesgo no siempre existe para todos los años del selector.
    # Usamos el último año disponible <= año solicitado (o el último global como fallback).
    q_ano_modelo = """
        SELECT
          COALESCE(
            MAX(CASE WHEN ano <= ? THEN ano END),
            MAX(ano)
          ) AS ano_modelo
        FROM gold.fct_riesgo_colegios
    """
    ano_df = execute_query(q_ano_modelo, params=[ano_objetivo])
    ano_modelo = int(ano_df.iloc[0]['ano_modelo']) if not ano_df.empty and pd.notna(ano_df.iloc[0]['ano_modelo']) else ano_objetivo

    query = """
        WITH risk AS (
          SELECT
            codigo_dane,
            departamento,
            prob_declive,
            avg_punt_global_actual
          FROM gold.fct_riesgo_colegios
          WHERE ano = ?
        ),
        agg AS (
          SELECT
            colegio_bk AS codigo_dane,
            gap_municipio_promedio,
            municipio
          FROM gold.fct_agg_colegios_ano
          WHERE CAST(ano AS INTEGER) = ?
        ),
        joined AS (
          SELECT
            r.codigo_dane,
            r.departamento,
            a.municipio,
            r.prob_declive,
            r.avg_punt_global_actual,
            a.gap_municipio_promedio
          FROM risk r
          LEFT JOIN agg a ON r.codigo_dane = a.codigo_dane
        ),
        scored AS (
          SELECT
            *,
            COALESCE(prob_declive, 0) * 0.5
              + (1 - COALESCE(avg_punt_global_actual, 0) / 500.0) * 0.3
              + (
                  CASE
                    WHEN COALESCE(gap_municipio_promedio, 0) < 0
                      THEN ABS(gap_municipio_promedio) / 100.0
                    ELSE 0
                  END
                ) * 0.2 AS priority_score
          FROM joined
        )
        SELECT
          s.codigo_dane,
          MIN(c.nombre_colegio) AS nombre_colegio,
          s.departamento,
          MIN(s.municipio) AS municipio,
          ROUND(AVG(s.prob_declive), 4) AS prob_declive,
          ROUND(AVG(s.avg_punt_global_actual), 2) AS avg_punt_global_actual,
          ROUND(AVG(s.gap_municipio_promedio), 2) AS gap_municipio_promedio,
          ROUND(AVG(s.priority_score), 4) AS priority_score
        FROM scored s
        LEFT JOIN gold.fct_riesgo_colegios c
          ON c.codigo_dane = s.codigo_dane AND c.ano = ?
        GROUP BY s.codigo_dane, s.departamento
        ORDER BY priority_score DESC
    """

    params = [ano_modelo, ano_objetivo, ano_modelo]
    df = execute_query(query, params=params)

    # Filtrado robusto por departamento en Python para evitar problemas de acentos/puntuación
    if depto_vals:
        target_keys = {_dept_key(v) for v in depto_vals}
        if 'BOGOTA DC' in target_keys or 'BOGOTA D C' in target_keys or 'BOGOTA' in target_keys:
            target_keys.update({'BOGOTA', 'BOGOTA DC', 'BOGOTA D C'})
        if not df.empty:
            df = df[df['departamento'].apply(lambda x: _dept_key(x) in target_keys)]

    if not df.empty:
        df = df.sort_values(by='priority_score', ascending=False).head(limit)

    return JsonResponse({
        'ano': ano_objetivo,
        'ano_modelo': ano_modelo,
        'departamento': departamento,
        'total': len(df.index),
        'items': df.to_dict(orient='records'),
    }, safe=False)


# ============================================================================
# ENDPOINTS API - CHARTS DATA
# ============================================================================

@cache_page(60 * 60 * 24)  # Cache 24 horas - datos históricos no cambian
@require_http_methods(["GET"])
def api_tendencias_nacionales(request):
    """
    Endpoint: Tendencias nacionales por año (para gráfico de líneas).
    Retorna evolución de puntajes promedio por materia.
    CACHED: 24 horas
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


@cache_page(60 * 30)  # Cache 30 minutos
@require_http_methods(["GET"])
def api_comparacion_sectores_chart(request):
    """
    Endpoint: Comparación de sectores para gráfico de barras.
    Query params: ?ano=2023 (opcional)
    CACHED: 30 minutos
    """
    try:
        ano = int(request.GET.get('ano', 2023))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
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
        WHERE ano = ?
        GROUP BY sector
        ORDER BY sector
    """

    df = execute_query(query, params=[ano])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@cache_page(60 * 60)  # 1 hora - ranking departamental
@require_http_methods(["GET"])
def api_ranking_departamentos(request):
    """
    Endpoint: Ranking de departamentos para gráfico de barras.
    Query params: ?ano=2023&limit=10 (opcionales)
    CACHED: 1 hora
    """
    try:
        ano = int(request.GET.get('ano', 2023))
        limit = int(request.GET.get('limit', 10))
        limit = min(limit, 100)  # Limitar máximo
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

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
    return JsonResponse(data, safe=False)


@cache_page(60 * 60)  # Cache 1 hora
@require_http_methods(["GET"])
def api_distribucion_regional(request):
    """
    Endpoint: Distribución de estudiantes por región.
    Query params: ?ano=2023 (opcional)
    CACHED: 1 hora
    """
    try:
        ano = int(request.GET.get('ano', 2023))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
        SELECT
            region,
            SUM(total_estudiantes) as total_estudiantes,
            AVG(avg_punt_global) as promedio
        FROM gold.vw_fct_colegios_region
        WHERE ano = ? AND region IS NOT NULL
        GROUP BY region
        ORDER BY total_estudiantes DESC
    """

    df = execute_query(query, params=[ano])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def api_promedios_ubicacion(request):
    """
    Endpoint: Promedios por ubicación (departamento o municipio).
    Query params: ?ano=2024&departamento=BOGOTÁ D.C.&municipio=BOGOTA (opcionales)
    Retorna promedios para comparación en gauges.
    """
    ano = request.GET.get('ano', 2024)
    departamento = request.GET.get('departamento')
    municipio = request.GET.get('municipio')
    
    if not ano:
        return JsonResponse({'error': 'Parámetro ano es requerido'}, status=400)
    
    try:
        data = get_promedios_ubicacion(
            ano=int(ano),
            departamento=departamento,
            municipio=municipio
        )
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# ENDPOINTS API - HIERARCHICAL EXPLORER
# ============================================================================

@require_http_methods(["GET"])
def hierarchy_regions(request):
    """
    Endpoint: Regiones con estadísticas agregadas y Z-scores.
    Query params: ?ano=2024
    """
    try:
        ano = int(request.GET.get('ano', 2024))
        ano_anterior = ano - 1
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

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
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def hierarchy_departments(request):
    """
    Endpoint: Departamentos de una región con estadísticas y Z-scores.
    Query params: ?region=ANDINA&ano=2024
    """
    region = request.GET.get('region', '')
    if not region:
        return JsonResponse([], safe=False)

    try:
        ano = int(request.GET.get('ano', 2024))
        ano_anterior = ano - 1
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    # Obtener departamentos de la región desde la base de datos
    query_deptos = """
        SELECT DISTINCT departamento
        FROM gold.dim_colegios
        WHERE region = ?
        ORDER BY departamento
    """
    deptos_df = execute_query(query_deptos, params=[region])
    deptos = tuple(deptos_df['departamento'].tolist()) if not deptos_df.empty else ()

    if not deptos:
        return JsonResponse([], safe=False)

    query = """
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
            WHERE ano = ? AND region = ?
            GROUP BY departamento
        ),
        previous_year AS (
            SELECT
                departamento,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.vw_fct_colegios_region
            WHERE ano = ? AND region = ?
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

    df = execute_query(query, params=[ano, region, ano_anterior, region])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def hierarchy_municipalities(request):
    """
    Endpoint: Municipios de un departamento con estadísticas y Z-scores.
    Query params: ?department=CUNDINAMARCA&ano=2024
    """
    department = request.GET.get('department', '')
    if not department:
        return JsonResponse([], safe=False)

    try:
        ano = int(request.GET.get('ano', 2024))
        ano_anterior = ano - 1
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
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
            WHERE ano = ? AND departamento = ?
            GROUP BY municipio
        ),
        previous_year AS (
            SELECT
                municipio,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.fct_agg_colegios_ano
            WHERE ano = ? AND departamento = ?
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

    df = execute_query(query, params=[ano, department, ano_anterior, department])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def hierarchy_schools(request):
    """
    Endpoint: Colegios de un municipio con estadísticas y Z-scores.
    Query params: ?municipality=BOGOTA&ano=2024
    """
    municipality = request.GET.get('municipality', '')
    if not municipality:
        return JsonResponse([], safe=False)

    try:
        ano = int(request.GET.get('ano', 2024))
        ano_anterior = ano - 1
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
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
            WHERE ano = ? AND municipio = ?
            GROUP BY colegio_sk
        ),
        previous_year AS (
            SELECT
                colegio_sk,
                AVG(avg_punt_global) as punt_global_anterior
            FROM gold.fct_agg_colegios_ano
            WHERE ano = ? AND municipio = ?
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

    df = execute_query(query, params=[ano, municipality, ano_anterior, municipality])
    data = df.to_dict(orient='records')
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def hierarchy_history(request):
    """
    Endpoint: Historial de puntajes por materia para una entidad geográfica o colegio.
    Query params: ?level=region|department|municipality|school&id=<nombre_o_colegio_sk>
    Returns: [{ano, punt_global, punt_matematicas, punt_lectura, punt_c_naturales, punt_sociales, punt_ingles}]
    """
    level = request.GET.get('level', 'region')
    entity_id = request.GET.get('id', '').strip()

    if not entity_id:
        return JsonResponse([], safe=False)

    if level == 'region':
        query = """
            SELECT ano,
                AVG(avg_punt_global)              AS punt_global,
                AVG(avg_punt_matematicas)          AS punt_matematicas,
                AVG(avg_punt_lectura_critica)      AS punt_lectura,
                AVG(avg_punt_c_naturales)          AS punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas)  AS punt_sociales,
                AVG(avg_punt_ingles)               AS punt_ingles,
                SUM(total_estudiantes)             AS total_estudiantes
            FROM gold.vw_fct_colegios_region
            WHERE region = ? AND ano >= 2000
            GROUP BY ano ORDER BY ano
        """
    elif level == 'department':
        query = """
            SELECT ano,
                AVG(avg_punt_global)              AS punt_global,
                AVG(avg_punt_matematicas)          AS punt_matematicas,
                AVG(avg_punt_lectura_critica)      AS punt_lectura,
                AVG(avg_punt_c_naturales)          AS punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas)  AS punt_sociales,
                AVG(avg_punt_ingles)               AS punt_ingles,
                SUM(total_estudiantes)             AS total_estudiantes
            FROM gold.vw_fct_colegios_region
            WHERE departamento = ? AND ano >= 2000
            GROUP BY ano ORDER BY ano
        """
    elif level == 'municipality':
        query = """
            SELECT ano,
                AVG(avg_punt_global)              AS punt_global,
                AVG(avg_punt_matematicas)          AS punt_matematicas,
                AVG(avg_punt_lectura_critica)      AS punt_lectura,
                AVG(avg_punt_c_naturales)          AS punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas)  AS punt_sociales,
                AVG(avg_punt_ingles)               AS punt_ingles
            FROM gold.fct_agg_colegios_ano
            WHERE municipio = ? AND ano >= 2000
            GROUP BY ano ORDER BY ano
        """
    elif level == 'school':
        query = """
            SELECT ano,
                AVG(avg_punt_global)              AS punt_global,
                AVG(avg_punt_matematicas)          AS punt_matematicas,
                AVG(avg_punt_lectura_critica)      AS punt_lectura,
                AVG(avg_punt_c_naturales)          AS punt_c_naturales,
                AVG(avg_punt_sociales_ciudadanas)  AS punt_sociales,
                AVG(avg_punt_ingles)               AS punt_ingles
            FROM gold.fct_agg_colegios_ano
            WHERE colegio_sk = ? AND ano >= 2000
            GROUP BY ano ORDER BY ano
        """
    else:
        return JsonResponse({'error': 'Nivel no válido'}, status=400)

    try:
        df = execute_query(query, params=[entity_id])
        data = df.to_dict(orient='records')
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# ENDPOINTS API - SCHOOL INDIVIDUAL VIEW
# ============================================================================

@require_http_methods(['GET'])
def api_search_colegios(request):
    '''Búsqueda/autocomplete de colegios'''
    query_text = request.GET.get('q', '')

    if not query_text or len(query_text) < 3:
        return JsonResponse([], safe=False)

    try:
        limit = int(request.GET.get('limit', 20))
        limit = min(limit, 100)  # Limitar máximo
    except (ValueError, TypeError):
        limit = 20

    # Sanitizar el texto de búsqueda para LIKE (usar parámetros)
    search_pattern = f'%{query_text}%'

    query = '''
        SELECT DISTINCT colegio_sk, codigo_dane, nombre_colegio,
                departamento, municipio, sector
        FROM gold.fct_colegio_historico
        WHERE LOWER(nombre_colegio) LIKE LOWER(?)
           OR codigo_dane LIKE ?
        ORDER BY nombre_colegio LIMIT ?
    '''
    df = execute_query(query, params=[search_pattern, search_pattern, limit])
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_historico(request, colegio_sk):
    """Evolución histórica de un colegio"""
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    query = """
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
            WHERE colegio_sk = ?
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
    df = execute_query(query, params=[str(colegio_sk)])
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_correlaciones(request, colegio_sk):
    """Correlaciones entre materias y puntaje global"""
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    query = """
        SELECT *
        FROM gold.fct_colegio_correlaciones
        WHERE colegio_sk = ?
    """
    df = execute_query(query, params=[str(colegio_sk)])
    if df.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)
    return JsonResponse(df.to_dict(orient='records')[0], safe=False)


@require_http_methods(["GET"])
def api_colegio_fortalezas(request, colegio_sk):
    """Fortalezas y debilidades por materia"""
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    query = """
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
        WHERE colegio_sk = ?
        ORDER BY ano DESC
    """
    df = execute_query(query, params=[str(colegio_sk)])
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_comparacion(request, colegio_sk):
    """Comparación del colegio vs promedios (último año)"""
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    query = """
        WITH ultimo_ano AS (
            SELECT MAX(ano) as ano
            FROM gold.fct_colegio_historico
            WHERE colegio_sk = ?
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
            WHERE h.colegio_sk = ?
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
    colegio_sk_str = str(colegio_sk)
    df = execute_query(query, params=[colegio_sk_str, colegio_sk_str])
    if df.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)
    return JsonResponse(df.to_dict(orient='records')[0], safe=False)


@require_http_methods(["GET"])
def api_colegio_resumen(request, colegio_sk):
    """Resumen ejecutivo del colegio"""
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    colegio_sk_str = str(colegio_sk)

    # Información básica
    query_basico = """
        SELECT DISTINCT colegio_sk, codigo_dane, nombre_colegio,
               sector, departamento, municipio
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = ?
        LIMIT 1
    """

    # Último año
    query_ultimo = """
        WITH ultimo_ano AS (
            SELECT MAX(ano) as ano
            FROM gold.fct_colegio_historico
            WHERE colegio_sk = ?
        )
        SELECT h.ano, h.total_estudiantes, h.avg_punt_global,
               h.ranking_nacional, h.ranking_municipal,
               h.cambio_absoluto_global, h.cambio_porcentual_global,
               h.clasificacion_tendencia
        FROM gold.fct_colegio_historico h
        INNER JOIN ultimo_ano u ON h.ano = u.ano
        WHERE h.colegio_sk = ?
    """

    # Z-Score global (último año)
    query_zscore = """
        WITH ultimo_ano AS (
            SELECT MAX(ano) as ano
            FROM gold.fct_colegio_historico
            WHERE colegio_sk = ?
        ),
        stats_nacionales AS (
            SELECT
                AVG(avg_punt_global) as promedio_nacional,
                STDDEV(avg_punt_global) as desviacion_nacional
            FROM gold.fct_colegio_historico h
            INNER JOIN ultimo_ano u ON h.ano = u.ano
        ),
        colegio_data AS (
            SELECT avg_punt_global
            FROM gold.fct_colegio_historico h
            INNER JOIN ultimo_ano u ON h.ano = u.ano
            WHERE h.colegio_sk = ?
        )
        SELECT
            (c.avg_punt_global - s.promedio_nacional) / NULLIF(s.desviacion_nacional, 0) as z_score_global,
            s.promedio_nacional,
            s.desviacion_nacional
        FROM colegio_data c, stats_nacionales s
    """

    # Rango de años
    query_rango = """
        SELECT MIN(ano) as ano_inicio, MAX(ano) as ano_fin,
               COUNT(DISTINCT ano) as total_anos
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = ?
    """

    # Fortalezas/debilidades
    query_fd = """
        SELECT materias_por_encima_promedio, materias_por_debajo_promedio,
               clasificacion_general, perfil_rendimiento
        FROM gold.fct_colegio_fortalezas_debilidades
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    # Cluster Data
    query_cluster = """
        SELECT cluster_id, cluster_name
        FROM gold.dim_colegios_cluster
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    # Risk Data (P2 - Data Science)
    query_riesgo = """
        SELECT ano, prob_declive, nivel_riesgo, prediccion_declive,
               factores_principales
        FROM gold.fct_riesgo_colegios
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    try:
        df_basico = execute_query(query_basico, params=[colegio_sk_str])
        df_ultimo = execute_query(query_ultimo, params=[colegio_sk_str, colegio_sk_str])
        df_zscore = execute_query(query_zscore, params=[colegio_sk_str, colegio_sk_str])
        df_rango = execute_query(query_rango, params=[colegio_sk_str])
        df_fd = execute_query(query_fd, params=[colegio_sk_str])

        df_cluster = execute_query(query_cluster, params=[colegio_sk_str])
    except Exception as e:
        # Fallback partial loading if some non-critical queries fail
        import traceback
        traceback.print_exc()
        if 'df_basico' not in locals(): df_basico = pd.DataFrame()
        if 'df_ultimo' not in locals(): df_ultimo = pd.DataFrame()
        if 'df_zscore' not in locals(): df_zscore = pd.DataFrame()
        if 'df_rango' not in locals(): df_rango = pd.DataFrame()
        if 'df_fd' not in locals(): df_fd = pd.DataFrame()
        df_cluster = pd.DataFrame()

    # Risk query - separate try/catch (table may not exist in prod)
    df_riesgo = pd.DataFrame()
    try:
        df_riesgo = execute_query(query_riesgo, params=[colegio_sk_str])
    except Exception:
        pass

    if df_basico.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)

    # Build risk data
    riesgo_data = {}
    if not df_riesgo.empty:
        row_r = df_riesgo.iloc[0]
        factores = []
        try:
            factores = json.loads(row_r['factores_principales']) if row_r['factores_principales'] else []
        except (json.JSONDecodeError, TypeError):
            pass
        riesgo_data = {
            'ano': int(row_r['ano']),
            'prob_declive': round(float(row_r['prob_declive']), 3),
            'nivel_riesgo': row_r['nivel_riesgo'],
            'factores_principales': factores,
        }

    resumen = {
        'info_basica': df_basico.to_dict(orient='records')[0],
        'ultimo_ano': df_ultimo.to_dict(orient='records')[0] if not df_ultimo.empty else {},
        'z_score': df_zscore.to_dict(orient='records')[0] if not df_zscore.empty else {},
        'rango_historico': df_rango.to_dict(orient='records')[0] if not df_rango.empty else {},
        'analisis': df_fd.to_dict(orient='records')[0] if not df_fd.empty else {},
        'cluster': df_cluster.to_dict(orient='records')[0] if not df_cluster.empty else {},
        'riesgo': riesgo_data,
    }

    return JsonResponse(resumen, safe=False)


@require_http_methods(["GET"])
def api_colegio_ai_recommendations(request, colegio_sk):
    """Generate AI-powered recommendations for school improvement using Anthropic Claude"""
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    colegio_sk_str = str(colegio_sk)

    try:
        # Get school data
        historico_query = """
            SELECT * FROM gold.fct_colegio_historico
            WHERE colegio_sk = ?
            ORDER BY ano DESC LIMIT 5
        """
        historico = execute_query(historico_query, params=[colegio_sk_str])

        fortalezas_query = """
            SELECT * FROM gold.fct_colegio_fortalezas_debilidades
            WHERE colegio_sk = ?
            ORDER BY ano DESC LIMIT 1
        """
        fortalezas = execute_query(fortalezas_query, params=[colegio_sk_str])

        # NEW: Get excellence indicators
        indicadores_query = """
            WITH indicadores_colegio AS (
                SELECT
                    i.ano,
                    i.pct_excelencia_integral,
                    i.pct_competencia_satisfactoria_integral,
                    i.pct_perfil_stem_avanzado,
                    i.pct_perfil_humanistico_avanzado,
                    i.total_estudiantes
                FROM gold.fct_indicadores_desempeno i
                WHERE i.colegio_bk = (SELECT DISTINCT codigo_dane FROM gold.fct_colegio_historico WHERE colegio_sk = ? LIMIT 1)
            ),
            promedios_nacionales AS (
                SELECT
                    ano,
                    AVG(pct_excelencia_integral) as nacional_excelencia,
                    AVG(pct_competencia_satisfactoria_integral) as nacional_competencia,
                    AVG(pct_perfil_stem_avanzado) as nacional_stem,
                    AVG(pct_perfil_humanistico_avanzado) as nacional_humanistico
                FROM gold.fct_indicadores_desempeno
                GROUP BY ano
            )
            SELECT
                ic.ano,
                ic.pct_excelencia_integral,
                ic.pct_competencia_satisfactoria_integral,
                ic.pct_perfil_stem_avanzado,
                ic.pct_perfil_humanistico_avanzado,
                ic.total_estudiantes,
                pn.nacional_excelencia,
                pn.nacional_competencia,
                pn.nacional_stem,
                pn.nacional_humanistico
            FROM indicadores_colegio ic
            LEFT JOIN promedios_nacionales pn ON ic.ano = pn.ano
            ORDER BY ic.ano DESC
            LIMIT 3
        """
        
        # Try to get excellence indicators (may not exist for all schools)
        try:
            indicadores = execute_query(indicadores_query, params=[colegio_sk_str])
        except Exception as e:
            print(f"Warning: Could not fetch indicators for {colegio_sk}: {e}")
            indicadores = pd.DataFrame()  # Empty dataframe
        
        # Validate that we have at least historical data
        if historico.empty:
            return JsonResponse({
                'error': 'No se encontraron datos históricos para este colegio',
                'message': 'Este colegio no tiene datos suficientes en la base de datos para generar recomendaciones.',
                'colegio_sk': colegio_sk
            }, status=404)
        
        # Prepare data for AI
        school_data = {
            'historical_performance': historico.to_dict(orient='records'),
            'strengths_weaknesses': fortalezas.to_dict(orient='records')[0] if not fortalezas.empty else {},
            'excellence_indicators': indicadores.to_dict(orient='records') if not indicadores.empty else []
        }
        
        # Check if Anthropic API key is configured
        from django.conf import settings
        if not hasattr(settings, 'ANTHROPIC_API_KEY') or not settings.ANTHROPIC_API_KEY:
            return JsonResponse({
                'error': 'API de IA no configurada',
                'message': 'La API key de Anthropic Claude no está configurada.',
                'instrucciones': {
                    'paso_1': 'Obtén tu API key en https://console.anthropic.com/',
                    'paso_2': 'En PowerShell ejecuta: $env:ANTHROPIC_API_KEY = "sk-ant-api03-TU-KEY-AQUI"',
                    'paso_3': 'Reinicia el servidor Django',
                    'documentacion': 'Ver setup_api_key.md para más detalles'
                },
                'nota': 'Las recomendaciones de IA estarán disponibles una vez configurada la API key'
            }, status=503)
        
        # Call Anthropic Claude API
        import anthropic
        
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        prompt = f"""Analiza el siguiente colegio colombiano basado en sus resultados ICFES y sus indicadores de excelencia académica:

DATOS HISTÓRICOS (últimos 5 años):
{json.dumps(school_data['historical_performance'], indent=2, ensure_ascii=False)}

FORTALEZAS Y DEBILIDADES ACTUALES:
{json.dumps(school_data['strengths_weaknesses'], indent=2, ensure_ascii=False)}

INDICADORES DE EXCELENCIA ACADÉMICA (últimos 3 años):
{json.dumps(school_data['excellence_indicators'], indent=2, ensure_ascii=False)}

CONTEXTO DE LOS INDICADORES DE EXCELENCIA:
- pct_excelencia_integral: % de estudiantes con nivel 4 (avanzado) en TODAS las materias
- pct_competencia_satisfactoria_integral: % de estudiantes con nivel 3+ (satisfactorio o superior) en TODAS las materias
- pct_perfil_stem_avanzado: % de estudiantes con nivel 4 en Matemáticas Y Ciencias Naturales
- pct_perfil_humanistico_avanzado: % de estudiantes con nivel 4 en Lectura Crítica Y Sociales
- nacional_*: Promedio nacional del indicador correspondiente

ANÁLISIS REQUERIDO:
Proporciona un análisis estratégico y detallado en formato JSON con la siguiente estructura:
{{
    "evaluacion_general": "Evaluación general del colegio en 2-3 párrafos. DEBE incluir análisis de los indicadores de excelencia y cómo se comparan con el promedio nacional. Menciona específicamente los porcentajes de excelencia integral, competencia satisfactoria, y perfiles STEM/Humanístico.",
    
    "fortalezas": [
        "Fortaleza 1 (debe ser específica, con datos numéricos si es posible)",
        "Fortaleza 2",
        "Fortaleza 3",
        "Fortaleza 4",
        "Fortaleza 5"
    ],
    
    "debilidades": [
        "Debilidad 1 (debe ser específica, con datos numéricos si es posible)",
        "Debilidad 2",
        "Debilidad 3",
        "Debilidad 4",
        "Debilidad 5"
    ],
    
    "estrategias_5_puntos": [
        "Estrategia específica 1 para aumentar 5 puntos en el puntaje global. DEBE considerar los indicadores de excelencia y ser muy específica sobre qué hacer.",
        "Estrategia específica 2 (puede enfocarse en aumentar el % de excelencia integral o competencia satisfactoria)",
        "Estrategia específica 3 (puede enfocarse en fortalecer perfil STEM o Humanístico según necesidad)",
        "Estrategia específica 4",
        "Estrategia específica 5"
    ],
    
    "recomendaciones_materias": {{
        "Matemáticas": "Recomendación específica para matemáticas. Si el perfil STEM es bajo, enfócate en cómo mejorarlo.",
        "Lectura Crítica": "Recomendación específica para lectura. Si el perfil humanístico es bajo, enfócate en cómo mejorarlo.",
        "Ciencias Naturales": "Recomendación específica para ciencias. Relaciona con perfil STEM.",
        "Sociales": "Recomendación específica para sociales. Relaciona con perfil humanístico.",
        "Inglés": "Recomendación específica para inglés."
    }},
    
    "plan_accion": "Plan de acción prioritario detallado en 2-3 párrafos con pasos concretos. DEBE incluir metas específicas para mejorar los indicadores de excelencia (ej: 'aumentar excelencia integral de X% a Y% en 1 año', 'incrementar perfil STEM de A% a B%'). Prioriza acciones de alto impacto.",
    
    "metas_indicadores_excelencia": {{
        "excelencia_integral": {{
            "actual": "X.X%",
            "meta_1_ano": "Y.Y%",
            "justificacion": "Explicación de por qué esta meta es alcanzable y cómo lograrla"
        }},
        "competencia_satisfactoria": {{
            "actual": "X.X%",
            "meta_1_ano": "Y.Y%",
            "justificacion": "Explicación"
        }},
        "perfil_prioritario": "STEM o Humanístico (el que necesite más atención)",
        "acciones_perfil_prioritario": [
            "Acción específica 1",
            "Acción específica 2",
            "Acción específica 3"
        ]
    }}
}}

INSTRUCCIONES CRÍTICAS:
1. Las recomendaciones DEBEN ser específicas y accionables, no genéricas
2. DEBES usar los datos numéricos proporcionados (porcentajes, puntajes, rankings)
3. Las estrategias DEBEN considerar los indicadores de excelencia académica
4. Prioriza acciones que aumenten la excelencia integral y competencia satisfactoria
5. Si el colegio está por debajo del promedio nacional en algún indicador, enfócate en cómo mejorarlo
6. Si el colegio está por encima, enfócate en cómo mantener y ampliar la ventaja
7. Contextualiza al sistema educativo colombiano (ICFES, niveles de desempeño, etc.)
8. Las metas deben ser ambiciosas pero realistas (típicamente +2-5% anual en indicadores de excelencia)

Responde ÚNICAMENTE con el JSON, sin texto adicional."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,  # Maximum recommended for complete detailed responses
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
        try:
            ai_response = json.loads(response_text)
            return JsonResponse(ai_response)
        except json.JSONDecodeError as e:
            # Log the actual response for debugging
            print(f"\n{'='*80}")
            print("ERROR: Failed to parse Claude response as JSON")
            print(f"{'='*80}")
            print(f"Error: {str(e)}")
            print(f"\nRaw response from Claude:")
            print(response_text)
            print(f"{'='*80}\n")
            
            return JsonResponse({
                'error': 'Error al parsear respuesta de IA',
                'details': f'La IA no respondió en formato JSON válido. Error: {str(e)}',
                'raw_response': response_text[:1000]  # Show more of the response
            }, status=500)
        
    except Exception as e:
        print(f"\n{'='*80}")
        print("ERROR: Unexpected error in AI recommendations")
        print(f"{'='*80}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        
        return JsonResponse({
            'error': 'Error al generar recomendaciones',
            'details': f'{type(e).__name__}: {str(e)}'
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
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    ano = request.GET.get('ano')
    params = [str(colegio_sk)]

    # Construir query base
    query_base = """
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
        WHERE colegio_sk = ?
    """

    # Agregar filtro de año si se especifica
    if ano:
        try:
            ano_int = int(ano)
            query_base += " AND ano = ?"
            params.append(ano_int)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = query_base + " ORDER BY ano DESC"

    df = execute_query(query, params=params)

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
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    ano = request.GET.get('ano')

    if not ano:
        return JsonResponse({'error': 'Parámetro ano es requerido'}, status=400)

    try:
        ano_int = int(ano)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
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
        WHERE colegio_sk = ?
            AND ano = ?
    """

    df = execute_query(query, params=[str(colegio_sk), ano_int])

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


@require_http_methods(["GET"])
def api_colegio_indicadores_excelencia(request, colegio_sk):
    """
    Endpoint: Indicadores de Excelencia Académica por colegio.
    Retorna los 4 indicadores clave + Riesgo Alto.
    
    NOTA: Se calcula dinámicamente desde fact_icfes_analytics porque
    la tabla pre-calculada fct_indicadores_desempeno aún no existe.
    Los rankings y promedios nacionales se retornan en 0 temporalmente.
    """
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    ano = request.GET.get('ano')
    colegio_sk_str = str(colegio_sk)
    params = [colegio_sk_str]

    # Construir parte condicional del query
    ano_filter = ""
    if ano:
        try:
            ano_int = int(ano)
            ano_filter = "AND ano = ?"
            params.append(ano_int)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    # Query para calcular indicadores al vuelo
    query = f"""
        SELECT
            ano,
            COUNT(*) as total_estudiantes,
            
            -- Excelencia Integral: Nivel 4 (>70) en TODAS las materias
            SUM(CASE WHEN 
                punt_matematicas > 70 AND 
                punt_lectura_critica > 70 AND
                punt_c_naturales > 70 AND
                punt_sociales_ciudadanas > 70 AND
                punt_ingles > 70
            THEN 1 ELSE 0 END) as count_excelencia,
            
            -- Competencia Satisfactoria: Nivel 3+ (>55) en TODAS las materias
            SUM(CASE WHEN 
                punt_matematicas > 55 AND 
                punt_lectura_critica > 55 AND
                punt_c_naturales > 55 AND
                punt_sociales_ciudadanas > 55 AND
                punt_ingles > 55
            THEN 1 ELSE 0 END) as count_satisfactoria,
            
            -- Perfil STEM Avanzado: Nivel 4 (>70) en Matematicas y Ciencias
            SUM(CASE WHEN 
                punt_matematicas > 70 AND 
                punt_c_naturales > 70
            THEN 1 ELSE 0 END) as count_stem,
            
            -- Perfil Humanístico Avanzado: Nivel 4 (>70) en Lectura y Sociales
            SUM(CASE WHEN 
                punt_lectura_critica > 70 AND 
                punt_sociales_ciudadanas > 70
            THEN 1 ELSE 0 END) as count_humanistico,
            
            -- Riesgo Alto: Nivel 1 (<=40) en 2+ materias
            SUM(CASE WHEN (
                (CASE WHEN punt_matematicas <= 40 THEN 1 ELSE 0 END) +
                (CASE WHEN punt_lectura_critica <= 40 THEN 1 ELSE 0 END) +
                (CASE WHEN punt_c_naturales <= 40 THEN 1 ELSE 0 END) +
                (CASE WHEN punt_sociales_ciudadanas <= 40 THEN 1 ELSE 0 END) +
                (CASE WHEN punt_ingles <= 40 THEN 1 ELSE 0 END)
            ) >= 2 THEN 1 ELSE 0 END) as count_riesgo

        FROM gold.fact_icfes_analytics
        WHERE colegio_sk = ?
        {ano_filter}
        GROUP BY ano
        ORDER BY ano DESC
        LIMIT 5
    """

    try:
        df = execute_query(query, params=params)

        if df.empty:
            return JsonResponse([], safe=False)

        # Procesar resultados y calcular porcentajes
        results = []
        for _, row in df.iterrows():
            total = row['total_estudiantes']
            if total == 0: continue

            item = {
                'ano': int(row['ano']),
                'colegio_bk': colegio_sk, # Placeholder
                'total_estudiantes': int(total),
                
                # Indicadores calculados
                'pct_excelencia_integral': round(row['count_excelencia'] / total * 100, 2),
                'pct_competencia_satisfactoria_integral': round(row['count_satisfactoria'] / total * 100, 2),
                'pct_perfil_stem_avanzado': round(row['count_stem'] / total * 100, 2),
                'pct_perfil_humanistico_avanzado': round(row['count_humanistico'] / total * 100, 2),
                'pct_riesgo_alto': round(row['count_riesgo'] / total * 100, 2),
                
                # Placeholders para comparación nacional (no disponible sin tabla agregada)
                'nacional_excelencia': 0,
                'nacional_competencia': 0,
                'nacional_stem': 0,
                'nacional_humanistico': 0,
                'nacional_riesgo': 0,
                
                # Placeholders para rankings
                'ranking_excelencia': 0,
                'ranking_competencia': 0,
                'ranking_stem': 0,
                'ranking_humanistico': 0,
                'ranking_riesgo': 0
            }
            results.append(item)

        return JsonResponse(results, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'Error calculando indicadores',
            'details': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_colegio_distribucion_niveles(request, colegio_sk):
    """
    Endpoint: Distribución de estudiantes por nivel de desempeño (1-4) para cada materia.
    Usado para gráficas de torta/donut estilo ICFES Saber 11.

    Query params: ?ano=2023&materia=todas (opcional)

    Niveles de desempeño ICFES:
    - Nivel 1: Puntaje 0-40 (Insuficiente)
    - Nivel 2: Puntaje 41-55 (Mínimo)
    - Nivel 3: Puntaje 56-70 (Satisfactorio)
    - Nivel 4: Puntaje 71-100 (Avanzado)

    Returns:
    {
        "ano": 2023,
        "total_estudiantes": 150,
        "materias": {
            "matematicas": {
                "nivel_1": {"cantidad": 10, "porcentaje": 6.67},
                "nivel_2": {"cantidad": 40, "porcentaje": 26.67},
                "nivel_3": {"cantidad": 70, "porcentaje": 46.67},
                "nivel_4": {"cantidad": 30, "porcentaje": 20.0}
            },
            ...
        }
    }
    """
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    ano = request.GET.get('ano')
    colegio_sk_str = str(colegio_sk)

    # Construir filtro de año
    ano_filter = ""
    params = [colegio_sk_str]
    if ano:
        try:
            ano_int = int(ano)
            ano_filter = "AND f.ano = ?"
            params.append(ano_int)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    # Query para calcular distribución de niveles por materia
    # Los niveles se calculan según rangos de puntaje ICFES
    query = f"""
        WITH estudiantes_colegio AS (
            SELECT
                f.ano,
                f.punt_matematicas,
                f.punt_lectura_critica,
                f.punt_c_naturales,
                f.punt_sociales_ciudadanas,
                f.punt_ingles,
                f.punt_global
            FROM gold.fact_icfes_analytics f
            WHERE f.colegio_sk = ?
            {ano_filter}
        ),
        niveles_calculados AS (
            SELECT
                ano,
                -- Matemáticas
                CASE
                    WHEN punt_matematicas <= 40 THEN 1
                    WHEN punt_matematicas <= 55 THEN 2
                    WHEN punt_matematicas <= 70 THEN 3
                    ELSE 4
                END as nivel_matematicas,
                -- Lectura Crítica
                CASE
                    WHEN punt_lectura_critica <= 40 THEN 1
                    WHEN punt_lectura_critica <= 55 THEN 2
                    WHEN punt_lectura_critica <= 70 THEN 3
                    ELSE 4
                END as nivel_lectura,
                -- Ciencias Naturales
                CASE
                    WHEN punt_c_naturales <= 40 THEN 1
                    WHEN punt_c_naturales <= 55 THEN 2
                    WHEN punt_c_naturales <= 70 THEN 3
                    ELSE 4
                END as nivel_naturales,
                -- Sociales y Ciudadanas
                CASE
                    WHEN punt_sociales_ciudadanas <= 40 THEN 1
                    WHEN punt_sociales_ciudadanas <= 55 THEN 2
                    WHEN punt_sociales_ciudadanas <= 70 THEN 3
                    ELSE 4
                END as nivel_sociales,
                -- Inglés
                CASE
                    WHEN punt_ingles <= 40 THEN 1
                    WHEN punt_ingles <= 55 THEN 2
                    WHEN punt_ingles <= 70 THEN 3
                    ELSE 4
                END as nivel_ingles,
                -- Global
                CASE
                    WHEN punt_global <= 160 THEN 1
                    WHEN punt_global <= 220 THEN 2
                    WHEN punt_global <= 280 THEN 3
                    ELSE 4
                END as nivel_global
            FROM estudiantes_colegio
        )
        SELECT
            MAX(ano) as ano,
            COUNT(*) as total_estudiantes,

            -- Matemáticas
            SUM(CASE WHEN nivel_matematicas = 1 THEN 1 ELSE 0 END) as mat_nivel_1,
            SUM(CASE WHEN nivel_matematicas = 2 THEN 1 ELSE 0 END) as mat_nivel_2,
            SUM(CASE WHEN nivel_matematicas = 3 THEN 1 ELSE 0 END) as mat_nivel_3,
            SUM(CASE WHEN nivel_matematicas = 4 THEN 1 ELSE 0 END) as mat_nivel_4,

            -- Lectura Crítica
            SUM(CASE WHEN nivel_lectura = 1 THEN 1 ELSE 0 END) as lec_nivel_1,
            SUM(CASE WHEN nivel_lectura = 2 THEN 1 ELSE 0 END) as lec_nivel_2,
            SUM(CASE WHEN nivel_lectura = 3 THEN 1 ELSE 0 END) as lec_nivel_3,
            SUM(CASE WHEN nivel_lectura = 4 THEN 1 ELSE 0 END) as lec_nivel_4,

            -- Ciencias Naturales
            SUM(CASE WHEN nivel_naturales = 1 THEN 1 ELSE 0 END) as nat_nivel_1,
            SUM(CASE WHEN nivel_naturales = 2 THEN 1 ELSE 0 END) as nat_nivel_2,
            SUM(CASE WHEN nivel_naturales = 3 THEN 1 ELSE 0 END) as nat_nivel_3,
            SUM(CASE WHEN nivel_naturales = 4 THEN 1 ELSE 0 END) as nat_nivel_4,

            -- Sociales y Ciudadanas
            SUM(CASE WHEN nivel_sociales = 1 THEN 1 ELSE 0 END) as soc_nivel_1,
            SUM(CASE WHEN nivel_sociales = 2 THEN 1 ELSE 0 END) as soc_nivel_2,
            SUM(CASE WHEN nivel_sociales = 3 THEN 1 ELSE 0 END) as soc_nivel_3,
            SUM(CASE WHEN nivel_sociales = 4 THEN 1 ELSE 0 END) as soc_nivel_4,

            -- Inglés
            SUM(CASE WHEN nivel_ingles = 1 THEN 1 ELSE 0 END) as ing_nivel_1,
            SUM(CASE WHEN nivel_ingles = 2 THEN 1 ELSE 0 END) as ing_nivel_2,
            SUM(CASE WHEN nivel_ingles = 3 THEN 1 ELSE 0 END) as ing_nivel_3,
            SUM(CASE WHEN nivel_ingles = 4 THEN 1 ELSE 0 END) as ing_nivel_4,

            -- Global
            SUM(CASE WHEN nivel_global = 1 THEN 1 ELSE 0 END) as glo_nivel_1,
            SUM(CASE WHEN nivel_global = 2 THEN 1 ELSE 0 END) as glo_nivel_2,
            SUM(CASE WHEN nivel_global = 3 THEN 1 ELSE 0 END) as glo_nivel_3,
            SUM(CASE WHEN nivel_global = 4 THEN 1 ELSE 0 END) as glo_nivel_4
        FROM niveles_calculados
    """

    df = execute_query(query, params=params)

    if df.empty or df.iloc[0]['total_estudiantes'] == 0:
        return JsonResponse({'error': 'No se encontraron datos para este colegio'}, status=404)

    row = df.iloc[0]
    total = int(row['total_estudiantes'])

    def build_nivel_data(prefix):
        """Construye datos de nivel con cantidad y porcentaje."""
        return {
            'nivel_1': {
                'cantidad': int(row[f'{prefix}_nivel_1']),
                'porcentaje': round(row[f'{prefix}_nivel_1'] / total * 100, 2)
            },
            'nivel_2': {
                'cantidad': int(row[f'{prefix}_nivel_2']),
                'porcentaje': round(row[f'{prefix}_nivel_2'] / total * 100, 2)
            },
            'nivel_3': {
                'cantidad': int(row[f'{prefix}_nivel_3']),
                'porcentaje': round(row[f'{prefix}_nivel_3'] / total * 100, 2)
            },
            'nivel_4': {
                'cantidad': int(row[f'{prefix}_nivel_4']),
                'porcentaje': round(row[f'{prefix}_nivel_4'] / total * 100, 2)
            }
        }

    result = {
        'ano': int(row['ano']) if row['ano'] else None,
        'total_estudiantes': total,
        'materias': {
            'matematicas': build_nivel_data('mat'),
            'lectura_critica': build_nivel_data('lec'),
            'ciencias_naturales': build_nivel_data('nat'),
            'sociales_ciudadanas': build_nivel_data('soc'),
            'ingles': build_nivel_data('ing'),
            'global': build_nivel_data('glo')
        },
        'niveles_info': {
            'nivel_1': {'nombre': 'Insuficiente', 'rango': '0-40', 'color': '#E74C3C'},
            'nivel_2': {'nombre': 'Mínimo', 'rango': '41-55', 'color': '#F39C12'},
            'nivel_3': {'nombre': 'Satisfactorio', 'rango': '56-70', 'color': '#F1C40F'},
            'nivel_4': {'nombre': 'Avanzado', 'rango': '71-100', 'color': '#27AE60'}
        }
    }

    return JsonResponse(result, safe=False)


# ============================================================================
# ENDPOINTS API - MAPA GEOGRÁFICO
# ============================================================================

@require_http_methods(["GET"])
def api_mapa_estudiantes_heatmap(request):
    """
    Retorna datos agregados de estudiantes para visualización en heatmap.
    Agrupa por cuadrícula geográfica (~1km) para performance y privacidad.

    Query params:
    - ano: Año de evaluación (default: 2024)
    - categoria: excelencia_integral, perfil_stem, perfil_humanistico, perfil_bilingue, riesgo_alto, critico_ingles, todos (default: excelencia_integral)
    - tipo_ubicacion: colegio (ubicación del colegio), residencia (residencia del estudiante) (default: colegio)
    - departamento: Filtro opcional por departamento
    - municipio: Filtro opcional por municipio

    Returns:
    {
        "type": "heatmap",
        "data": [[lat, lon, intensity], ...],
        "stats": {
            "total_estudiantes": int,
            "max_concentracion": int,
            "zonas_alta_concentracion": int,
            "total_celdas": int
        }
    }
    """
    # Validar parámetros
    try:
        ano = int(request.GET.get('ano', 2024))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    categoria = request.GET.get('categoria', 'excelencia_integral')
    # Validar categoria contra lista permitida
    categorias_validas = ['excelencia_integral', 'perfil_stem', 'perfil_humanistico',
                          'perfil_bilingue', 'riesgo_alto', 'critico_ingles', 'todos']
    if categoria not in categorias_validas:
        categoria = 'excelencia_integral'

    departamento = request.GET.get('departamento', None)
    municipio = request.GET.get('municipio', None)
    tipo_ubicacion = request.GET.get('tipo_ubicacion', 'colegio')

    # Validar tipo_ubicacion
    if tipo_ubicacion not in ['colegio', 'residencia']:
        tipo_ubicacion = 'colegio'

    # Determine which coordinates to use (from fact_icfes_analytics)
    if tipo_ubicacion == 'residencia':
        lat_field = 'f.latitud_reside'
        lon_field = 'f.longitud_reside'
        dept_field = 'f.departamento'
        muni_field = 'f.municipio'
    else:  # 'colegio' (default)
        lat_field = 'f.latitud_presentacion'
        lon_field = 'f.longitud_presentacion'
        dept_field = 'f.departamento'
        muni_field = 'f.municipio'

    # Build WHERE clause for filters using parameterized queries
    params = [ano]
    where_clauses = ["f.ano = ?"]

    if departamento:
        where_clauses.append(f"{dept_field} = ?")
        params.append(departamento)
    if municipio:
        where_clauses.append(f"{muni_field} = ?")
        params.append(municipio)
    
    where_sql = " AND ".join(where_clauses)
    
    # Build category condition based on performance levels
    if categoria == 'excelencia_integral':
        # Level 4 in all subjects
        categoria_condition = """
            f.desempeno_lectura_critica = 4 
            AND f.desempeno_matematicas = 4 
            AND f.desempeno_sociales_ciudadanas = 4 
            AND f.desempeno_c_naturales = 4 
            AND f.desempeno_ingles = 4
        """
    elif categoria == 'perfil_stem':
        # Level 4 in Math and Sciences
        categoria_condition = """
            f.desempeno_matematicas = 4 
            AND f.desempeno_c_naturales = 4
        """
    elif categoria == 'perfil_humanistico':
        # Level 4 in Reading and Social Studies
        categoria_condition = """
            f.desempeno_lectura_critica = 4 
            AND f.desempeno_sociales_ciudadanas = 4
        """
    elif categoria == 'perfil_bilingue':
        # Level 4 in English (advanced bilingual profile)
        categoria_condition = """
            f.desempeno_ingles = 4
        """
    elif categoria == 'riesgo_alto':
        # Level 1 in 2 or more subjects
        categoria_condition = """
            (CASE WHEN f.desempeno_lectura_critica = 1 THEN 1 ELSE 0 END +
             CASE WHEN f.desempeno_matematicas = 1 THEN 1 ELSE 0 END +
             CASE WHEN f.desempeno_sociales_ciudadanas = 1 THEN 1 ELSE 0 END +
             CASE WHEN f.desempeno_c_naturales = 1 THEN 1 ELSE 0 END +
             CASE WHEN f.desempeno_ingles = 1 THEN 1 ELSE 0 END) >= 2
        """
    elif categoria == 'critico_ingles':
        # Level 1 in English (critical need for English academies)
        categoria_condition = """
            f.desempeno_ingles = 1
        """
    else:  # 'todos'
        categoria_condition = "1=1"
    
    # Special handling for San Andrés - filter out erroneous continental coordinates
    # San Andrés should only show coordinates in the Caribbean (12-13.5°N, -82 to -81°W)
    san_andres_filter = ""
    if departamento and 'Archipiélago' in departamento:
        san_andres_filter = f"""
              AND {lat_field} BETWEEN 12.0 AND 13.5
              AND {lon_field} BETWEEN -82.0 AND -81.0
        """

    # Build dynamic WHERE clause
    where_sql = " AND ".join(where_clauses)

    # Main query: aggregate students by geographic grid
    # Note: lat_field/lon_field are safe - derived from validated tipo_ubicacion
    query = f"""
        WITH estudiantes_ubicados AS (
            SELECT
                {lat_field},
                {lon_field},
                ROUND(CAST({lat_field} AS DOUBLE), 2) as lat_grid,
                ROUND(CAST({lon_field} AS DOUBLE), 2) as lon_grid
            FROM gold.fact_icfes_analytics f
            WHERE {where_sql}
              AND {lat_field} IS NOT NULL
              AND {lon_field} IS NOT NULL
              AND CAST({lat_field} AS DOUBLE) BETWEEN -4.5 AND 13.5
              AND CAST({lon_field} AS DOUBLE) BETWEEN -82 AND -66
              {san_andres_filter}
              AND ({categoria_condition})
        )
        SELECT
            lat_grid,
            lon_grid,
            COUNT(*) as count
        FROM estudiantes_ubicados
        GROUP BY lat_grid, lon_grid
        HAVING COUNT(*) >= 3  -- Minimum 3 students per cell (privacy)
        ORDER BY count DESC
    """

    try:
        df = execute_query(query, params=params)
        
        # Format for Leaflet.heat: [[lat, lon, intensity], ...]
        heatmap_data = [
            [float(row['lat_grid']), float(row['lon_grid']), int(row['count'])]
            for _, row in df.iterrows()
        ]
        
        # Calculate statistics
        total_estudiantes = int(df['count'].sum()) if not df.empty else 0
        max_concentracion = int(df['count'].max()) if not df.empty else 0
        zonas_concentracion = len(df[df['count'] >= 10]) if not df.empty else 0
        
        return JsonResponse({
            'type': 'heatmap',
            'data': heatmap_data,
            'stats': {
                'total_estudiantes': total_estudiantes,
                'max_concentracion': max_concentracion,
                'zonas_alta_concentracion': zonas_concentracion,
                'total_celdas': len(df)
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'Error al generar mapa de calor',
            'details': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_mapa_departamentos(request):
    """
    Retorna lista de departamentos con conteo de estudiantes.

    Query params:
    - ano: Año de evaluación (default: 2024)

    Returns:
    [
        {"departamento": "BOGOTÁ D.C.", "total_estudiantes": 12345},
        ...
    ]
    """
    try:
        ano = int(request.GET.get('ano', 2024))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    query = """
        SELECT
            f.departamento,
            COUNT(*) as total_estudiantes
        FROM gold.fact_icfes_analytics f
        WHERE f.ano = ?
          AND f.departamento IS NOT NULL
          AND f.departamento != ''
        GROUP BY f.departamento
        ORDER BY total_estudiantes DESC
    """

    try:
        df = execute_query(query, params=[ano])
        data = df.to_dict(orient='records')
        return JsonResponse(data, safe=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'Error al obtener departamentos',
            'details': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_mapa_municipios(request):
    """
    Retorna lista de municipios filtrados por departamento.

    Query params:
    - ano: Año de evaluación (default: 2024)
    - departamento: Departamento para filtrar (requerido)

    Returns:
    [
        {"municipio": "BOGOTÁ D.C.", "total_estudiantes": 12345},
        ...
    ]
    """
    try:
        ano = int(request.GET.get('ano', 2024))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    departamento = request.GET.get('departamento')

    if not departamento:
        return JsonResponse({
            'error': 'Parámetro departamento es requerido'
        }, status=400)

    query = """
        SELECT
            f.municipio,
            COUNT(*) as total_estudiantes
        FROM gold.fact_icfes_analytics f
        WHERE f.ano = ?
          AND f.departamento = ?
          AND f.municipio IS NOT NULL
          AND f.municipio != ''
        GROUP BY f.municipio
        ORDER BY total_estudiantes DESC
    """

    try:
        df = execute_query(query, params=[ano, departamento])
        data = df.to_dict(orient='records')
        return JsonResponse(data, safe=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'Error al obtener municipios',
            'details': str(e)
        }, status=500)


# ============================================================================
# ENDPOINTS API - SCHOOL COMPARISON
# ============================================================================

@require_http_methods(["GET"])
def api_comparar_colegios(request):
    """
    Endpoint: Comparar dos colegios lado a lado.
    Query params: ?colegio_a_sk=xxx&colegio_b_sk=yyy&ano=2024
    """

    colegio_a_sk = request.GET.get('colegio_a_sk')
    colegio_b_sk = request.GET.get('colegio_b_sk')

    if not colegio_a_sk or not colegio_b_sk:
        return JsonResponse({
            'error': 'Parámetros faltantes',
            'message': 'Se requieren colegio_a_sk y colegio_b_sk'
        }, status=400)

    # Validar colegio_sk
    if not str(colegio_a_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_a_sk inválido'}, status=400)
    if not str(colegio_b_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_b_sk inválido'}, status=400)

    try:
        ano = int(request.GET.get('ano', 2024))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parámetro ano inválido'}, status=400)

    try:
        from .db_utils import get_comparacion_colegios
        data = get_comparacion_colegios(str(colegio_a_sk), str(colegio_b_sk), ano)

        if 'error' in data:
            return JsonResponse(data, status=404)

        return JsonResponse(data, safe=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'Error al comparar colegios',
            'details': str(e)
        }, status=500)



# ============================================================================
# ENDPOINT API - DISTRIBUCIÓN NIVELES DESEMPEÑO
# ============================================================================

@require_http_methods(["GET"])
def api_colegio_distribucion_niveles(request, colegio_sk):
    """
    Endpoint: Distribución de estudiantes por niveles de desempeño (1-4).
    Calculado dinámicamente desde gold.fact_icfes_analytics.
    """
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)

    try:
        ano = int(request.GET.get('ano', 2023))
    except (ValueError, TypeError):
        # Default to latest year if invalid
        ano = 2023

    # Query to get distribution counts
    query = """
        SELECT
            COUNT(*) as total_estudiantes,
            
            -- Matemáticas
            COUNT(CASE WHEN punt_matematicas <= 40 THEN 1 END) as mat_1,
            COUNT(CASE WHEN punt_matematicas > 40 AND punt_matematicas <= 55 THEN 1 END) as mat_2,
            COUNT(CASE WHEN punt_matematicas > 55 AND punt_matematicas <= 70 THEN 1 END) as mat_3,
            COUNT(CASE WHEN punt_matematicas > 70 THEN 1 END) as mat_4,
            
            -- Lectura Crítica
            COUNT(CASE WHEN punt_lectura_critica <= 40 THEN 1 END) as lec_1,
            COUNT(CASE WHEN punt_lectura_critica > 40 AND punt_lectura_critica <= 55 THEN 1 END) as lec_2,
            COUNT(CASE WHEN punt_lectura_critica > 55 AND punt_lectura_critica <= 70 THEN 1 END) as lec_3,
            COUNT(CASE WHEN punt_lectura_critica > 70 THEN 1 END) as lec_4,
            
            -- Ciencias Naturales
            COUNT(CASE WHEN punt_c_naturales <= 40 THEN 1 END) as nat_1,
            COUNT(CASE WHEN punt_c_naturales > 40 AND punt_c_naturales <= 55 THEN 1 END) as nat_2,
            COUNT(CASE WHEN punt_c_naturales > 55 AND punt_c_naturales <= 70 THEN 1 END) as nat_3,
            COUNT(CASE WHEN punt_c_naturales > 70 THEN 1 END) as nat_4,
            
            -- Sociales y Ciudadanas
            COUNT(CASE WHEN punt_sociales_ciudadanas <= 40 THEN 1 END) as soc_1,
            COUNT(CASE WHEN punt_sociales_ciudadanas > 40 AND punt_sociales_ciudadanas <= 55 THEN 1 END) as soc_2,
            COUNT(CASE WHEN punt_sociales_ciudadanas > 55 AND punt_sociales_ciudadanas <= 70 THEN 1 END) as soc_3,
            COUNT(CASE WHEN punt_sociales_ciudadanas > 70 THEN 1 END) as soc_4,
            
            -- Inglés
            COUNT(CASE WHEN punt_ingles <= 40 THEN 1 END) as ing_1,
            COUNT(CASE WHEN punt_ingles > 40 AND punt_ingles <= 55 THEN 1 END) as ing_2,
            COUNT(CASE WHEN punt_ingles > 55 AND punt_ingles <= 70 THEN 1 END) as ing_3,
            COUNT(CASE WHEN punt_ingles > 70 THEN 1 END) as ing_4
            
        FROM gold.fact_icfes_analytics
        WHERE colegio_sk = ? AND ano = ?
    """

    try:
        df = execute_query(query, params=[str(colegio_sk), ano])
        
        if df.empty or df.iloc[0]['total_estudiantes'] == 0:
            return JsonResponse({'message': 'No data found', 'materias': {}}, safe=False)

        row = df.iloc[0]
        total = int(row['total_estudiantes'])
        
        # Helper to format subject data
        def format_subject(prefix):
            return {
                'nivel_1': {'cantidad': int(row[f'{prefix}_1']), 'porcentaje': (row[f'{prefix}_1'] / total * 100) if total else 0},
                'nivel_2': {'cantidad': int(row[f'{prefix}_2']), 'porcentaje': (row[f'{prefix}_2'] / total * 100) if total else 0},
                'nivel_3': {'cantidad': int(row[f'{prefix}_3']), 'porcentaje': (row[f'{prefix}_3'] / total * 100) if total else 0},
                'nivel_4': {'cantidad': int(row[f'{prefix}_4']), 'porcentaje': (row[f'{prefix}_4'] / total * 100) if total else 0},
            }

        response_data = {
            'colegio_sk': colegio_sk,
            'ano': ano,
            'total_estudiantes': total,
            'materias': {
                'matematicas': format_subject('mat'),
                'lectura': format_subject('lec'),
                'c_naturales': format_subject('nat'),
                'sociales': format_subject('soc'),
                'ingles': format_subject('ing')
            }
        }
        
        return JsonResponse(response_data, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'Error calculating levels',
            'details': str(e)
        }, status=500)


# ============================================================================
# ENDPOINTS - RIESGO DE DECLIVE (Data Science P2)
# ============================================================================

@require_http_methods(["GET"])
def api_colegio_riesgo(request, colegio_sk):
    """
    Risk prediction for a specific school.
    Returns probability of decline, risk level, and contributing factors.
    Source: gold.fct_riesgo_colegios (XGBoost model output)
    """
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk invalido'}, status=400)

    colegio_sk_str = str(colegio_sk)

    query = """
        SELECT
            colegio_sk, codigo_dane, nombre_colegio, sector, departamento,
            ano, avg_punt_global_actual, prob_declive, prediccion_declive,
            nivel_riesgo, factores_principales, modelo_version
        FROM gold.fct_riesgo_colegios
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    try:
        df = execute_query(query, params=[colegio_sk_str])
    except Exception:
        return JsonResponse({'riesgo': None, 'disponible': False})

    if df.empty:
        return JsonResponse({'riesgo': None, 'disponible': False})

    row = df.iloc[0]
    factores = []
    try:
        factores = json.loads(row['factores_principales']) if row['factores_principales'] else []
    except (json.JSONDecodeError, TypeError):
        pass

    return JsonResponse({
        'disponible': True,
        'riesgo': {
            'ano': int(row['ano']),
            'prob_declive': round(float(row['prob_declive']), 3),
            'nivel_riesgo': row['nivel_riesgo'],
            'prediccion_declive': int(row['prediccion_declive']),
            'avg_punt_global_actual': round(float(row['avg_punt_global_actual']), 1),
            'factores_principales': factores,
            'modelo_version': row['modelo_version'],
        }
    })


@require_http_methods(["GET"])
def api_panorama_riesgo(request):
    """
    Aggregated risk panorama for the general overview tab.
    Returns risk distribution across all schools.
    """
    query = """
        SELECT
            nivel_riesgo,
            COUNT(*) as total_colegios,
            ROUND(AVG(prob_declive), 3) as prob_promedio,
            ROUND(AVG(avg_punt_global_actual), 1) as puntaje_promedio
        FROM gold.fct_riesgo_colegios
        GROUP BY nivel_riesgo
        ORDER BY
            CASE nivel_riesgo
                WHEN 'Alto' THEN 1
                WHEN 'Medio' THEN 2
                WHEN 'Bajo' THEN 3
            END
    """

    try:
        df = execute_query(query)
    except Exception:
        return JsonResponse({'disponible': False, 'distribucion': []})

    if df.empty:
        return JsonResponse({'disponible': False, 'distribucion': []})

    total = int(df['total_colegios'].sum())
    distribucion = []
    for _, row in df.iterrows():
        distribucion.append({
            'nivel_riesgo': row['nivel_riesgo'],
            'total_colegios': int(row['total_colegios']),
            'porcentaje': round(int(row['total_colegios']) / total * 100, 1),
            'prob_promedio': float(row['prob_promedio']),
            'puntaje_promedio': float(row['puntaje_promedio']),
        })

    # Top 5 colegios en mayor riesgo
    query_top = """
        SELECT nombre_colegio, departamento, sector,
               ROUND(prob_declive, 3) as prob_declive,
               ROUND(avg_punt_global_actual, 1) as puntaje_actual
        FROM gold.fct_riesgo_colegios
        WHERE nivel_riesgo = 'Alto'
        ORDER BY prob_declive DESC
        LIMIT 5
    """

    try:
        df_top = execute_query(query_top)
        top_riesgo = df_top.to_dict(orient='records')
    except Exception:
        top_riesgo = []

    return JsonResponse({
        'disponible': True,
        'total_colegios_analizados': total,
        'distribucion': distribucion,
        'top_riesgo': top_riesgo,
    })
