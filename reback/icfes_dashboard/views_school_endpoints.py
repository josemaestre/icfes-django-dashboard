"""
New API endpoints for School Individual View.
Append this content to icfes_dashboard/views.py
"""


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
    # Información básica
    query_basico = f"""
        SELECT DISTINCT colegio_sk, codigo_dane, nombre_colegio,
               sector, departamento, municipio
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = {colegio_sk}
        LIMIT 1
    """
    
    # Último año
    query_ultimo = f"""
        WITH ultimo_ano AS (
            SELECT MAX(ano) as ano
            FROM gold.fct_colegio_historico
            WHERE colegio_sk = {colegio_sk}
        )
        SELECT h.ano, h.total_estudiantes, h.avg_punt_global,
               h.ranking_nacional, h.ranking_municipal,
               h.cambio_absoluto_global, h.cambio_porcentual_global,
               h.clasificacion_tendencia
        FROM gold.fct_colegio_historico h
        INNER JOIN ultimo_ano u ON h.ano = u.ano
        WHERE h.colegio_sk = {colegio_sk}
    """
    
    # Rango de años
    query_rango = f"""
        SELECT MIN(ano) as ano_inicio, MAX(ano) as ano_fin,
               COUNT(DISTINCT ano) as total_anos
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = {colegio_sk}
    """
    
    # Fortalezas/debilidades
    query_fd = f"""
        SELECT total_fortalezas, total_debilidades,
               clasificacion_general, perfil_rendimiento
        FROM gold.fct_colegio_fortalezas_debilidades
        WHERE colegio_sk = {colegio_sk}
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
