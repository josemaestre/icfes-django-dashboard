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
def api_colegio_ingles(request, colegio_sk):
    """Perfil de bilingüismo del colegio (último año)"""
    if not colegio_sk or not str(colegio_sk).replace('-', '').replace('_', '').isalnum():
        return JsonResponse({'error': 'colegio_sk inválido'}, status=400)
        
    colegio_sk_str = str(colegio_sk)
    
    query_historico = """
        SELECT ano, avg_punt_ingles, codigo_dane 
        FROM gold.fct_colegio_historico 
        WHERE colegio_sk = ? AND avg_punt_ingles IS NOT NULL
        ORDER BY ano DESC
    """
    df_hist = execute_query(query_historico, params=[colegio_sk_str])
    if df_hist.empty:
        return JsonResponse({'error': 'No hay datos de inglés'}, status=404)
        
    ultimo = df_hist.iloc[0]
    codigo_dane = str(ultimo['codigo_dane'])
    
    # Promedio historico
    promedio_historico = df_hist['avg_punt_ingles'].mean()
    
    # Desempeño MCER (último año)
    query_mcer = """
        SELECT 
            ing_nivel_pre_a1, ing_nivel_a1, ing_nivel_a2, ing_nivel_b1,
            total_estudiantes
        FROM gold.fct_indicadores_desempeno
        WHERE colegio_bk = ?
        ORDER BY ano DESC
        LIMIT 1
    """
    df_mcer = execute_query(query_mcer, params=[codigo_dane])
    
    mcer_data = {}
    if not df_mcer.empty:
        mcer = df_mcer.iloc[0]
        total = float(mcer['total_estudiantes']) if mcer['total_estudiantes'] else 1
        mcer_data = {
            'pre_a1': float(mcer['ing_nivel_pre_a1'] or 0),
            'a1': float(mcer['ing_nivel_a1'] or 0),
            'a2': float(mcer['ing_nivel_a2'] or 0),
            'b1': float(mcer['ing_nivel_b1'] or 0),
            'total': total
        }
    
    response = {
        'avg_historico': round(float(promedio_historico), 1),
        'avg_ultimo': float(ultimo['avg_punt_ingles']),
        'mcer': mcer_data
    }
    
    return JsonResponse(response)


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
    """Fortalezas y debilidades por materia (último año disponible)"""
    query = """
        SELECT colegio_sk, ano, codigo_dane, nombre_colegio, sector,
               departamento, municipio,
               avg_punt_matematicas, avg_punt_lectura_critica,
               avg_punt_c_naturales, avg_punt_sociales_ciudadanas, avg_punt_ingles,
               avg_punt_global,
               brecha_matematicas, brecha_lectura, brecha_ciencias,
               brecha_sociales, brecha_ingles, brecha_global,
               materia_mas_fuerte, materia_mas_debil,
               clasificacion_general, perfil_rendimiento,
               urgencia_mejora, recomendacion_principal
        FROM gold.fct_colegio_fortalezas_debilidades
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """
    df = execute_query(query, params=[str(colegio_sk)])
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

    # Cluster Data
    query_cluster = """
        SELECT cluster_id, cluster_name
        FROM gold.dim_colegios_cluster
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    try:
        df_cluster = execute_query(query_cluster, params=[colegio_sk_str])
    except Exception as e:
        print(f"[DEBUG] Cluster query failed: {e}")
        df_cluster = pd.DataFrame()

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
    query_target = """
        SELECT cluster_id, ano
        FROM gold.dim_colegios_cluster
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """

    try:
        df_target = execute_query(query_target, params=[colegio_sk_str])
    except Exception:
        return JsonResponse({'error': 'Error consultando cluster'}, status=500)

    if df_target.empty:
         return JsonResponse({'error': 'No se encontró clasificación de cluster para este colegio'}, status=404)

    cluster_id = int(df_target['cluster_id'][0])
    ano = int(df_target['ano'][0])

    # 2. Buscar colegios del mismo cluster y año
    # Ordenados por diferencia de puntaje global absoluto (los más parecidos en desempeño)
    
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
        FROM gold.dim_colegios_cluster c
        JOIN gold.fct_agg_colegios_ano f ON c.colegio_sk = f.colegio_sk AND c.ano = f.ano
        WHERE c.cluster_id = ?
          AND c.ano = ?
          AND f.colegio_sk != ? -- Excluir el propio colegio
          AND f.nombre_colegio != 'COLEGIO SINTETICO POR MUNICIPIO'
        ORDER BY diff_score ASC
        LIMIT ?
    """

    # Parametros: colegio_sk (para target avg), ano (target), cluster_id, ano (filtro), colegio_sk (exclude), limit
    params = [colegio_sk_str, ano, cluster_id, ano, colegio_sk_str, limit]

    df_similares = execute_query(query_similares, params=params)

    return JsonResponse(df_similares.to_dict(orient='records'), safe=False)


