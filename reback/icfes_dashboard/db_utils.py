"""
Utilidades para trabajar con DuckDB en el dashboard ICFES.
"""
import duckdb
import pandas as pd
import numpy as np
from django.conf import settings
from contextlib import contextmanager
import threading

# Lock para crear vistas solo una vez
_views_lock = threading.Lock()
_views_created = set()

def _ensure_gold_views_exist(db_path):
    """Asegura que las vistas gold existan (thread-safe)."""
    if db_path in _views_created:
        return
    
    with _views_lock:
        # Double-check después del lock
        if db_path in _views_created:
            return
        
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Conectar temporalmente en read-write para crear vistas
            temp_conn = duckdb.connect(db_path, read_only=False)
            
            logger.info(f"Creating gold schema views for {db_path}")
            
            # Crear schema gold
            temp_conn.execute("CREATE SCHEMA IF NOT EXISTS gold;")
            
            # Check schemas in priority order
            source_schema = 'main'
            tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = ?"
            tables = temp_conn.execute(tables_query, [source_schema]).fetchall()
            
            if not tables:
                # Try 'prod' schema if main is empty
                logger.info("No tables found in 'main' schema, checking 'prod' schema...")
                tables = temp_conn.execute(tables_query, ['prod']).fetchall()
                if tables:
                    source_schema = 'prod'
            
            logger.info(f"Found {len(tables)} tables in {source_schema} schema")
            
            # Crear vistas gold.* -> source_schema.*
            views_created = 0
            for (table_name,) in tables:
                try:
                    temp_conn.execute(f"CREATE OR REPLACE VIEW gold.{table_name} AS SELECT * FROM {source_schema}.{table_name}")
                    views_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create view for {table_name}: {e}")
            
            temp_conn.close()
            logger.info(f"Successfully created {views_created} gold schema views from {source_schema}")
            
            # Marcar como creado
            _views_created.add(db_path)
            
        except Exception as e:
            logger.error(f"Error creating gold schema views: {e}")
            # No raise - continuar con conexión normal


