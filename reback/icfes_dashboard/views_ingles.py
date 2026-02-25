import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods
from django.core.cache import cache
import pandas as pd
import duckdb

from .db_utils import execute_query

logger = logging.getLogger(__name__)
_CACHE_TTL = 60 * 60 * 2  # 2 horas

def _is_table_missing(exc):
    """True si la excepción es un CatalogException de DuckDB (tabla no existe)."""
    return isinstance(exc, duckdb.CatalogException) or (
        "CatalogException" in type(exc).__name__ or
        "does not exist" in str(exc)
    )

def _cached(key, timeout, func):
    data = cache.get(key)
    if data is None:
        data = func()
        cache.set(key, data, timeout)
    return data

def build_where_clause(ano, departamento):
    where_clauses = []
    params = []
    if ano:
        where_clauses.append("CAST(ano AS INTEGER) = ?")
        params.append(int(ano))
    if departamento:
        # Simplificación asumiendo que el frontend manda el valor exacto o manejamos UPPER
        where_clauses.append("UPPER(departamento) = UPPER(?)")
        params.append(departamento)
    
    where_stmt = " AND ".join(where_clauses) if where_clauses else "1=1"
    return where_stmt, params

def build_where_clause_master(ano, departamento):
    where_clauses = ["estudiantes > 0"]
    params = []
    if ano:
        where_clauses.append("CAST(ano AS INTEGER) = ?")
        params.append(int(ano))
    if departamento:
        where_clauses.append("UPPER(cole_depto_ubicacion) = UPPER(?)")
        params.append(departamento)
    
    where_stmt = " AND ".join(where_clauses) if where_clauses else "1=1"
    return where_stmt, params