@require_http_methods(["GET"])
def api_colegio_niveles_historico(request, colegio_sk):
    """
    Evolución histórica de la distribución de niveles de desempeño (1-4)
    por materia para un colegio. Fuente: fct_indicadores_desempeno.

    Retorna todos los años disponibles con % de estudiantes en cada nivel
    para las 4 materias clásicas + inglés (niveles MCER).
    """
    if not colegio_sk or not str(colegio_sk).replace("-", "").replace("_", "").isalnum():
        return JsonResponse({"error": "colegio_sk inválido"}, status=400)

    colegio_sk_str = str(colegio_sk)

    query = """
        SELECT
            f.ano,
            f.total_estudiantes,
            -- Matemáticas
            f.mat_nivel_1_insuficiente   AS mat_n1,
            f.mat_nivel_2_minimo         AS mat_n2,
            f.mat_nivel_3_satisfactorio  AS mat_n3,
            f.mat_nivel_4_avanzado       AS mat_n4,
            -- Lectura Crítica
            f.lc_nivel_1_insuficiente    AS lc_n1,
            f.lc_nivel_2_minimo          AS lc_n2,
            f.lc_nivel_3_satisfactorio   AS lc_n3,
            f.lc_nivel_4_avanzado        AS lc_n4,
            -- Ciencias Naturales
            f.cn_nivel_1_insuficiente    AS cn_n1,
            f.cn_nivel_2_minimo          AS cn_n2,
            f.cn_nivel_3_satisfactorio   AS cn_n3,
            f.cn_nivel_4_avanzado        AS cn_n4,
            -- Sociales y Ciudadanas
            f.sc_nivel_1_insuficiente    AS sc_n1,
            f.sc_nivel_2_minimo          AS sc_n2,
            f.sc_nivel_3_satisfactorio   AS sc_n3,
            f.sc_nivel_4_avanzado        AS sc_n4,
            -- Inglés (MCER)
            f.ing_nivel_pre_a1           AS ing_pre_a1,
            f.ing_nivel_a1               AS ing_a1,
            f.ing_nivel_a2               AS ing_a2,
            f.ing_nivel_b1               AS ing_b1
        FROM gold.fct_indicadores_desempeno f
        WHERE f.colegio_bk = (
            SELECT colegio_bk FROM gold.dim_colegios
            WHERE colegio_sk = ? LIMIT 1
        )
        ORDER BY f.ano
    """
    df = execute_query(query, params=[colegio_sk_str])
    if df.empty:
        return JsonResponse([], safe=False)

    rows = []
    for _, r in df.iterrows():
        def pct(num, tot):
            return round(float(num or 0) / tot * 100, 1) if tot else 0

        row = {"ano": str(r["ano"]), "total": int(r["total_estudiantes"] or 0)}

        for prefix in ("mat", "lc", "cn", "sc"):
            tot = sum(float(r[f"{prefix}_n{i}"] or 0) for i in range(1, 5))
            for i in range(1, 5):
                row[f"{prefix}_pct{i}"] = pct(r[f"{prefix}_n{i}"], tot)

        # Inglés MCER
        ing_tot = sum(float(r[k] or 0) for k in ("ing_pre_a1", "ing_a1", "ing_a2", "ing_b1"))
        row["ing_pct_pre_a1"] = pct(r["ing_pre_a1"], ing_tot)
        row["ing_pct_a1"]     = pct(r["ing_a1"],     ing_tot)
        row["ing_pct_a2"]     = pct(r["ing_a2"],     ing_tot)
        row["ing_pct_b1"]     = pct(r["ing_b1"],     ing_tot)

        rows.append(row)

    return JsonResponse(rows, safe=False)