@contextmanager
def get_duckdb_connection(read_only=True):
    """
    Context manager para obtener una conexión a DuckDB.
    Soporta tanto archivos locales como S3.
    
    Para S3, descarga el archivo a /tmp en el primer uso.
    
    Args:
        read_only: Si True, abre la BD en modo solo lectura (default: True)
    
    Yields:
        duckdb.DuckDBPyConnection: Conexión a DuckDB
    
    Example:
        with get_duckdb_connection() as con:
            df = con.execute("SELECT * FROM gold.fact_icfes_analytics LIMIT 10").df()
    """
    import os
    import subprocess
    
    con = None
    try:
        # Crear conexión en memoria para S3 o local para archivo
        db_path = getattr(settings, 'ICFES_DUCKDB_PATH', None)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Database path: {db_path}")
        
        # Determinar si es S3 o local
        is_s3 = db_path and db_path.startswith('s3://')
        logger.info(f"Is S3: {is_s3}")
        
        if is_s3:
            # Descargar desde S3 a Railway volume (persiste entre deployments)
            local_path = '/app/data/prod.duckdb'
            
            # Verificar si el archivo existe Y tiene tamaño adecuado (> 1GB)
            file_exists = os.path.exists(local_path)
            file_size = os.path.getsize(local_path) if file_exists else 0
            min_size = 1 * 1024 * 1024 * 1024  # 1 GB
            
            logger.info(f"File exists: {file_exists}, Size: {file_size / (1024**3):.2f} GB")
            
            # Si el archivo existe pero podría estar corrupto, verificar tablas
            needs_download = not file_exists or file_size < min_size
            
            if file_exists and file_size >= min_size:
                # Verificar si tiene tablas (archivo podría estar corrupto)
                try:
                    test_conn = duckdb.connect(local_path, read_only=True)
                    # Check main or prod schemas
                    table_count = test_conn.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema IN ('main', 'prod')
                    """).fetchone()[0]
                    test_conn.close()
                    logger.info(f"File has {table_count} tables in main/prod schemas")
                    
                    if table_count == 0:
                        logger.warning("File exists but has 0 tables - deleting corrupted file")
                        os.remove(local_path)
                        needs_download = True
                except Exception as e:
                    logger.warning(f"Error checking file: {e} - will re-download")
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    needs_download = True
            
            if needs_download:
                # Usar AWS CLI para descargar
                aws_key = os.environ.get('AWS_ACCESS_KEY_ID')
                aws_secret = os.environ.get('AWS_SECRET_ACCESS_KEY')
                aws_region = os.environ.get('AWS_S3_REGION', 'us-east-1')
                
                # Configurar variables de entorno para AWS CLI
                env = os.environ.copy()
                env['AWS_ACCESS_KEY_ID'] = aws_key
                env['AWS_SECRET_ACCESS_KEY'] = aws_secret
                env['AWS_DEFAULT_REGION'] = aws_region
                
                # Descargar archivo desde S3
                import logging
                logger = logging.getLogger(__name__)
                
                logger.info(f"Downloading {db_path} to {local_path}...")
                
                result = subprocess.run(
                    ['aws', 's3', 'cp', db_path, local_path],
                    env=env,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    error_msg = f"Failed to download from S3. Return code: {result.returncode}\n"
                    error_msg += f"STDOUT: {result.stdout}\n"
                    error_msg += f"STDERR: {result.stderr}\n"
                    error_msg += f"S3 Path: {db_path}\n"
                    error_msg += f"Local Path: {local_path}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                logger.info(f"Successfully downloaded {db_path}")
            
            # Conectar al archivo local
            # Crear vistas una sola vez si no existen
            _ensure_gold_views_exist(local_path)
            
            # Ahora conectar en modo read-only para queries
            con = duckdb.connect(local_path, read_only=read_only)
        else:
            # Conexión local tradicional
            # Crear vistas gold si no existen
            _ensure_gold_views_exist(db_path)
            con = duckdb.connect(db_path, read_only=read_only)
        
        yield con
    finally:
        if con:
            con.close()


def execute_query(query, params=None):
    """
    Ejecuta una query SQL en DuckDB y retorna un DataFrame.
    
    Args:
        query: Query SQL a ejecutar
        params: Parámetros para la query (opcional)
    
    Returns:
        pandas.DataFrame: Resultado de la query
    """
    with get_duckdb_connection() as con:
        if params:
            result = con.execute(query, params).df()
        else:
            result = con.execute(query).df()
        
        # Limpiar NaN, NaT e infinitos para JSON
        result = result.replace([pd.NA, np.nan, np.inf, -np.inf], None)
        
        return result


def get_table_data(table_name, filters=None, limit=None, order_by=None):
    """
    Obtiene datos de una tabla con filtros opcionales.

    Args:
        table_name: Nombre de la tabla (ej: 'gold.fact_icfes_analytics')
        filters: Dict con filtros (ej: {'ano': 2023, 'sector': 'OFICIAL'})
        limit: Límite de registros
        order_by: Campo(s) para ordenar

    Returns:
        pandas.DataFrame: Datos de la tabla
    """
    # Validar table_name contra whitelist de tablas permitidas
    allowed_tables = [
        'gold.fact_icfes_analytics',
        'gold.dim_colegios',
        'gold.fct_agg_colegios_ano',
        'gold.vw_fct_colegios_region',
        'gold.fct_colegio_historico',
        'gold.fct_estadisticas_anuales',
        'gold.tendencias_regionales',
        'gold.brechas_educativas',
        'gold.fct_indicadores_desempeno',
    ]

    if table_name not in allowed_tables:
        raise ValueError(f"Tabla no permitida: {table_name}")

    # Validar order_by fields
    allowed_order_fields = [
        'ano', 'ano DESC', 'ano ASC',
        'departamento', 'municipio', 'sector', 'region',
        'avg_punt_global', 'avg_punt_global DESC', 'avg_punt_global ASC',
        'promedio_departamental', 'promedio_departamental DESC',
        'brecha_absoluta_puntos', 'brecha_absoluta_puntos DESC',
        'total_estudiantes', 'total_estudiantes DESC',
    ]

    params = []
    query = f"SELECT * FROM {table_name}"

    if filters:
        where_clauses = []
        for key, value in filters.items():
            # Validar que key sea un campo permitido
            if not key.replace('_', '').isalnum():
                raise ValueError(f"Campo de filtro no válido: {key}")
            where_clauses.append(f"{key} = ?")
            params.append(value)
        query += " WHERE " + " AND ".join(where_clauses)

    if order_by:
        if isinstance(order_by, list):
            # Validar cada campo de orden
            for field in order_by:
                if field not in allowed_order_fields:
                    raise ValueError(f"Campo de orden no permitido: {field}")
            query += f" ORDER BY {', '.join(order_by)}"
        else:
            if order_by not in allowed_order_fields:
                raise ValueError(f"Campo de orden no permitido: {order_by}")
            query += f" ORDER BY {order_by}"

    if limit:
        try:
            limit = int(limit)
            limit = min(limit, 10000)  # Máximo 10000 registros
            query += f" LIMIT {limit}"
        except (ValueError, TypeError):
            pass

    return execute_query(query, params=params if params else None)


def get_anos_disponibles():
    """
    Obtiene la lista de años disponibles en la base de datos.
    
    Returns:
        list: Lista de años ordenados descendentemente
    """
    query = """
        SELECT DISTINCT ano 
        FROM gold.fact_icfes_analytics 
        ORDER BY ano DESC
    """
    df = execute_query(query)
    return df['ano'].tolist()


def get_departamentos():
    """
    Obtiene la lista de departamentos únicos.
    
    Returns:
        list: Lista de departamentos ordenados alfabéticamente
    """
    query = """
        SELECT DISTINCT departamento 
        FROM gold.dim_colegios 
        ORDER BY departamento
    """
    df = execute_query(query)
    return df['departamento'].tolist()


def get_municipios_por_departamento(departamento):
    """
    Obtiene municipios de un departamento específico.

    Args:
        departamento: Nombre del departamento

    Returns:
        list: Lista de municipios
    """
    query = """
        SELECT DISTINCT municipio
        FROM gold.dim_colegios
        WHERE departamento = ?
        ORDER BY municipio
    """
    df = execute_query(query, params=[departamento])
    return df['municipio'].tolist()


def get_estadisticas_generales(ano=None):
    """
    Obtiene estadísticas generales del sistema.

    Args:
        ano: Año específico (opcional, si None usa todos los años)

    Returns:
        dict: Diccionario con estadísticas
    """
    # Validar ano si se proporciona
    if ano is not None:
        try:
            ano = int(ano)
        except (ValueError, TypeError):
            return {}

    # Intentar usar tabla materializada fct_estadisticas_anuales para performance
    # Si no existe (aún no se ejecutó dbt), usar query antigua

    try:
        if ano:
            query = """
                SELECT
                    total_estudiantes,
                    total_colegios,
                    total_departamentos,
                    total_municipios,
                    promedio_nacional,
                    puntaje_minimo,
                    puntaje_maximo,
                    desviacion_estandar
                FROM gold.fct_estadisticas_anuales
                WHERE ano = ?
            """
            df = execute_query(query, params=[ano])
        else:
            # Si no hay año, agregar todas las filas
            query = """
                SELECT
                    SUM(total_estudiantes) as total_estudiantes,
                    COUNT(DISTINCT ano) as total_anos,
                    ROUND(AVG(promedio_nacional), 2) as promedio_nacional,
                    MIN(puntaje_minimo) as puntaje_minimo,
                    MAX(puntaje_maximo) as puntaje_maximo,
                    ROUND(AVG(desviacion_estandar), 2) as desviacion_estandar
                FROM gold.fct_estadisticas_anuales
            """
            df = execute_query(query)

        if df.empty:
            return {}

        result = df.iloc[0].to_dict()

        # Si no hay año específico, agregar conteos totales
        if not ano:
            counts_query = """
                SELECT
                    COUNT(DISTINCT colegio_sk) as total_colegios,
                    COUNT(DISTINCT departamento) as total_departamentos,
                    COUNT(DISTINCT municipio) as total_municipios
                FROM gold.fact_icfes_analytics
            """
            counts_df = execute_query(counts_query)
            if not counts_df.empty:
                result.update(counts_df.iloc[0].to_dict())

        return result

    except Exception as e:
        # Fallback: usar query antigua si la tabla no existe
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"fct_estadisticas_anuales no existe, usando query antigua: {e}")

        if ano:
            query = """
                SELECT
                    COUNT(DISTINCT estudiante_sk) as total_estudiantes,
                    COUNT(DISTINCT colegio_sk) as total_colegios,
                    COUNT(DISTINCT departamento) as total_departamentos,
                    COUNT(DISTINCT municipio) as total_municipios,
                    AVG(punt_global) as promedio_nacional,
                    MIN(punt_global) as puntaje_minimo,
                    MAX(punt_global) as puntaje_maximo,
                    STDDEV(punt_global) as desviacion_estandar
                FROM gold.fact_icfes_analytics
                WHERE ano = ?
            """
            df = execute_query(query, params=[ano])
        else:
            query = """
                SELECT
                    COUNT(DISTINCT estudiante_sk) as total_estudiantes,
                    COUNT(DISTINCT colegio_sk) as total_colegios,
                    COUNT(DISTINCT departamento) as total_departamentos,
                    COUNT(DISTINCT municipio) as total_municipios,
                    AVG(punt_global) as promedio_nacional,
                    MIN(punt_global) as puntaje_minimo,
                    MAX(punt_global) as puntaje_maximo,
                    STDDEV(punt_global) as desviacion_estandar
                FROM gold.fact_icfes_analytics
            """
            df = execute_query(query)

        return df.iloc[0].to_dict() if not df.empty else {}


def get_promedios_ubicacion(ano, departamento=None, municipio=None):
    """
    Obtiene promedios por ubicación (departamento o municipio).

    Args:
        ano: Año
        departamento: Nombre del departamento (opcional)
        municipio: Nombre del municipio (opcional)

    Returns:
        dict: Promedios por materia para la ubicación especificada
    """
    # Validar ano
    try:
        ano = int(ano)
    except (ValueError, TypeError):
        return {}

    params = [ano]
    where_clauses = ["ano = ?"]

    if departamento:
        where_clauses.append("departamento = ?")
        params.append(departamento)
    if municipio:
        where_clauses.append("municipio = ?")
        params.append(municipio)

    where_clause = " AND ".join(where_clauses)

    # Construir ubicacion label de forma segura
    ubicacion_label = departamento if departamento else 'Nacional'

    query = f"""
        SELECT
            ? as ubicacion,
            ? as ano,
            AVG(punt_global) as punt_global,
            AVG(punt_lectura_critica) as punt_lectura,
            AVG(punt_matematicas) as punt_matematicas,
            AVG(punt_c_naturales) as punt_c_naturales,
            AVG(punt_sociales_ciudadanas) as punt_sociales,
            AVG(punt_ingles) as punt_ingles,
            COUNT(DISTINCT estudiante_sk) as total_estudiantes
        FROM gold.fact_icfes_analytics
        WHERE {where_clause}
    """

    # Agregar ubicacion_label y ano a params al inicio
    full_params = [ubicacion_label, ano] + params

    df = execute_query(query, params=full_params)
    return df.iloc[0].to_dict() if not df.empty else {}


def get_comparacion_colegios(colegio_a_sk, colegio_b_sk, ano=2024):
    """
    Compara dos colegios y retorna métricas comparativas completas.
    
    Args:
        colegio_a_sk: SK del primer colegio
        colegio_b_sk: SK del segundo colegio
        ano: Año de comparación (default: 2024)
    
    Returns:
        dict: Datos comparativos de ambos colegios con diferencias e insights
    """
    query = """
    WITH colegio_a_data AS (
        SELECT 
            f.colegio_sk,
            f.ano,
            COUNT(DISTINCT f.estudiante_sk) as total_estudiantes,
            AVG(f.punt_global) as puntaje_global,
            AVG(f.punt_lectura_critica) as lectura,
            AVG(f.punt_matematicas) as matematicas,
            AVG(f.punt_c_naturales) as ciencias,
            AVG(f.punt_sociales_ciudadanas) as sociales,
            AVG(f.punt_ingles) as ingles,
            AVG(f.global_zscore) as z_score
        FROM gold.fact_icfes_analytics f
        WHERE f.colegio_sk = ? AND f.ano = ?
        GROUP BY f.colegio_sk, f.ano
    ),
    colegio_b_data AS (
        SELECT 
            f.colegio_sk,
            f.ano,
            COUNT(DISTINCT f.estudiante_sk) as total_estudiantes,
            AVG(f.punt_global) as puntaje_global,
            AVG(f.punt_lectura_critica) as lectura,
            AVG(f.punt_matematicas) as matematicas,
            AVG(f.punt_c_naturales) as ciencias,
            AVG(f.punt_sociales_ciudadanas) as sociales,
            AVG(f.punt_ingles) as ingles,
            AVG(f.global_zscore) as z_score
        FROM gold.fact_icfes_analytics f
        WHERE f.colegio_sk = ? AND f.ano = ?
        GROUP BY f.colegio_sk, f.ano
    ),
    promedios_nacionales AS (
        SELECT 
            ano,
            AVG(punt_global) as promedio_nacional_global
        FROM gold.fact_icfes_analytics
        WHERE ano = ?
        GROUP BY ano
    ),
    metadata_a AS (
        SELECT DISTINCT
            colegio_sk,
            nombre_colegio,
            municipio,
            departamento,
            sector,
            codigo_dane
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = ?
        LIMIT 1
    ),
    metadata_b AS (
        SELECT DISTINCT
            colegio_sk,
            nombre_colegio,
            municipio,
            departamento,
            sector,
            codigo_dane
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = ?
        LIMIT 1
    )
    SELECT 
        a.*,
        ma.nombre_colegio,
        ma.municipio,
        ma.departamento,
        ma.sector,
        ma.codigo_dane,
        b.colegio_sk as b_colegio_sk,
        b.total_estudiantes as b_total_estudiantes,
        b.puntaje_global as b_puntaje_global,
        b.lectura as b_lectura,
        b.matematicas as b_matematicas,
        b.ciencias as b_ciencias,
        b.sociales as b_sociales,
        b.ingles as b_ingles,
        b.z_score as b_z_score,
        mb.nombre_colegio as b_nombre_colegio,
        mb.municipio as b_municipio,
        mb.departamento as b_departamento,
        mb.sector as b_sector,
        mb.codigo_dane as b_codigo_dane,
        pn.promedio_nacional_global,
        -- Excellence indicators for colegio A (using scalar subqueries)
        (SELECT i.pct_excelencia_integral 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = ma.codigo_dane AND i.ano = ?
         LIMIT 1) as a_excelencia_integral,
        (SELECT i.pct_competencia_satisfactoria_integral 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = ma.codigo_dane AND i.ano = ?
         LIMIT 1) as a_competencia_satisfactoria,
        (SELECT i.pct_perfil_stem_avanzado 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = ma.codigo_dane AND i.ano = ?
         LIMIT 1) as a_perfil_stem,
        (SELECT i.pct_perfil_humanistico_avanzado 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = ma.codigo_dane AND i.ano = ?
         LIMIT 1) as a_perfil_humanistico,
        (SELECT i.pct_riesgo_alto 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = ma.codigo_dane AND i.ano = ?
         LIMIT 1) as a_riesgo_alto,
        -- Excellence indicators for colegio B (using scalar subqueries)
        (SELECT i.pct_excelencia_integral 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = mb.codigo_dane AND i.ano = ?
         LIMIT 1) as b_excelencia_integral,
        (SELECT i.pct_competencia_satisfactoria_integral 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = mb.codigo_dane AND i.ano = ?
         LIMIT 1) as b_competencia_satisfactoria,
        (SELECT i.pct_perfil_stem_avanzado 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = mb.codigo_dane AND i.ano = ?
         LIMIT 1) as b_perfil_stem,
        (SELECT i.pct_perfil_humanistico_avanzado 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = mb.codigo_dane AND i.ano = ?
         LIMIT 1) as b_perfil_humanistico,
        (SELECT i.pct_riesgo_alto 
         FROM gold.fct_indicadores_desempeno i
         WHERE i.colegio_bk = mb.codigo_dane AND i.ano = ?
         LIMIT 1) as b_riesgo_alto
    FROM colegio_a_data a
    CROSS JOIN colegio_b_data b
    LEFT JOIN promedios_nacionales pn ON a.ano = pn.ano
    LEFT JOIN metadata_a ma ON a.colegio_sk = ma.colegio_sk
    LEFT JOIN metadata_b mb ON b.colegio_sk = mb.colegio_sk
    """
    
    # Parameters: colegio_a_sk, ano (for colegio_a_data), 
    #             colegio_b_sk, ano (for colegio_b_data), 
    #             ano (for promedios_nacionales),
    #             colegio_a_sk (for metadata_a),
    #             colegio_b_sk (for metadata_b),
    #             ano (5 times for each indicator subquery for A),
    #             ano (5 times for each indicator subquery for B)
    params = [
        colegio_a_sk, ano,  # colegio_a_data
        colegio_b_sk, ano,  # colegio_b_data
        ano,                # promedios_nacionales
        colegio_a_sk,       # metadata_a
        colegio_b_sk,       # metadata_b
        ano,  # a_excelencia_integral
        ano,  # a_competencia_satisfactoria
        ano,  # a_perfil_stem
        ano,  # a_perfil_humanistico
        ano,  # a_riesgo_alto
        ano,  # b_excelencia_integral
        ano,  # b_competencia_satisfactoria
        ano,  # b_perfil_stem
        ano,  # b_perfil_humanistico
        ano   # b_riesgo_alto
    ]
    
    df = execute_query(query, params)
    
    if df.empty:
        return {
            'error': 'No se encontraron datos para los colegios especificados',
            'debug': {
                'colegio_a_sk': colegio_a_sk,
                'colegio_b_sk': colegio_b_sk,
                'ano': ano,
                'registros_a': int(test_df_a.iloc[0]['count']),
                'registros_b': int(test_df_b.iloc[0]['count']),
                'anos_disponibles_a': years_a['ano'].tolist() if not years_a.empty else [],
                'anos_disponibles_b': years_b['ano'].tolist() if not years_b.empty else []
            }
        }
    
    row = df.iloc[0]
    
    # Estructura de datos del colegio A
    colegio_a = {
        'sk': row['colegio_sk'],
        'nombre': row['nombre_colegio'],
        'municipio': row['municipio'],
        'departamento': row['departamento'],
        'sector': row['sector'],
        'total_estudiantes': int(row['total_estudiantes']) if pd.notna(row['total_estudiantes']) else 0,
        'puntaje_global': float(row['puntaje_global']) if pd.notna(row['puntaje_global']) else 0,
        'lectura': float(row['lectura']) if pd.notna(row['lectura']) else 0,
        'matematicas': float(row['matematicas']) if pd.notna(row['matematicas']) else 0,
        'ciencias': float(row['ciencias']) if pd.notna(row['ciencias']) else 0,
        'sociales': float(row['sociales']) if pd.notna(row['sociales']) else 0,
        'ingles': float(row['ingles']) if pd.notna(row['ingles']) else 0,
        'z_score': float(row['z_score']) if pd.notna(row['z_score']) else 0,
        'promedio_nacional': float(row['promedio_nacional_global']) if pd.notna(row['promedio_nacional_global']) else 0,
        'excelencia_integral': float(row['a_excelencia_integral']) if pd.notna(row['a_excelencia_integral']) else 0,
        'competencia_satisfactoria': float(row['a_competencia_satisfactoria']) if pd.notna(row['a_competencia_satisfactoria']) else 0,
        'perfil_stem': float(row['a_perfil_stem']) if pd.notna(row['a_perfil_stem']) else 0,
        'perfil_humanistico': float(row['a_perfil_humanistico']) if pd.notna(row['a_perfil_humanistico']) else 0,
        'riesgo_alto': float(row['a_riesgo_alto']) if pd.notna(row['a_riesgo_alto']) else 0
    }
    
    # Estructura de datos del colegio B
    colegio_b = {
        'sk': row['b_colegio_sk'],
        'nombre': row['b_nombre_colegio'],
        'municipio': row['b_municipio'],
        'departamento': row['b_departamento'],
        'sector': row['b_sector'],
        'total_estudiantes': int(row['b_total_estudiantes']) if pd.notna(row['b_total_estudiantes']) else 0,
        'puntaje_global': float(row['b_puntaje_global']) if pd.notna(row['b_puntaje_global']) else 0,
        'lectura': float(row['b_lectura']) if pd.notna(row['b_lectura']) else 0,
        'matematicas': float(row['b_matematicas']) if pd.notna(row['b_matematicas']) else 0,
        'ciencias': float(row['b_ciencias']) if pd.notna(row['b_ciencias']) else 0,
        'sociales': float(row['b_sociales']) if pd.notna(row['b_sociales']) else 0,
        'ingles': float(row['b_ingles']) if pd.notna(row['b_ingles']) else 0,
        'z_score': float(row['b_z_score']) if pd.notna(row['b_z_score']) else 0,
        'promedio_nacional': float(row['promedio_nacional_global']) if pd.notna(row['promedio_nacional_global']) else 0,
        'excelencia_integral': float(row['b_excelencia_integral']) if pd.notna(row['b_excelencia_integral']) else 0,
        'competencia_satisfactoria': float(row['b_competencia_satisfactoria']) if pd.notna(row['b_competencia_satisfactoria']) else 0,
        'perfil_stem': float(row['b_perfil_stem']) if pd.notna(row['b_perfil_stem']) else 0,
        'perfil_humanistico': float(row['b_perfil_humanistico']) if pd.notna(row['b_perfil_humanistico']) else 0,
        'riesgo_alto': float(row['b_riesgo_alto']) if pd.notna(row['b_riesgo_alto']) else 0
    }
    
    # Calcular diferencias
    materias = ['lectura', 'matematicas', 'ciencias', 'sociales', 'ingles']
    diferencias = {
        'puntaje_global': {
            'absoluta': round(colegio_a['puntaje_global'] - colegio_b['puntaje_global'], 2),
            'porcentual': round(((colegio_a['puntaje_global'] - colegio_b['puntaje_global']) / colegio_b['puntaje_global'] * 100), 2) if colegio_b['puntaje_global'] > 0 else 0,
            'ganador': 'colegio_a' if colegio_a['puntaje_global'] > colegio_b['puntaje_global'] else 'colegio_b'
        },
        'z_score': {
            'absoluta': round(colegio_a['z_score'] - colegio_b['z_score'], 2),
            'interpretacion': _interpretar_diferencia_zscore(colegio_a['z_score'] - colegio_b['z_score'])
        }
    }
    
    # Diferencias por materia
    for materia in materias:
        diff = colegio_a[materia] - colegio_b[materia]
        diferencias[materia] = {
            'absoluta': round(diff, 2),
            'porcentual': round((diff / colegio_b[materia] * 100), 2) if colegio_b[materia] > 0 else 0,
            'ganador': 'colegio_a' if diff > 0 else 'colegio_b'
        }
    
    # Generar insights automáticos
    insights = _generar_insights_comparacion(colegio_a, colegio_b, diferencias)
    
    return {
        'ano': int(ano),
        'colegio_a': colegio_a,
        'colegio_b': colegio_b,
        'diferencias': diferencias,
        'insights': insights
    }


def _interpretar_diferencia_zscore(diff):
    """Interpreta la diferencia de Z-Score entre dos colegios"""
    if diff > 1.5:
        return "Colegio A significativamente superior"
    elif diff > 0.5:
        return "Colegio A superior"
    elif diff > -0.5:
        return "Rendimiento similar"
    elif diff > -1.5:
        return "Colegio B superior"
    else:
        return "Colegio B significativamente superior"


def _generar_insights_comparacion(colegio_a, colegio_b, diferencias):
    """Genera insights automáticos de la comparación"""
    insights = []
    
    # Comparación global
    if diferencias['puntaje_global']['ganador'] == 'colegio_a':
        insights.append(f"🏆 {colegio_a['nombre']} supera a {colegio_b['nombre']} por {diferencias['puntaje_global']['absoluta']} puntos ({diferencias['puntaje_global']['porcentual']}%)")
    else:
        insights.append(f"🏆 {colegio_b['nombre']} supera a {colegio_a['nombre']} por {abs(diferencias['puntaje_global']['absoluta'])} puntos ({abs(diferencias['puntaje_global']['porcentual'])}%)")
    
    # Materias donde A es mejor
    materias_a_mejor = []
    materias_b_mejor = []
    for materia in ['lectura', 'matematicas', 'ciencias', 'sociales', 'ingles']:
        if diferencias[materia]['ganador'] == 'colegio_a':
            materias_a_mejor.append((materia, diferencias[materia]['absoluta']))
        else:
            materias_b_mejor.append((materia, abs(diferencias[materia]['absoluta'])))
    
    if len(materias_a_mejor) == 5:
        insights.append(f"✅ {colegio_a['nombre']} supera en todas las materias")
    elif len(materias_b_mejor) == 5:
        insights.append(f"✅ {colegio_b['nombre']} supera en todas las materias")
    else:
        insights.append(f"📊 {colegio_a['nombre']} es mejor en {len(materias_a_mejor)} materias, {colegio_b['nombre']} en {len(materias_b_mejor)}")
    
    # Mayor brecha
    todas_materias = materias_a_mejor + materias_b_mejor
    if todas_materias:
        mayor_brecha = max(todas_materias, key=lambda x: x[1])
        nombre_materia = {
            'lectura': 'Lectura Crítica',
            'matematicas': 'Matemáticas',
            'ciencias': 'C. Naturales',
            'sociales': 'Sociales',
            'ingles': 'Inglés'
        }.get(mayor_brecha[0], mayor_brecha[0])
        insights.append(f"📈 Mayor brecha en {nombre_materia}: {mayor_brecha[1]:.1f} puntos")
    
    # Comparación con promedio nacional
    if colegio_a['puntaje_global'] > colegio_a['promedio_nacional'] and colegio_b['puntaje_global'] > colegio_b['promedio_nacional']:
        insights.append("✓ Ambos colegios están por encima del promedio nacional")
    elif colegio_a['puntaje_global'] < colegio_a['promedio_nacional'] and colegio_b['puntaje_global'] < colegio_b['promedio_nacional']:
        insights.append("⚠ Ambos colegios están por debajo del promedio nacional")
    
    # Excelencia
    if colegio_a['excelencia_integral'] > 0 and colegio_b['excelencia_integral'] > 0:
        ratio = colegio_a['excelencia_integral'] / colegio_b['excelencia_integral'] if colegio_b['excelencia_integral'] > 0 else 0
        if ratio > 2:
            insights.append(f"⭐ {colegio_a['nombre']} tiene {ratio:.1f}x más estudiantes con Excelencia Integral")
        elif ratio < 0.5:
            insights.append(f"⭐ {colegio_b['nombre']} tiene {1/ratio:.1f}x más estudiantes con Excelencia Integral")
    
    # Riesgo alto
    if colegio_a['riesgo_alto'] > colegio_b['riesgo_alto'] * 1.5:
        insights.append(f"⚠ {colegio_a['nombre']} tiene mayor porcentaje de estudiantes en riesgo alto ({colegio_a['riesgo_alto']:.1f}%)")
    elif colegio_b['riesgo_alto'] > colegio_a['riesgo_alto'] * 1.5:
        insights.append(f"⚠ {colegio_b['nombre']} tiene mayor porcentaje de estudiantes en riesgo alto ({colegio_b['riesgo_alto']:.1f}%)")
    
    # Sector
    if colegio_a['sector'] != colegio_b['sector']:
        insights.append(f"🏫 Comparación entre sectores: {colegio_a['sector']} vs {colegio_b['sector']}")
    
    return insights

