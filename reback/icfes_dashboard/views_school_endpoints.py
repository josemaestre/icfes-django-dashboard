"""
New API endpoints for School Individual View.
Append this content to icfes_dashboard/views.py
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .db_utils import execute_query
import pandas as pd
import json



@require_http_methods(["GET"])
def api_colegio_historico(request, colegio_sk):
    """Evolución histórica de un colegio"""
    query = f"""
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
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = {colegio_sk}
        ORDER BY ano DESC
    """
    df = execute_query(query)
    return JsonResponse(df.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_correlaciones(request, colegio_sk):
    """Correlaciones entre materias y puntaje global"""
    query = f"""
        SELECT *
        FROM gold.fct_colegio_correlaciones
        WHERE colegio_sk = {colegio_sk}
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
               departamento, municipio, materia, promedio_colegio,
               promedio_nacional, brecha_vs_nacional, brecha_porcentual,
               clasificacion_brecha, es_fortaleza, es_debilidad,
               ranking_materia, es_materia_mas_fuerte, es_materia_mas_debil,
               total_fortalezas, total_debilidades, clasificacion_general,
               perfil_rendimiento, recomendacion, prioridad_mejora,
               potencial_mejora_estimado
        FROM gold.fct_colegio_fortalezas_debilidades
        WHERE colegio_sk = {colegio_sk}
        ORDER BY ranking_materia
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
            WHERE colegio_sk = {colegio_sk}
        )
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
        WHERE h.colegio_sk = {colegio_sk}
    """
    df = execute_query(query)
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

    # Cluster Data - Intentar gold primero, luego main como fallback
    query_cluster_gold = """
        SELECT cluster_id, cluster_name
        FROM gold.dim_colegios_cluster
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    query_cluster_main = """
        SELECT cluster_id, cluster_name
        FROM main.dim_colegios_cluster
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    df_basico = execute_query(query_basico, params=[colegio_sk_str])
    df_ultimo = execute_query(query_ultimo, params=[colegio_sk_str, colegio_sk_str])
    df_zscore = execute_query(query_zscore, params=[colegio_sk_str, colegio_sk_str])
    df_rango = execute_query(query_rango, params=[colegio_sk_str])
    df_fd = execute_query(query_fd, params=[colegio_sk_str])

    # Intentar gold primero, si falla usar main
    try:
        df_cluster = execute_query(query_cluster_gold, params=[colegio_sk_str])
        print(f"[DEBUG] Gold cluster query result: {df_cluster.to_dict() if not df_cluster.empty else 'EMPTY'}")
        if df_cluster.empty:
            df_cluster = execute_query(query_cluster_main, params=[colegio_sk_str])
            print(f"[DEBUG] Main cluster query result: {df_cluster.to_dict() if not df_cluster.empty else 'EMPTY'}")
    except Exception as e:
        print(f"[DEBUG] Gold query failed with: {e}")
        df_cluster = execute_query(query_cluster_main, params=[colegio_sk_str])
        print(f"[DEBUG] Fallback main cluster result: {df_cluster.to_dict() if not df_cluster.empty else 'EMPTY'}")

    if df_basico.empty:
        return JsonResponse({'error': 'Colegio no encontrado'}, status=404)

    resumen = {
        'info_basica': df_basico.to_dict(orient='records')[0],
        'ultimo_ano': df_ultimo.to_dict(orient='records')[0] if not df_ultimo.empty else {},
        'z_score': df_zscore.to_dict(orient='records')[0] if not df_zscore.empty else {},
        'rango_historico': df_rango.to_dict(orient='records')[0] if not df_rango.empty else {},
        'analisis': df_fd.to_dict(orient='records')[0] if not df_fd.empty else {},
        'cluster': df_cluster.to_dict(orient='records')[0] if not df_cluster.empty else {}
    }

    return JsonResponse(resumen, safe=False)


@require_http_methods(["GET"])
def api_colegios_similares(request, colegio_sk):
    """
    Encuentra colegios similares basados en el cluster del mismo año.
    Query params: ?limit=5 (opcional)
    """
    # Validar colegio_sk
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)
    
    try:
        limit = int(request.GET.get('limit', 5))
        limit = min(limit, 20)
    except (ValueError, TypeError):
        limit = 5

    colegio_sk_str = str(colegio_sk)

    # 1. Obtener cluster y año del colegio objetivo (último disponible)
    # Intentar gold primero, luego main como fallback
    query_target_gold = """
        SELECT cluster_id, ano
        FROM gold.dim_colegios_cluster
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """
    query_target_main = """
        SELECT cluster_id, ano
        FROM main.dim_colegios_cluster
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    try:
        df_target = execute_query(query_target_gold, params=[colegio_sk_str])
        if df_target.empty:
            df_target = execute_query(query_target_main, params=[colegio_sk_str])
    except Exception:
        df_target = execute_query(query_target_main, params=[colegio_sk_str])

    if df_target.empty:
         return JsonResponse({'error': 'No se encontró clasificación de cluster para este colegio'}, status=404)

    cluster_id = int(df_target['cluster_id'][0])
    ano = int(df_target['ano'][0])

    # 2. Buscar colegios del mismo cluster y año
    # Ordenados por diferencia de puntaje global absoluto (los más parecidos en desempeño)
    # Usar main directamente ya que gold puede no existir

    query_similares = """
        WITH target_score AS (
            SELECT avg_punt_global
            FROM gold.fct_agg_colegios_ano
            WHERE colegio_sk = ? AND ano = ?
        )
        SELECT
            f.colegio_sk,
            f.nombre_colegio,
            f.municipio,
            f.departamento,
            f.avg_punt_global,
            f.total_estudiantes,
            ABS(f.avg_punt_global - (SELECT avg_punt_global FROM target_score)) as diff_score
        FROM main.dim_colegios_cluster c
        JOIN gold.fct_agg_colegios_ano f ON c.colegio_sk = f.colegio_sk AND c.ano = f.ano
        WHERE c.cluster_id = ?
          AND c.ano = ?
          AND f.colegio_sk != ? -- Excluir el propio colegio
        ORDER BY diff_score ASC
        LIMIT ?
    """

    # Parametros: colegio_sk (para target avg), ano (target), cluster_id, ano (filtro), colegio_sk (exclude), limit
    params = [colegio_sk_str, ano, cluster_id, ano, colegio_sk_str, limit]

    df_similares = execute_query(query_similares, params=params)
    
    return JsonResponse(df_similares.to_dict(orient='records'), safe=False)