@require_GET
def api_ingles_kpis(request):
    ano = request.GET.get('ano')
    departamento = request.GET.get('departamento')

    def fetch():
        where_m, params_m = build_where_clause_master(ano, departamento)
        
        query = f"""
        WITH base AS (
            SELECT
                SUM(avg_ingles * estudiantes) / NULLIF(SUM(estudiantes), 0) as promedio_ingles,
                (SUM(CASE WHEN UPPER(cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN avg_ingles * estudiantes ELSE 0 END)
                 / NULLIF(SUM(CASE WHEN UPPER(cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN estudiantes ELSE 0 END), 0)) as promedio_ingles_privado,
                (SUM(CASE WHEN UPPER(cole_naturaleza) IN ('OFICIAL', '1') THEN avg_ingles * estudiantes ELSE 0 END)
                 / NULLIF(SUM(CASE WHEN UPPER(cole_naturaleza) IN ('OFICIAL', '1') THEN estudiantes ELSE 0 END), 0)) as promedio_ingles_publico
            FROM gold.icfes_master_resumen
            WHERE {where_m}
        )
        SELECT 
            ROUND(promedio_ingles, 2) as promedio_ingles,
            ROUND(promedio_ingles_privado, 2) as promedio_ingles_privado,
            ROUND(promedio_ingles_publico, 2) as promedio_ingles_publico,
            ROUND(promedio_ingles_privado - promedio_ingles_publico, 2) as brecha_ingles
        FROM base
        """
        df = execute_query(query, params=params_m)
        if df.empty:
            return {}
        
        data = df.to_dict(orient='records')[0]
        
        # Opcional: obtener los de desempeño de ingles (ing_pct_a2_o_superior, ing_pct_b1) desde fct_indicadores_desempeno
        where_i, params_i = build_where_clause(ano, departamento)
        query_mcer = f"""
        SELECT 
            ROUND(SUM(ing_nivel_a2 + ing_nivel_b1) * 100.0 / NULLIF(SUM(total_estudiantes), 0), 2) as pct_a2_o_superior,
            ROUND(SUM(ing_nivel_b1) * 100.0 / NULLIF(SUM(total_estudiantes), 0), 2) as pct_b1
        FROM gold.fct_indicadores_desempeno
        WHERE {where_i}
        """
        try:
            df_mcer = execute_query(query_mcer, params=params_i)
            if not df_mcer.empty:
                data.update(df_mcer.to_dict(orient='records')[0])
        except Exception as e:
            logger.error(f"Error fetching MCER KPIs: {{e}}")
            
        return data

    try:
        cache_key = f"ingles_kpis_{ano}_{departamento}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        logger.error(f"api_ingles_kpis error: {{e}}")
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def api_ingles_tendencia(request):
    departamento = request.GET.get('departamento')

    def fetch():
        where_m, params_m = build_where_clause_master(None, departamento)
        query = f"""
        SELECT 
            CAST(ano AS INTEGER) as ano,
            ROUND(SUM(avg_ingles * estudiantes) / NULLIF(SUM(estudiantes), 0), 2) as promedio_ingles,
            ROUND(SUM(avg_global * estudiantes) / NULLIF(SUM(estudiantes), 0), 2) as promedio_global
        FROM gold.icfes_master_resumen
        WHERE {where_m} AND ano >= '2014'
        GROUP BY ano
        ORDER BY ano ASC
        """
        df = execute_query(query, params=params_m)
        return df.to_dict(orient='records')

    try:
        cache_key = f"ingles_tendencia_{departamento}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def api_ingles_distribucion(request):
    ano = request.GET.get('ano')
    departamento = request.GET.get('departamento')

    def fetch():
        conditions = [
            "punt_ingles > 0",
            "nivel_ingles_mcer IS NOT NULL",
            "nivel_ingles_mcer != 'Sin Información'",
        ]
        params = []
        if ano:
            conditions.append("ano = ?")
            params.append(str(ano))
        if departamento:
            conditions.append("UPPER(departamento) = UPPER(?)")
            params.append(departamento)
        where = " AND ".join(conditions)

        query = f"""
        SELECT
            nivel_ingles_mcer AS nivel,
            COUNT(*)          AS total
        FROM gold.fact_icfes_analytics
        WHERE {where}
        GROUP BY nivel_ingles_mcer
        """
        df = execute_query(query, params=params if params else None)
        if df.empty:
            return []

        # Orden canónico MCER
        orden = ['Pre A1', 'A1', 'A2', 'B1']
        labels = {
            'Pre A1': 'Pre A1',
            'A1':     'A1',
            'A2':     'A2',
            'B1':     'B1 / B+',
        }
        totales = {row['nivel']: int(row['total']) for _, row in df.iterrows()}
        grand_total = sum(totales.values()) or 1

        return [
            {
                'name':    labels[nivel],
                'value':   totales.get(nivel, 0),
                'percent': round(totales.get(nivel, 0) * 100 / grand_total, 1),
            }
            for nivel in orden
        ]

    try:
        cache_key = f"ingles_distribucion_v2_{ano}_{departamento}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def api_ingles_mcer_historico(request):
    """Evolución de niveles MCER por año (2016-2024), opcionalmente por departamento.
    Fuente: fact_icfes_analytics (incluye Pre A1 correctamente)."""
    departamento = request.GET.get('departamento')

    def fetch():
        where_clauses = [
            "punt_ingles > 0",
            "nivel_ingles_mcer IS NOT NULL",
            "nivel_ingles_mcer != 'Sin Información'",
            "CAST(ano AS INTEGER) >= 2016",
        ]
        params = []
        if departamento:
            where_clauses.append("UPPER(departamento) = UPPER(?)")
            params.append(departamento)
        where = " AND ".join(where_clauses)

        query = f"""
        SELECT
            CAST(ano AS INTEGER) AS ano,
            COUNT(CASE WHEN nivel_ingles_mcer = 'Pre A1' THEN 1 END) AS pre_a1,
            COUNT(CASE WHEN nivel_ingles_mcer = 'A1'     THEN 1 END) AS a1,
            COUNT(CASE WHEN nivel_ingles_mcer = 'A2'     THEN 1 END) AS a2,
            COUNT(CASE WHEN nivel_ingles_mcer = 'B1'     THEN 1 END) AS b1,
            COUNT(*) AS total
        FROM gold.fact_icfes_analytics
        WHERE {where}
        GROUP BY ano
        ORDER BY ano ASC
        """
        df = execute_query(query, params=params if params else None)
        if df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            total = int(row['total']) or 1
            result.append({
                'ano':       int(row['ano']),
                'pre_a1':    int(row['pre_a1']),
                'a1':        int(row['a1']),
                'a2':        int(row['a2']),
                'b1':        int(row['b1']),
                'pct_pre_a1': round(int(row['pre_a1']) * 100 / total, 1),
                'pct_a1':     round(int(row['a1'])     * 100 / total, 1),
                'pct_a2':     round(int(row['a2'])     * 100 / total, 1),
                'pct_b1':     round(int(row['b1'])     * 100 / total, 1),
            })
        return result

    try:
        cache_key = f"ingles_mcer_historico_v2_{departamento}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        logger.error(f"api_ingles_mcer_historico error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_brechas(request):
    """Brechas socioeconómicas en inglés: por estrato, acceso digital y educación del hogar.

    Lee desde tablas gold pre-materializadas (build_ingles_brechas.py) en lugar
    de icfes_silver.icfes, garantizando que el endpoint funcione en producción.
    """

    def fetch():
        # Query 1: por estrato
        q_estrato = """
        SELECT
            estrato,
            avg_ingles,
            n_estudiantes AS total
        FROM gold.fct_ingles_brecha_estrato
        ORDER BY estrato
        """
        df_estrato = execute_query(q_estrato)

        # Query 2: por acceso digital (internet + computador)
        q_acceso = """
        SELECT
            tiene_internet,
            tiene_computador,
            avg_ingles,
            n_estudiantes AS total
        FROM gold.fct_ingles_brecha_acceso
        ORDER BY avg_ingles DESC
        """
        df_acceso = execute_query(q_acceso)

        # Query 3a: por educación del padre
        q_padre = """
        SELECT
            nivel_educacion,
            avg_ingles,
            n_estudiantes AS total
        FROM gold.fct_ingles_brecha_educacion_padre
        ORDER BY avg_ingles DESC
        """
        df_padre = execute_query(q_padre)

        # Query 3b: por educación de la madre
        q_madre = """
        SELECT
            nivel_educacion,
            avg_ingles,
            n_estudiantes AS total
        FROM gold.fct_ingles_brecha_educacion_madre
        ORDER BY avg_ingles DESC
        """
        df_madre = execute_query(q_madre)

        # Query 3c: extremos del hogar para storytelling (1 fila)
        q_story = """
        SELECT hogar_postgrado, hogar_ninguno, n_postgrado, n_ninguno
        FROM gold.fct_ingles_story_educacion
        """
        df_story = execute_query(q_story)
        story_row = df_story.iloc[0] if not df_story.empty else {}
        brecha_hogar = None
        if story_row.get('hogar_postgrado') and story_row.get('hogar_ninguno'):
            brecha_hogar = round(float(story_row['hogar_postgrado']) - float(story_row['hogar_ninguno']), 1)

        return {
            'por_estrato': df_estrato.to_dict(orient='records') if not df_estrato.empty else [],
            'por_acceso': df_acceso.to_dict(orient='records') if not df_acceso.empty else [],
            'por_educacion_padre': df_padre.to_dict(orient='records') if not df_padre.empty else [],
            'por_educacion_madre': df_madre.to_dict(orient='records') if not df_madre.empty else [],
            'story_educacion': {
                'hogar_postgrado': float(story_row.get('hogar_postgrado') or 0),
                'hogar_ninguno':   float(story_row.get('hogar_ninguno') or 0),
                'brecha_hogar':    brecha_hogar,
                'n_postgrado':     int(story_row.get('n_postgrado') or 0),
                'n_ninguno':       int(story_row.get('n_ninguno') or 0),
            },
        }

    try:
        cache_key = "ingles_brechas_v4"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        if _is_table_missing(e):
            logger.warning("api_ingles_brechas: tablas de brechas no disponibles en prod aún")
            return JsonResponse({'data': None, 'unavailable': True})
        logger.error(f"api_ingles_brechas error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_potencial(request):
    """Colegios con mayor/menor exceso de inglés respecto a su contexto socioeconómico."""
    ano = request.GET.get('ano', '2024')
    departamento = request.GET.get('departamento')
    modo = request.GET.get('modo', 'transformadores')  # 'transformadores' o 'riesgo'

    def fetch():
        where_clauses = ["p.ano = ?"]
        params = [str(ano)]
        if departamento:
            where_clauses.append("UPPER(p.departamento) = UPPER(?)")
            params.append(departamento)
        where = " AND ".join(where_clauses)

        order = "p.exceso_ingles DESC" if modo == 'transformadores' else "p.exceso_ingles ASC"

        query = f"""
        SELECT
            p.colegio_bk,
            p.nombre_colegio,
            p.sector,
            p.departamento,
            p.region,
            ROUND(p.avg_ingles, 1)              as avg_ingles,
            ROUND(p.score_ingles_esperado, 1)   as score_esperado,
            ROUND(p.exceso_ingles, 1)           as exceso_ingles,
            ROUND(p.percentil_exceso_ingles, 0) as percentil,
            p.clasificacion_ingles,
            p.ranking_exceso_nacional,
            COALESCE(s.slug, '')                as slug
        FROM gold.fct_potencial_ingles p
        LEFT JOIN gold.dim_colegios_slugs s
          ON p.colegio_bk = s.codigo
        WHERE {where}
        ORDER BY {order}
        LIMIT 15
        """
        df = execute_query(query, params=params)
        return df.to_dict(orient='records') if not df.empty else []

    try:
        cache_key = f"ingles_potencial_{ano}_{departamento}_{modo}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        if _is_table_missing(e):
            logger.warning("api_ingles_potencial: fct_potencial_ingles no disponible en prod aún")
            return JsonResponse({'data': [], 'unavailable': True})
        logger.error(f"api_ingles_potencial error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_mapa_depto(request):
    """Promedio de inglés y distribución MCER por departamento."""
    ano = request.GET.get('ano', '2024')

    def fetch():
        query = """
        SELECT
            departamento,
            COUNT(*) as total_estudiantes,
            ROUND(AVG(punt_ingles), 2) as avg_ingles,
            ROUND(COUNT(CASE WHEN nivel_ingles_mcer = 'B1' THEN 1 END) * 100.0
                  / NULLIF(COUNT(CASE WHEN nivel_ingles_mcer IS NOT NULL
                                       AND nivel_ingles_mcer != 'Sin Información' THEN 1 END), 0), 1) as pct_b1,
            ROUND(COUNT(CASE WHEN nivel_ingles_mcer = 'Pre A1' THEN 1 END) * 100.0
                  / NULLIF(COUNT(CASE WHEN nivel_ingles_mcer IS NOT NULL
                                       AND nivel_ingles_mcer != 'Sin Información' THEN 1 END), 0), 1) as pct_pre_a1
        FROM gold.fact_icfes_analytics
        WHERE punt_ingles > 0
          AND ano = ?
          AND departamento IS NOT NULL
          AND LENGTH(departamento) > 3
        GROUP BY departamento
        HAVING COUNT(*) >= 100
        ORDER BY avg_ingles DESC
        """
        df = execute_query(query, params=[str(ano)])
        return df.to_dict(orient='records') if not df.empty else []

    try:
        cache_key = f"ingles_mapa_depto_{ano}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        logger.error(f"api_ingles_mapa_depto error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_story(request):
    """Genera narrativa dinámica de 4 capítulos sobre inglés en Colombia."""
    ano = request.GET.get('ano', '2024')

    def fetch():
        ano_int = int(ano)
        ano_ant = str(ano_int - 1)

        # 1. KPI actual + cambio interanual
        df_kpi = execute_query("""
            SELECT
                ROUND(SUM(CASE WHEN ano = ?1 THEN avg_ingles * estudiantes ELSE 0 END)
                      / NULLIF(SUM(CASE WHEN ano = ?1 THEN estudiantes ELSE 0 END), 0), 1) AS avg_actual,
                ROUND(SUM(CASE WHEN ano = ?2 THEN avg_ingles * estudiantes ELSE 0 END)
                      / NULLIF(SUM(CASE WHEN ano = ?2 THEN estudiantes ELSE 0 END), 0), 1) AS avg_ant,
                SUM(CASE WHEN ano = ?1 THEN estudiantes ELSE 0 END)                         AS total_est
            FROM gold.icfes_master_resumen
            WHERE estudiantes > 0 AND ano IN (?1, ?2)
        """, params=[str(ano), ano_ant])

        # 2. MCER distribution — usando fact_icfes_analytics (fuente correcta, coherente con KPIs)
        df_mcer = execute_query("""
            SELECT
                ROUND(COUNT(CASE WHEN nivel_ingles_mcer = 'Pre A1' THEN 1 END) * 100.0
                      / NULLIF(COUNT(CASE WHEN nivel_ingles_mcer IS NOT NULL
                                          AND nivel_ingles_mcer != 'Sin Información' THEN 1 END), 0), 1) AS pct_pre_a1,
                ROUND(COUNT(CASE WHEN nivel_ingles_mcer = 'B1' THEN 1 END) * 100.0
                      / NULLIF(COUNT(CASE WHEN nivel_ingles_mcer IS NOT NULL
                                          AND nivel_ingles_mcer != 'Sin Información' THEN 1 END), 0), 1) AS pct_b1
            FROM gold.fact_icfes_analytics
            WHERE punt_ingles > 0 AND ano = ?
        """, params=[str(ano)])

        # 3. Gap estado de ánimo
        df_animo = execute_query("""
            SELECT ROUND(MAX(avg_i) - MIN(avg_i), 0) AS gap,
                   ROUND(MAX(avg_i), 1)              AS max_i,
                   ROUND(MIN(avg_i), 1)              AS min_i
            FROM (
                SELECT estado_animo_ingles, AVG(punt_ingles) AS avg_i
                FROM gold.fact_icfes_analytics
                WHERE punt_ingles > 0
                  AND estado_animo_ingles IS NOT NULL
                  AND estado_animo_ingles NOT IN ('', 'Sin Información')
                  AND ano = ?
                GROUP BY estado_animo_ingles
            ) t
        """, params=[str(ano)])

        # 4. Transformadores — conteo + top
        try:
            df_transf = execute_query("""
                SELECT
                    COUNT(*)                   AS total_excepcional,
                    ROUND(MAX(exceso_ingles),1) AS max_exceso
                FROM gold.fct_potencial_ingles
                WHERE clasificacion_ingles = 'Excepcional en Inglés' AND ano = ?
            """, params=[str(ano)])
            df_top = execute_query("""
                SELECT nombre_colegio, departamento, ROUND(exceso_ingles, 1) AS exceso
                FROM gold.fct_potencial_ingles
                WHERE ano = ?
                ORDER BY exceso_ingles DESC LIMIT 1
            """, params=[str(ano)])
        except Exception:
            df_transf = pd.DataFrame()
            df_top = pd.DataFrame()

        # Extraer valores con fallbacks seguros
        def safe(df, col, default):
            try:
                v = df.iloc[0][col]
                return default if (v is None or (isinstance(v, float) and pd.isna(v))) else v
            except Exception:
                return default

        avg_actual = float(safe(df_kpi, 'avg_actual', 51.5))
        avg_ant    = float(safe(df_kpi, 'avg_ant', avg_actual))
        total_est  = int(safe(df_kpi, 'total_est', 0))
        cambio     = round(avg_actual - avg_ant, 1)

        pct_b1  = float(safe(df_mcer, 'pct_b1', 10.0))
        pct_pre = float(safe(df_mcer, 'pct_pre_a1', 10.8))

        gap   = int(safe(df_animo, 'gap', 64))
        max_i = float(safe(df_animo, 'max_i', 94))
        min_i = float(safe(df_animo, 'min_i', 30))

        transf_total = int(safe(df_transf, 'total_excepcional', 0))
        max_exceso   = float(safe(df_transf, 'max_exceso', 0))
        top_nombre   = str(safe(df_top, 'nombre_colegio', 'N/D'))
        top_depto    = str(safe(df_top, 'departamento', ''))

        subiendo = cambio >= 0
        meta_ratio = round(22 / max(pct_b1, 0.1), 1)

        chapters = [
            {
                'id': 'panorama',
                'icon': 'bx-world',
                'color': 'primary',
                'titulo': f'El Balance de {ano}',
                'texto': (
                    f'{total_est:,} estudiantes presentaron la prueba de inglés en {ano}. '
                    f'El promedio nacional se ubicó en <strong>{avg_actual} puntos</strong>, '
                    f'{"subiendo" if subiendo else "bajando"} {abs(cambio)} puntos '
                    f'respecto a {ano_int - 1}. '
                    f'Un resultado que refleja tanto esfuerzos pedagógicos como las '
                    f'profundas desigualdades que persisten en el sistema educativo colombiano.'
                ),
                'metricas': [
                    {'valor': f'{avg_actual} pts', 'label': 'Promedio nacional', 'color': 'primary'},
                    {'valor': f'{"+" if subiendo else ""}{cambio} pts', 'label': f'vs {ano_int-1}',
                     'color': 'success' if subiendo else 'danger'},
                ],
            },
            {
                'id': 'bilinguismo',
                'icon': 'bx-certification',
                'color': 'warning',
                'titulo': 'La Meta B1: Un Camino Largo',
                'texto': (
                    f'El nivel B1 del Marco Común Europeo es el umbral del hablante '
                    f'"independiente" — quien puede comunicarse en situaciones cotidianas. '
                    f'En {ano}, apenas el <strong>{pct_b1}%</strong> de los estudiantes lo alcanzó, '
                    f'mientras el <strong>{pct_pre}%</strong> no superó siquiera el Pre-A1. '
                    f'El Ministerio de Educación fijó la meta del 22% para 2025 — '
                    f'un reto {meta_ratio}x mayor al nivel actual.'
                ),
                'metricas': [
                    {'valor': f'{pct_b1}%', 'label': 'alcanza B1', 'color': 'danger'},
                    {'valor': '22%', 'label': 'meta MEN 2025', 'color': 'warning'},
                ],
            },
            {
                'id': 'brecha',
                'icon': 'bx-heart-circle',
                'color': 'danger',
                'titulo': 'La Brecha que No Aparece en los Informes',
                'texto': (
                    f'La brecha por estrato (23 pts entre E1 y E6) es real, pero hay un '
                    f'factor aún más poderoso: la <strong>motivación del estudiante</strong>. '
                    f'Quienes se sienten seguros en inglés promedian <strong>{max_i} pts</strong>; '
                    f'quienes no, apenas <strong>{min_i} pts</strong> — '
                    f'una diferencia de <strong>{gap} puntos</strong>, casi 3 veces mayor que '
                    f'la brecha socioeconómica. El trabajo motivacional es tan urgente como el pedagógico.'
                ),
                'metricas': [
                    {'valor': f'{gap} pts', 'label': 'brecha motivacional', 'color': 'danger'},
                    {'valor': '23 pts', 'label': 'brecha por estrato', 'color': 'warning'},
                ],
            },
            {
                'id': 'transformadores',
                'icon': 'bx-rocket',
                'color': 'success',
                'titulo': 'Los Que Cambian la Historia',
                'texto': (
                    f'A pesar del contexto, <strong>{transf_total:,} instituciones</strong> '
                    f'están superando lo que su entorno predice — los llamados '
                    f'"Colegios Transformadores". Demuestran que la excelencia en inglés '
                    f'no es exclusiva de sectores privilegiados. El caso más destacado: '
                    f'<strong>{top_nombre}</strong>'
                    + (f' ({top_depto})' if top_depto else '')
                    + f', con <strong>+{max_exceso} puntos</strong> por encima de lo esperado '
                    f'para su contexto socioeconómico.'
                ),
                'metricas': [
                    {'valor': f'{transf_total:,}', 'label': 'Colegios Excepcionales', 'color': 'success'},
                    {'valor': f'+{max_exceso} pts', 'label': 'exceso máximo', 'color': 'primary'},
                ],
            },
        ]

        return {'ano': ano, 'chapters': chapters}

    try:
        cache_key = f"ingles_story_v2_{ano}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        logger.error(f"api_ingles_story error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_estado_animo(request):
    """Puntaje promedio de inglés por estado de ánimo del estudiante (año filtrable)."""
    ano = request.GET.get('ano', '2024')

    def fetch():
        query = """
        SELECT
            estado_animo_ingles,
            ROUND(AVG(punt_ingles), 2) AS avg_ingles,
            COUNT(*) AS total
        FROM gold.fact_icfes_analytics
        WHERE punt_ingles > 0
          AND estado_animo_ingles IS NOT NULL
          AND estado_animo_ingles NOT IN ('', 'Sin Información')
          AND ano = ?
        GROUP BY estado_animo_ingles
        ORDER BY avg_ingles DESC
        """
        df = execute_query(query, params=[str(ano)])
        return df.to_dict(orient='records') if not df.empty else []

    try:
        cache_key = f"ingles_estado_animo_{ano}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        logger.error(f"api_ingles_estado_animo error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_alertas_declive(request):
    """Colegios con declive sostenido en inglés durante 3 años consecutivos."""
    ano_ref = request.GET.get('ano', '2024')

    def fetch():
        query = """
        WITH historial AS (
            SELECT
                m.cole_cod_dane_establecimiento AS colegio_bk,
                m.ano,
                m.avg_ingles,
                m.estudiantes,
                m.cole_depto_ubicacion          AS departamento,
                m.cole_naturaleza               AS sector,
                LAG(m.avg_ingles, 1) OVER (
                    PARTITION BY m.cole_cod_dane_establecimiento ORDER BY m.ano
                ) AS ingles_y1,
                LAG(m.avg_ingles, 2) OVER (
                    PARTITION BY m.cole_cod_dane_establecimiento ORDER BY m.ano
                ) AS ingles_y2
            FROM gold.icfes_master_resumen m
            WHERE m.avg_ingles  IS NOT NULL
              AND m.estudiantes >= 10
              AND m.ano          >= '2020'
        ),
        con_declive AS (
            SELECT
                h.*,
                ROUND(h.ingles_y2 - h.avg_ingles, 2) AS caida_total
            FROM historial h
            WHERE h.ano          = ?
              AND h.ingles_y1    IS NOT NULL
              AND h.ingles_y2    IS NOT NULL
              AND h.avg_ingles   < h.ingles_y1
              AND h.ingles_y1    < h.ingles_y2
              AND h.ingles_y2 - h.avg_ingles > 2
        )
        SELECT
            d.colegio_bk,
            c.nombre_colegio,
            d.sector,
            d.departamento,
            ROUND(d.ingles_y2,   1) AS ingles_base,
            ROUND(d.ingles_y1,   1) AS ingles_medio,
            ROUND(d.avg_ingles,  1) AS ingles_actual,
            d.caida_total,
            COALESCE(s.slug, '')    AS slug
        FROM con_declive d
        LEFT JOIN gold.dim_colegios_ano c
          ON d.colegio_bk = c.colegio_bk AND d.ano = c.ano
        LEFT JOIN gold.dim_colegios_slugs s
          ON d.colegio_bk = s.codigo
        ORDER BY d.caida_total DESC
        LIMIT 20
        """
        df = execute_query(query, params=[str(ano_ref)])
        return df.to_dict(orient='records') if not df.empty else []

    try:
        cache_key = f"ingles_alertas_declive_{ano_ref}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        logger.error(f"api_ingles_alertas_declive error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_colegio_serie(request):
    """Serie histórica de inglés para un colegio + comparación con promedio nacional."""
    colegio_bk = request.GET.get('colegio_bk')
    if not colegio_bk:
        return JsonResponse({'error': 'colegio_bk requerido'}, status=400)

    def fetch():
        # Serie del colegio + promedio nacional por año
        serie_query = """
        WITH school_data AS (
            SELECT
                CAST(r.ano AS INTEGER)  AS ano,
                ROUND(r.avg_ingles, 1)  AS avg_ingles,
                r.estudiantes
            FROM gold.icfes_master_resumen r
            WHERE r.cole_cod_dane_establecimiento = ?
              AND r.avg_ingles  IS NOT NULL
              AND r.ano         >= '2014'
        ),
        nacional AS (
            SELECT
                CAST(r.ano AS INTEGER) AS ano,
                ROUND(SUM(r.avg_ingles * r.estudiantes) / NULLIF(SUM(r.estudiantes), 0), 1) AS avg_nacional
            FROM gold.icfes_master_resumen r
            WHERE r.avg_ingles  IS NOT NULL
              AND r.estudiantes > 0
              AND r.ano         >= '2014'
            GROUP BY r.ano
        )
        SELECT
            s.ano,
            s.avg_ingles,
            s.estudiantes,
            n.avg_nacional,
            ROUND(s.avg_ingles - n.avg_nacional, 1) AS vs_nacional
        FROM school_data s
        LEFT JOIN nacional n ON s.ano = n.ano
        ORDER BY s.ano ASC
        """
        df_serie = execute_query(serie_query, params=[str(colegio_bk)])

        # Metadata del colegio (registro más reciente)
        meta_query = """
        SELECT
            c.nombre_colegio,
            c.region,
            c.calendario,
            r.cole_naturaleza       AS sector,
            r.cole_depto_ubicacion  AS departamento,
            COALESCE(s.slug, '')    AS slug
        FROM gold.icfes_master_resumen r
        LEFT JOIN gold.dim_colegios_ano c
          ON r.cole_cod_dane_establecimiento = c.colegio_bk AND r.ano = c.ano
        LEFT JOIN gold.dim_colegios_slugs s
          ON r.cole_cod_dane_establecimiento = s.codigo
        WHERE r.cole_cod_dane_establecimiento = ?
          AND r.avg_ingles IS NOT NULL
        ORDER BY r.ano DESC
        LIMIT 1
        """
        df_meta = execute_query(meta_query, params=[str(colegio_bk)])

        meta = df_meta.to_dict(orient='records')[0] if not df_meta.empty else {}
        serie = df_serie.to_dict(orient='records') if not df_serie.empty else []
        return {'colegio': meta, 'serie': serie}

    try:
        cache_key = f"ingles_serie_{colegio_bk}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        logger.error(f"api_ingles_colegio_serie error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_ingles_colegios_top(request):
    ano = request.GET.get('ano')
    departamento = request.GET.get('departamento')
    
    def fetch():
        where_m, params_m = build_where_clause_master(ano, departamento)
        query = f"""
        SELECT 
            cole_cod_dane_establecimiento as codigo_dane,
            MAX(cole_naturaleza) as sector,
            MAX(cole_mcpio_ubicacion) as municipio,
            ROUND(AVG(avg_ingles), 2) as promedio_ingles,
            SUM(estudiantes) as total_estudiantes
        FROM gold.icfes_master_resumen
        WHERE {where_m} AND avg_ingles IS NOT NULL
        GROUP BY 1
        HAVING SUM(estudiantes) > 10
        ORDER BY promedio_ingles DESC
        LIMIT 20
        """
        df = execute_query(query, params=params_m)
        
        # Enriquecer con nombres (como icfes_master_resumen no tiene nombre_colegio directo fácil, cruzamos con fct_agg_colegios_ano si podemos)
        # o devolvemos simple por ahora. Pero fct_agg_colegios_ano sí los tiene.
        # Haremos un join simple usando gold.fct_agg_colegios_ano.
        
        # A better query joining the two:
        query_better = f"""
        SELECT 
            a.colegio_sk,
            a.nombre_colegio,
            a.municipio,
            a.sector,
            a.avg_punt_ingles as promedio_ingles,
            a.total_estudiantes
        FROM gold.fct_agg_colegios_ano a
        WHERE {where_m.replace("estudiantes > 0", "a.total_estudiantes > 0").replace("cole_depto_ubicacion", "a.departamento")}
          AND a.avg_punt_ingles IS NOT NULL
        ORDER BY a.avg_punt_ingles DESC
        LIMIT 10
        """
        df_better = execute_query(query_better, params=params_m)
        return df_better.to_dict(orient='records')

    try:
        cache_key = f"ingles_colegios_top_{ano}_{departamento}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# API: Score de Prioridad de Intervención en Inglés
# GET /api/ingles/prioridad/?ano=2024&departamento=&sector=&limit=50
# ---------------------------------------------------------------------------
@require_GET
def api_ingles_prioridad(request):
    """
    Devuelve los colegios ordenados por score_prioridad DESC.
    Fuente: gold.fct_prioridad_ingles (generada por train_prioridad_ingles.py).

    Params:
      ano         : año de referencia (default 2024)
      departamento: filtro opcional
      sector      : filtro opcional (OFICIAL / NO OFICIAL)
      nivel       : filtro por nivel_prioridad (Crítico / Urgente / Atención / Estable)
      limit       : max filas (default 50, max 500)
    """
    ano         = request.GET.get('ano', '2024')
    departamento= request.GET.get('departamento', '').strip()
    sector      = request.GET.get('sector', '').strip()
    nivel       = request.GET.get('nivel', '').strip()
    limit       = min(int(request.GET.get('limit', 50)), 500)

    def fetch():
        where_parts = ["ano = ?"]
        params = [str(ano)]

        if departamento:
            where_parts.append("UPPER(departamento) = UPPER(?)")
            params.append(departamento)
        if sector:
            where_parts.append("UPPER(sector) = UPPER(?)")
            params.append(sector)
        if nivel:
            where_parts.append("nivel_prioridad = ?")
            params.append(nivel)

        where = " AND ".join(where_parts)
        query = f"""
            SELECT
                colegio_bk, nombre_colegio, ano, sector, departamento, region,
                avg_ingles, exceso_ingles, score_ingles_esperado, clasificacion_ingles,
                score_prioridad, nivel_prioridad,
                dim_brecha_potencial, dim_declive_3y, dim_nivel_absoluto, dim_volumen
            FROM gold.fct_prioridad_ingles
            WHERE {where}
            ORDER BY score_prioridad DESC
            LIMIT {limit}
        """
        df = execute_query(query, params=params)
        return df.to_dict(orient='records')

    try:
        cache_key = f"ingles_prioridad_v1_{ano}_{departamento}_{sector}_{nivel}_{limit}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        if _is_table_missing(e):
            logger.warning("api_ingles_prioridad: fct_prioridad_ingles no disponible en prod aún")
            return JsonResponse({'data': [], 'unavailable': True})
        logger.exception("api_ingles_prioridad error")
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# API: Clusters de Departamentos por Trayectoria de Inglés
# GET /api/ingles/clusters-depto/
# ---------------------------------------------------------------------------
@require_GET
def api_ingles_clusters_depto(request):
    """
    Devuelve todos los departamentos con su cluster de trayectoria de inglés.
    Fuente: gold.fct_clusters_depto_ingles (generada por train_clusters_depto_ingles.py).

    Útil para colorear un mapa coroplético por cluster.
    No requiere parámetros — siempre devuelve los ~32 departamentos.
    """
    def fetch():
        query = """
            SELECT
                departamento, cluster_id, cluster_label,
                promedio_historico, promedio_reciente,
                tendencia_pendiente, volatilidad, cambio_abs,
                n_colegios_activos, n_departamentos_en_cluster
            FROM gold.fct_clusters_depto_ingles
            ORDER BY cluster_id, departamento
        """
        df = execute_query(query)
        return df.to_dict(orient='records')

    try:
        return JsonResponse({'data': _cached('ingles_clusters_depto_v1', _CACHE_TTL, fetch)})
    except Exception as e:
        if _is_table_missing(e):
            logger.warning("api_ingles_clusters_depto: fct_clusters_depto_ingles no disponible en prod aún")
            return JsonResponse({'data': [], 'unavailable': True})
        logger.exception("api_ingles_clusters_depto error")
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# API: Predicciones de Inglés para el Año Siguiente
# GET /api/ingles/prediccion/?sector=&departamento=&limit=50&orden=mejora
# ---------------------------------------------------------------------------
@require_GET
def api_ingles_prediccion(request):
    """
    Devuelve predicciones de avg_ingles para el año siguiente por colegio.
    Fuente: gold.fct_prediccion_ingles (generada por train_predictor_ingles.py).

    Params:
      departamento: filtro opcional
      sector      : filtro opcional
      tendencia   : filtro por tendencia (Mejora / Estable / Declive)
      orden       : "mejora" (default) → mayor cambio predicho primero
                    "riesgo"           → mayor caída primero
      limit       : max filas (default 50, max 500)
    """
    departamento= request.GET.get('departamento', '').strip()
    sector      = request.GET.get('sector', '').strip()
    tendencia   = request.GET.get('tendencia', '').strip()
    orden       = request.GET.get('orden', 'mejora').strip()
    limit       = min(int(request.GET.get('limit', 50)), 500)

    order_dir = "DESC" if orden != "riesgo" else "ASC"

    def fetch():
        where_parts = ["1=1"]
        params = []

        if departamento:
            where_parts.append("UPPER(departamento) = UPPER(?)")
            params.append(departamento)
        if sector:
            where_parts.append("UPPER(sector) = UPPER(?)")
            params.append(sector)
        if tendencia:
            where_parts.append("tendencia = ?")
            params.append(tendencia)

        where = " AND ".join(where_parts)
        query = f"""
            SELECT
                colegio_bk, nombre_colegio, ano_prediccion,
                sector, departamento, region,
                avg_ingles_actual, avg_ingles_y1, avg_ingles_y2, cambio_real_1y,
                estudiantes, avg_ingles_predicho, cambio_predicho,
                tendencia, ranking_mejora_nacional, model_r2, model_mae
            FROM gold.fct_prediccion_ingles
            WHERE {where}
            ORDER BY cambio_predicho {order_dir}
            LIMIT {limit}
        """
        df = execute_query(query, params=params)
        return df.to_dict(orient='records')

    try:
        cache_key = f"ingles_prediccion_v1_{departamento}_{sector}_{tendencia}_{orden}_{limit}"
        return JsonResponse({'data': _cached(cache_key, _CACHE_TTL, fetch)})
    except Exception as e:
        if _is_table_missing(e):
            logger.warning("api_ingles_prediccion: fct_prediccion_ingles no disponible en prod aún")
            return JsonResponse({'data': [], 'unavailable': True})
        logger.exception("api_ingles_prediccion error")
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Análisis IA — persiste en PostgreSQL, no en DuckDB
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def api_ingles_ai_analisis(request):
    """
    GET  → Devuelve el análisis IA activo desde PostgreSQL.
            Si no existe, retorna {'disponible': False} para que
            el frontend muestre el botón de generar.
    POST → Genera el análisis en tiempo real y lo guarda en Postgres.
            Solo disponible cuando no hay análisis activo (o con ?forzar=1).
            Requiere ANTHROPIC_API_KEY configurada.

    Params (GET/POST): ?ano=2024 | ?departamento=BOGOTA (default: nacional)
    """
    from icfes_dashboard.models import InglesAnalisisIA
    from icfes_dashboard.management.commands.generate_ingles_ia_analisis import (
        _get_duckdb_data_nacional, _get_duckdb_data_depto,
        _build_prompt_nacional, _build_prompt_depto,
        _parse_sections, MODEL_IA, MAX_TOKENS,
    )

    ano         = int(request.GET.get('ano', 2024))
    departamento = request.GET.get('departamento', '').strip().upper()
    forzar      = request.GET.get('forzar', '0') == '1'

    tipo     = InglesAnalisisIA.TIPO_DEPARTAMENTO if departamento else InglesAnalisisIA.TIPO_NACIONAL
    parametro = departamento  # '' para nacional

    # --- GET: leer desde Postgres ---
    if request.method == 'GET':
        obj = InglesAnalisisIA.objects.filter(
            tipo=tipo,
            parametro=parametro,
            ano_referencia=ano,
            estado=InglesAnalisisIA.ESTADO_ACTIVO,
        ).order_by('-fecha_generacion').first()

        if obj is None:
            return JsonResponse({
                'disponible': False,
                'mensaje': 'Análisis no generado. Usa el botón para generarlo.',
            })

        return JsonResponse({
            'disponible':      True,
            'tipo':            obj.tipo,
            'parametro':       obj.parametro or 'Nacional',
            'ano_referencia':  obj.ano_referencia,
            'analisis_md':     obj.analisis_md,
            'situacion':       obj.situacion,
            'geografia':       obj.geografia,
            'prediccion':      obj.prediccion,
            'brecha':          obj.brecha,
            'recomendacion':   obj.recomendacion,
            'modelo_ia':       obj.modelo_ia,
            'fecha_generacion': obj.fecha_generacion.isoformat(),
            'tokens_output':   obj.tokens_output,
        })

    # --- POST: generar en tiempo real ---
    if not forzar:
        existe = InglesAnalisisIA.objects.filter(
            tipo=tipo, parametro=parametro,
            ano_referencia=ano, estado=InglesAnalisisIA.ESTADO_ACTIVO,
        ).exists()
        if existe:
            return JsonResponse({
                'error': 'Ya existe un análisis activo. Usa ?forzar=1 para regenerar.'
            }, status=409)

    from django.conf import settings
    if not getattr(settings, 'ANTHROPIC_API_KEY', None):
        return JsonResponse({'error': 'ANTHROPIC_API_KEY no configurada.'}, status=503)

    try:
        if departamento:
            data   = _get_duckdb_data_depto(ano, departamento)
            prompt = _build_prompt_depto(data, ano, departamento)
        else:
            data   = _get_duckdb_data_nacional(ano)
            prompt = _build_prompt_nacional(data, ano)

        import anthropic
        client  = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=MODEL_IA, max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        analisis_md   = message.content[0].text
        tokens_input  = message.usage.input_tokens
        tokens_output = message.usage.output_tokens
        sections      = _parse_sections(analisis_md)

        # Archivar activos anteriores
        InglesAnalisisIA.objects.filter(
            tipo=tipo, parametro=parametro,
            ano_referencia=ano, estado=InglesAnalisisIA.ESTADO_ACTIVO,
        ).update(estado=InglesAnalisisIA.ESTADO_ARCHIVADO)

        obj = InglesAnalisisIA.objects.create(
            tipo=tipo, parametro=parametro, ano_referencia=ano,
            estado=InglesAnalisisIA.ESTADO_ACTIVO,
            analisis_md=analisis_md,
            situacion=sections.get('situacion', ''),
            geografia=sections.get('geografia', ''),
            prediccion=sections.get('prediccion', ''),
            brecha=sections.get('brecha', ''),
            recomendacion=sections.get('recomendacion', ''),
            modelo_ia=MODEL_IA,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )

        return JsonResponse({
            'disponible':      True,
            'generado_ahora':  True,
            'tipo':            obj.tipo,
            'parametro':       obj.parametro or 'Nacional',
            'ano_referencia':  obj.ano_referencia,
            'analisis_md':     obj.analisis_md,
            'situacion':       obj.situacion,
            'geografia':       obj.geografia,
            'prediccion':      obj.prediccion,
            'brecha':          obj.brecha,
            'recomendacion':   obj.recomendacion,
            'modelo_ia':       obj.modelo_ia,
            'fecha_generacion': obj.fecha_generacion.isoformat(),
            'tokens_output':   obj.tokens_output,
        })

    except Exception as e:
        logger.exception("api_ingles_ai_analisis POST error")
        return JsonResponse({'error': str(e)}, status=500)
