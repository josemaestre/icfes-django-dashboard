"""
Utilidades para trabajar con DuckDB en el dashboard ICFES.
"""
import logging
import duckdb
import pandas as pd
import numpy as np
from django.conf import settings
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

# Schema configuration: 'gold' for dev (dev.duckdb), 'main' for prod (prod.duckdb)
# Detection: explicit setting > DB path check > default 'gold'
def _detect_schema():
    explicit = getattr(settings, 'ICFES_DB_SCHEMA', None)
    if explicit:
        return explicit
    db_path = getattr(settings, 'ICFES_DUCKDB_PATH', '')
    if db_path.startswith('s3://') or 'prod.duckdb' in db_path:
        return 'main'
    return 'gold'


SCHEMA = _detect_schema()


def resolve_schema(query):
    """Replace gold. prefix with the correct schema for the current environment."""
    if SCHEMA != 'gold':
        return query.replace('gold.', f'{SCHEMA}.')
    return query


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
            
            # Get existing tables in gold schema to avoid conflicts
            existing_gold_tables = set()
            try:
                gold_tables = temp_conn.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'gold'
                """).fetchall()
                existing_gold_tables = {table[0] for table in gold_tables}
                logger.info(f"Found {len(existing_gold_tables)} existing tables in gold schema")
            except Exception as e:
                logger.warning(f"Could not check existing gold tables: {e}")
            
            # Crear vistas gold.* -> source_schema.* (skip if already exists in gold)
            views_created = 0
            views_skipped = 0
            for (table_name,) in tables:
                # Skip if table already exists in gold
                if table_name in existing_gold_tables:
                    views_skipped += 1
                    continue
                try:
                    temp_conn.execute(f"CREATE OR REPLACE VIEW gold.{table_name} AS SELECT * FROM {source_schema}.{table_name}")
                    views_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create view for {table_name}: {e}")
            
            temp_conn.close()
            logger.info(f"Successfully created {views_created} gold schema views from {source_schema}, skipped {views_skipped} existing tables")
            
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
            
            # Conectar al archivo local en modo read-only para queries
            con = duckdb.connect(local_path, read_only=read_only)
        else:
            # Conexión local tradicional
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
        try:
            resolved = resolve_schema(query)
            if params:
                result = con.execute(resolved, params).df()
            else:
                result = con.execute(resolved).df()
            
            # Limpiar NaN, NaT e infinitos para JSON
            result = result.replace([pd.NA, np.nan, np.inf, -np.inf], None)
            return result
            
        except duckdb.CatalogException as e:
            # Fallback: Si falla buscando en 'gold' y sugiere 'prod', reintentar cambiando el schema
            error_msg = str(e)
            if 'Did you mean "prod.' in error_msg or 'Table with name' in error_msg:
                import logging
                logger = logging.getLogger(__name__)
                
                # Intentar reemplazar gold. por prod.
                new_query = query.replace('gold.', 'prod.')
                
                # Si no hubo cambios (no había gold), intentar reemplazar main. por prod.
                if new_query == query:
                    new_query = query.replace('main.', 'prod.')
                
                if new_query != query:
                    logger.warning(f"Catalog error using 'gold/main' schema. Retrying with 'prod' schema. Error: {e}")
                    try:
                        if params:
                            result = con.execute(new_query, params).df()
                        else:
                            result = con.execute(new_query).df()
                        
                        result = result.replace([pd.NA, np.nan, np.inf, -np.inf], None)
                        return result
                    except Exception as retry_e:
                        logger.error(f"Fallback query failed: {retry_e}")
                        raise e  # Raise original if fallback fails too
            
            raise e


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


# =============================================================================
# BRECHA EDUCATIVA: Oficial vs No Oficial
# Optimizado: usa tablas pre-agregadas del schema gold
# =============================================================================

# Expresión SQL que normaliza los distintos valores de sector en icfes_master_resumen
_SECTOR_NORM = """
    CASE
        WHEN UPPER(cole_naturaleza) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN 'NO_OFICIAL'
        WHEN UPPER(cole_naturaleza) = 'OFICIAL' OR cole_naturaleza = '1'  THEN 'OFICIAL'
        ELSE NULL
    END
"""

# Para fct_colegio_historico / fct_indicadores_desempeno (campo 'sector')
_SECTOR_NORM_FCH = """
    CASE
        WHEN UPPER(sector) IN ('NO_OFICIAL', 'NO OFICIAL', '0') THEN 'NO_OFICIAL'
        WHEN UPPER(sector) = 'OFICIAL' OR sector = '1'          THEN 'OFICIAL'
        ELSE NULL
    END
"""


def get_brecha_kpis(ano=None, departamento=None):
    """
    KPIs del dashboard de brechas.
    Fuente: gold.icfes_master_resumen (pre-agregado por colegio×año).
    """
    params  = []
    where_clauses = ["m.estudiantes > 0"]
    
    if ano:
        where_clauses.append("m.ano = ?")
        params.append(str(ano))
        
    if departamento:
        if isinstance(departamento, list):
            pl = ", ".join(["?"] * len(departamento))
            where_clauses.append(f"m.cole_depto_ubicacion IN ({pl})")
            params.extend(departamento)
        else:
            where_clauses.append("m.cole_depto_ubicacion = ?")
            params.append(departamento)
        
    where_stmt = " AND ".join(where_clauses)

    query = f"""
        SELECT
            {_SECTOR_NORM} AS sector_norm,
            COUNT(DISTINCT m.cole_cod_dane_establecimiento) AS total_colegios,
            SUM(m.estudiantes)                              AS total_estudiantes,
            ROUND(SUM(m.avg_global      * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_global,
            ROUND(SUM(m.avg_matematicas * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_matematicas,
            ROUND(SUM(m.avg_lectura     * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_lectura,
            ROUND(SUM(m.avg_ingles      * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_ingles
        FROM gold.icfes_master_resumen m
        WHERE {where_stmt}
        GROUP BY sector_norm
        HAVING sector_norm IS NOT NULL
    """

    try:
        df = execute_query(query, params=params or None)
        if df.empty:
            return {}

        result = {}
        for _, row in df.iterrows():
            sector = row['sector_norm']
            result[sector] = {
                'total_colegios':      int(row['total_colegios'])      if row['total_colegios']      is not None else 0,
                'total_estudiantes':   int(row['total_estudiantes'])   if row['total_estudiantes']   is not None else 0,
                'promedio_global':     float(row['promedio_global'])   if row['promedio_global']     is not None else 0,
                'promedio_matematicas':float(row['promedio_matematicas']) if row['promedio_matematicas'] is not None else 0,
                'promedio_lectura':    float(row['promedio_lectura'])  if row['promedio_lectura']    is not None else 0,
                'promedio_ingles':     float(row['promedio_ingles'])   if row['promedio_ingles']     is not None else 0,
            }

        if 'OFICIAL' in result and 'NO_OFICIAL' in result:
            result['brecha_global'] = round(
                result['NO_OFICIAL']['promedio_global'] - result['OFICIAL']['promedio_global'], 2
            )
        else:
            result['brecha_global'] = 0

        return result

    except Exception as e:
        logger.error(f"Error in get_brecha_kpis: {e}")
        return {}


def get_brecha_por_materia(ano=None, departamento=None):
    """
    Puntajes promedio por materia separados por sector.
    Fuente: gold.icfes_master_resumen.
    """
    params  = []
    where_clauses = ["m.estudiantes > 0"]
    
    if ano:
        where_clauses.append("m.ano = ?")
        params.append(str(ano))
        
    if departamento:
        if isinstance(departamento, list):
            pl = ", ".join(["?"] * len(departamento))
            where_clauses.append(f"m.cole_depto_ubicacion IN ({pl})")
            params.extend(departamento)
        else:
            where_clauses.append("m.cole_depto_ubicacion = ?")
            params.append(departamento)
        
    where_stmt = " AND ".join(where_clauses)

    query = f"""
        SELECT
            {_SECTOR_NORM} AS sector_norm,
            ROUND(SUM(m.avg_global      * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS global,
            ROUND(SUM(m.avg_lectura     * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS lectura_critica,
            ROUND(SUM(m.avg_matematicas * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS matematicas,
            ROUND(SUM(m.avg_naturales   * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS ciencias_naturales,
            ROUND(SUM(m.avg_sociales    * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS sociales_ciudadanas,
            ROUND(SUM(m.avg_ingles      * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS ingles
        FROM gold.icfes_master_resumen m
        WHERE {where_stmt}
        GROUP BY sector_norm
        HAVING sector_norm IS NOT NULL
    """

    try:
        df = execute_query(query, params=params or None)
        return df.to_dict('records') if not df.empty else []
    except Exception as e:
        logger.error(f"Error in get_brecha_por_materia: {e}")
        return []


def get_tendencia_historica_sector(departamento=None, ano=None):
    """
    Evolución histórica del puntaje global por sector.
    Fuente: gold.icfes_master_resumen.
    """
    params  = []
    where_clauses = ["m.estudiantes > 0"]
    
    if departamento:
        if isinstance(departamento, list):
            pl = ", ".join(["?"] * len(departamento))
            where_clauses.append(f"m.cole_depto_ubicacion IN ({pl})")
            params.extend(departamento)
        else:
            where_clauses.append("m.cole_depto_ubicacion = ?")
            params.append(departamento)
        
    if ano:
        where_clauses.append("m.ano <= ?")
        params.append(str(ano))
        
    where_stmt = " AND ".join(where_clauses)

    query = f"""
        SELECT
            m.ano,
            {_SECTOR_NORM} AS sector_norm,
            ROUND(SUM(m.avg_global      * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_global,
            ROUND(SUM(m.avg_matematicas * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_matematicas,
            ROUND(SUM(m.avg_lectura     * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_lectura,
            ROUND(SUM(m.avg_ingles      * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_ingles,
            SUM(m.estudiantes) AS total_estudiantes
        FROM gold.icfes_master_resumen m
        WHERE {where_stmt}
        GROUP BY m.ano, sector_norm
        HAVING sector_norm IS NOT NULL
        ORDER BY m.ano ASC, sector_norm
    """

    try:
        print("QUERY TO EXECUTE:", query)
        df = execute_query(query, params=params or None)
        return df.to_dict('records') if not df.empty else []
    except Exception as e:
        logger.error(f"Error in get_tendencia_historica_sector: {e}")
        raise e


def get_niveles_desempeno_sector(ano=None, departamento=None):
    """
    Distribución de niveles de desempeño global (promedio de las materias) por sector.
    """
    try:
        params  = []
        where_clauses = ["dc.sector_norm IS NOT NULL"]

        if ano:
            where_clauses.append("i.ano = ?")
            params.append(str(ano))

        if departamento:
            if isinstance(departamento, list):
                pl = ", ".join(["?"] * len(departamento))
                where_clauses.append(f"dc.cole_depto_ubicacion IN ({pl})")
                params.extend(departamento)
            else:
                where_clauses.append("dc.cole_depto_ubicacion = ?")
                params.append(departamento)

        where_stmt = " AND ".join(where_clauses)

        query = f"""
            SELECT
                dc.sector_norm,
                SUM(i.lc_nivel_1_insuficiente + i.mat_nivel_1_insuficiente + i.cn_nivel_1_insuficiente + i.sc_nivel_1_insuficiente + i.ing_nivel_pre_a1) AS insuf_abs,
                SUM(i.lc_nivel_2_minimo + i.mat_nivel_2_minimo + i.cn_nivel_2_minimo + i.sc_nivel_2_minimo + i.ing_nivel_a1) AS min_abs,
                SUM(i.lc_nivel_3_satisfactorio + i.mat_nivel_3_satisfactorio + i.cn_nivel_3_satisfactorio + i.sc_nivel_3_satisfactorio + i.ing_nivel_a2) AS sat_abs,
                SUM(i.lc_nivel_4_avanzado + i.mat_nivel_4_avanzado + i.cn_nivel_4_avanzado + i.sc_nivel_4_avanzado + i.ing_nivel_b1) AS avz_abs,
                SUM(i.total_estudiantes * 5) AS total_mediciones,
                COUNT(DISTINCT i.colegio_bk) AS total_colegios
            FROM gold.fct_indicadores_desempeno i
            JOIN (
                SELECT DISTINCT
                    CAST(cole_cod_dane_establecimiento AS VARCHAR) AS codigo_dane,
                    cole_depto_ubicacion,
                    {_SECTOR_NORM} AS sector_norm
                FROM gold.icfes_master_resumen
                WHERE cole_naturaleza IS NOT NULL
            ) dc ON CAST(i.colegio_bk AS VARCHAR) = dc.codigo_dane
            WHERE {where_stmt}
            GROUP BY dc.sector_norm
        """

        df = execute_query(query, params=params or None)
        if df.empty:
            return []
            
        result = []
        for _, row in df.iterrows():
            insuf = float(row['insuf_abs'] or 0)
            mini  = float(row['min_abs'] or 0)
            sat   = float(row['sat_abs'] or 0)
            avz   = float(row['avz_abs'] or 0)
            total = insuf + mini + sat + avz
            if total == 0:
                total = 1
                
            result.append({
                'sector_norm': row['sector_norm'],
                'pct_insuficiente': round((insuf / total) * 100, 2),
                'pct_minimo': round((mini / total) * 100, 2),
                'pct_satisfactorio': round((sat / total) * 100, 2),
                'pct_avanzado': round((avz / total) * 100, 2),
                'total_colegios': row['total_colegios']
            })
        return result

    except Exception as e:
        logger.error(f"Error in get_niveles_desempeno_sector: {e}")
        return []


def get_brecha_departamental(ano=None, departamento=None):
    """
    Brecha entre sector oficial y no oficial por departamento.
    Fuente: gold.icfes_master_resumen agrupado por depto × sector.
    """
    params = []
    where_clauses = ["m.estudiantes > 0"]
    
    if ano:
        where_clauses.append("m.ano = ?")
        params.append(str(ano))
        
    if departamento:
        if isinstance(departamento, list):
            pl = ", ".join(["?"] * len(departamento))
            where_clauses.append(f"m.cole_depto_ubicacion IN ({pl})")
            params.extend(departamento)
        else:
            where_clauses.append("m.cole_depto_ubicacion = ?")
            params.append(departamento)
        
    where_stmt = " AND ".join(where_clauses) if where_clauses else "1=1"

    query = f"""
        SELECT 
            m.cole_depto_ubicacion AS departamento,
            {_SECTOR_NORM} AS sector,
            ROUND(SUM(m.avg_global * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS promedio_global,
            COUNT(DISTINCT m.cole_cod_dane_establecimiento) AS total_colegios
        FROM gold.icfes_master_resumen m
        WHERE {where_stmt}
        GROUP BY m.cole_depto_ubicacion, sector
        HAVING sector IS NOT NULL AND m.cole_depto_ubicacion IS NOT NULL
        ORDER BY m.cole_depto_ubicacion
    """

    try:
        df = execute_query(query, params=params or None)
        if df.empty:
            return []

        result = {}
        for _, row in df.iterrows():
            depto  = row['departamento']
            sector = row['sector']
            if depto not in result:
                result[depto] = {
                    'departamento':             depto,
                    'OFICIAL':                  None,
                    'NO_OFICIAL':               None,
                    'total_colegios_oficial':    0,
                    'total_colegios_no_oficial': 0,
                }
            result[depto][sector] = float(row['promedio_global']) if row['promedio_global'] is not None else None
            if sector == 'OFICIAL':
                result[depto]['total_colegios_oficial']    = int(row['total_colegios'])
            else:
                result[depto]['total_colegios_no_oficial'] = int(row['total_colegios'])

        final = []
        for depto, data in result.items():
            if data['OFICIAL'] is not None and data['NO_OFICIAL'] is not None:
                data['brecha']     = round(data['NO_OFICIAL'] - data['OFICIAL'], 2)
                data['publico_gana'] = data['OFICIAL'] > data['NO_OFICIAL']
            else:
                data['brecha']     = None
                data['publico_gana'] = False
            final.append(data)

        final.sort(key=lambda x: abs(x['brecha']) if x['brecha'] is not None else 0, reverse=True)
        return final

    except Exception as e:
        logger.error(f"Error in get_brecha_departamental: {e}")
        return []


def get_niveles_por_materia_sector(ano=None, departamento=None):
    """
    Distribución de niveles (Insuficiente/Mínimo/Satisfactorio/Avanzado) por materia y sector.
    Fuente: gold.fct_indicadores_desempeno  — UN SOLO SCAN.
    Usa icfes_master_resumen para sector (más cobertura que fct_colegio_historico) y para promedios.
    """
    params  = []
    where_clauses1 = ["dc.sector_norm IS NOT NULL"]

    if ano:
        where_clauses1.append("i.ano = ?")
        params.append(str(ano))

    if departamento:
        if isinstance(departamento, list):
            pl = ", ".join(["?"] * len(departamento))
            where_clauses1.append(f"dc.cole_depto_ubicacion IN ({pl})")
            params.extend(departamento)
        else:
            where_clauses1.append("dc.cole_depto_ubicacion = ?")
            params.append(departamento)

    where_stmt1 = " AND ".join(where_clauses1)

    query = f"""
        SELECT
            dc.sector_norm,
            -- Lectura Crítica
            SUM(i.lc_nivel_1_insuficiente)   AS lc_insuf_abs,
            SUM(i.lc_nivel_2_minimo)         AS lc_min_abs,
            SUM(i.lc_nivel_3_satisfactorio)  AS lc_sat_abs,
            SUM(i.lc_nivel_4_avanzado)       AS lc_avz_abs,
            SUM(i.total_estudiantes)         AS lc_total,
            -- Matemáticas
            SUM(i.mat_nivel_1_insuficiente)  AS mat_insuf_abs,
            SUM(i.mat_nivel_2_minimo)        AS mat_min_abs,
            SUM(i.mat_nivel_3_satisfactorio) AS mat_sat_abs,
            SUM(i.mat_nivel_4_avanzado)      AS mat_avz_abs,
            SUM(i.total_estudiantes)         AS mat_total,
            -- Ciencias Naturales
            SUM(i.cn_nivel_1_insuficiente)   AS cn_insuf_abs,
            SUM(i.cn_nivel_2_minimo)         AS cn_min_abs,
            SUM(i.cn_nivel_3_satisfactorio)  AS cn_sat_abs,
            SUM(i.cn_nivel_4_avanzado)       AS cn_avz_abs,
            SUM(i.total_estudiantes)         AS cn_total,
            -- Sociales Ciudadanas
            SUM(i.sc_nivel_1_insuficiente)   AS soc_insuf_abs,
            SUM(i.sc_nivel_2_minimo)         AS soc_min_abs,
            SUM(i.sc_nivel_3_satisfactorio)  AS soc_sat_abs,
            SUM(i.sc_nivel_4_avanzado)       AS soc_avz_abs,
            SUM(i.total_estudiantes)         AS soc_total,
            -- Inglés
            SUM(i.ing_nivel_pre_a1)          AS ing_insuf_abs,
            SUM(i.ing_nivel_a1)              AS ing_min_abs,
            SUM(i.ing_nivel_a2)              AS ing_sat_abs,
            SUM(i.ing_nivel_b1)              AS ing_avz_abs,
            SUM(i.total_estudiantes)         AS ing_total
        FROM gold.fct_indicadores_desempeno i
        JOIN (
            SELECT DISTINCT
                CAST(cole_cod_dane_establecimiento AS VARCHAR) AS codigo_dane,
                cole_depto_ubicacion,
                {_SECTOR_NORM} AS sector_norm
            FROM gold.icfes_master_resumen
            WHERE cole_naturaleza IS NOT NULL
        ) dc ON CAST(i.colegio_bk AS VARCHAR) = dc.codigo_dane
        WHERE {where_stmt1}
        GROUP BY dc.sector_norm
    """

    materias = [
        ('lectura_critica',      'lc'),
        ('matematicas',          'mat'),
        ('ciencias_naturales',   'cn'),
        ('sociales_ciudadanas',  'soc'),
        ('ingles',               'ing'),
    ]

    try:
        df = execute_query(query, params=params or None)

        # Promedios por materia desde icfes_master_resumen (siempre disponibles)
        avg_where_clauses = ["m.estudiantes > 0"]
        if ano:
            avg_where_clauses.append("m.ano = ?")
        if departamento:
            if isinstance(departamento, list):
                pl = ", ".join(["?"] * len(departamento))
                avg_where_clauses.append(f"m.cole_depto_ubicacion IN ({pl})")
            else:
                avg_where_clauses.append("m.cole_depto_ubicacion = ?")

        avg_query = f"""
            SELECT
                {_SECTOR_NORM} AS sector_norm,
                ROUND(SUM(m.avg_lectura     * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS lectura_critica,
                ROUND(SUM(m.avg_matematicas * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS matematicas,
                ROUND(SUM(m.avg_naturales   * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS ciencias_naturales,
                ROUND(SUM(m.avg_sociales    * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS sociales_ciudadanas,
                ROUND(SUM(m.avg_ingles      * m.estudiantes) / NULLIF(SUM(m.estudiantes), 0), 2) AS ingles
            FROM gold.icfes_master_resumen m
            WHERE {" AND ".join(avg_where_clauses)}
            GROUP BY sector_norm
            HAVING sector_norm IS NOT NULL
        """
        avg_df = execute_query(avg_query, params=params or None)
        avg_lookup = {}
        if not avg_df.empty:
            for _, arow in avg_df.iterrows():
                sec = arow['sector_norm']
                avg_lookup[sec] = {
                    mat: float(arow[mat]) if arow[mat] is not None else None
                    for mat in ('lectura_critica', 'matematicas', 'ciencias_naturales',
                                'sociales_ciudadanas', 'ingles')
                }

        if df.empty:
            return []

        rows_out = []
        for _, row in df.iterrows():
            sector = row['sector_norm']
            for mat_name, pfx in materias:
                insuf = float(row[f'{pfx}_insuf_abs'] or 0)
                mini  = float(row[f'{pfx}_min_abs'] or 0)
                sat   = float(row[f'{pfx}_sat_abs'] or 0)
                avz   = float(row[f'{pfx}_avz_abs'] or 0)
                total = insuf + mini + sat + avz
                if total == 0:
                    total = 1
                    
                rows_out.append({
                    'sector_norm':       sector,
                    'materia':           mat_name,
                    'pct_insuficiente':  round(insuf * 100 / total, 2),
                    'pct_minimo':        round(mini * 100 / total, 2),
                    'pct_satisfactorio': round(sat * 100 / total, 2),
                    'pct_avanzado':      round(avz * 100 / total, 2),
                    'promedio':          avg_lookup.get(sector, {}).get(mat_name),
                })
        return rows_out

    except Exception as e:
        logger.error(f"Error in get_niveles_por_materia_sector: {e}")
        return []


# =============================================================================
# NUEVAS FUNCIONES — features del dashboard
# =============================================================================

def get_convergencia_regional(ano=None):
    """
    Brecha entre regiones geográficas y estado de convergencia.
    Fuente: gold.convergencia_regional (pre-calculado).
    Si el año solicitado excede el máximo disponible, retorna el más reciente.
    """
    try:
        # Tabla solo llega a 2022 — tomar el valor más cercano disponible
        if ano:
            query = """
                SELECT * FROM gold.convergencia_regional
                WHERE ano <= ?
                ORDER BY ano DESC LIMIT 1
            """
            df = execute_query(query, params=[str(ano)])
        else:
            query = "SELECT * FROM gold.convergencia_regional ORDER BY ano DESC LIMIT 1"
            df = execute_query(query)

        if df.empty:
            return {}

        row = df.iloc[0].to_dict()

        # detalle_regiones puede venir como string JSON
        import json
        detalle = row.get('detalle_regiones')
        if isinstance(detalle, str):
            try:
                detalle = json.loads(detalle)
            except Exception:
                detalle = []

        return {
            'ano':                  row.get('ano'),
            'promedio_nacional':    row.get('promedio_nacional'),
            'desviacion_estandar':  row.get('desviacion_estandar'),
            'brecha_lider_rezagada':row.get('brecha_lider_rezagado'),
            'estado_convergencia':  row.get('estado_convergencia'),
            'tendencia_brecha':     row.get('tendencia_brecha'),
            'regiones':             detalle,
        }

    except Exception as e:
        logger.error(f"Error in get_convergencia_regional: {e}")
        return {}


def get_tendencia_brecha_sector(ano=None, departamento=None):
    """
    Evolución histórica de la brecha entre sector público y privado.
    Calculado dinámicamente desde gold.icfes_master_resumen para soportar filtros.
    """
    try:
        params  = []
        where_clauses = ["m.estudiantes > 0"]

        if ano:
            where_clauses.append("m.ano <= ?")
            params.append(str(ano))

        if departamento:
            if isinstance(departamento, list):
                pl = ", ".join(["?"] * len(departamento))
                where_clauses.append(f"m.cole_depto_ubicacion IN ({pl})")
                params.extend(departamento)
            else:
                where_clauses.append("m.cole_depto_ubicacion = ?")
                params.append(departamento)

        where_stmt = " AND ".join(where_clauses)

        query = f"""
            WITH promedios AS (
                SELECT
                    m.ano,
                    {_SECTOR_NORM} AS sector_norm,
                    ROUND(SUM(m.avg_global * m.estudiantes) / NULLIF(SUM(m.estudiantes),0), 2) AS promedio_global
                FROM gold.icfes_master_resumen m
                WHERE {where_stmt}
                GROUP BY m.ano, sector_norm
                HAVING sector_norm IS NOT NULL
            )
            SELECT
                t1.ano,
                t1.promedio_global AS puntaje_publico,
                t2.promedio_global AS puntaje_privado,
                ROUND(t2.promedio_global - t1.promedio_global, 2) AS brecha_absoluta_puntos
            FROM (SELECT * FROM promedios WHERE sector_norm = 'OFICIAL') t1
            LEFT JOIN (SELECT * FROM promedios WHERE sector_norm = 'NO_OFICIAL') t2
              ON t1.ano = t2.ano
            ORDER BY t1.ano ASC
        """

        df = execute_query(query, params=params or None)
        return df.to_dict('records') if not df.empty else []

    except Exception as e:
        logger.error(f"Error in get_tendencia_brecha_sector: {e}")
        return []


def get_fortalezas_sector(ano=None, departamento=None):
    """
    Distribución de mejor y peor área por sector (% de colegios).
    Fuente: gold.icfes_master_resumen (columnas mejor_area, peor_area).
    """
    params  = []
    where_clauses = ["mejor_area IS NOT NULL", "peor_area IS NOT NULL"]

    if ano:
        where_clauses.append("ano = ?")
        params.append(str(ano))

    if departamento:
        if isinstance(departamento, list):
            pl = ", ".join(["?"] * len(departamento))
            where_clauses.append(f"cole_depto_ubicacion IN ({pl})")
            params.extend(departamento)
        else:
            where_clauses.append("cole_depto_ubicacion = ?")
            params.append(departamento)
        
    where_stmt = " AND ".join(where_clauses)

    query = f"""
        SELECT
            {_SECTOR_NORM}  AS sector_norm,
            mejor_area,
            peor_area,
            COUNT(*)        AS total_colegios
        FROM gold.icfes_master_resumen
        WHERE {where_stmt}
        GROUP BY sector_norm, mejor_area, peor_area
        HAVING sector_norm IS NOT NULL
        ORDER BY sector_norm, total_colegios DESC
    """

    try:
        df = execute_query(query, params=params or None)
        if df.empty:
            return {}

        result = {'OFICIAL': {}, 'NO_OFICIAL': {}}

        # Aggregate best/worst area counts per sector
        for sector in ['OFICIAL', 'NO_OFICIAL']:
            sub = df[df['sector_norm'] == sector]
            if sub.empty:
                continue
            total = sub['total_colegios'].sum()

            mejor_counts = sub.groupby('mejor_area')['total_colegios'].sum().sort_values(ascending=False)
            peor_counts  = sub.groupby('peor_area')['total_colegios'].sum().sort_values(ascending=False)

            result[sector] = {
                'mejor_area': mejor_counts.index[0] if not mejor_counts.empty else None,
                'mejor_area_pct': round(float(mejor_counts.iloc[0]) * 100 / total, 1) if not mejor_counts.empty else 0,
                'peor_area':  peor_counts.index[0] if not peor_counts.empty else None,
                'peor_area_pct': round(float(peor_counts.iloc[0]) * 100 / total, 1) if not peor_counts.empty else 0,
                'mejor_distribucion': [
                    {'area': a, 'pct': round(float(c) * 100 / total, 1)}
                    for a, c in mejor_counts.items()
                ],
                'total_colegios': int(total),
            }

        return result

    except Exception as e:
        logger.error(f"Error in get_fortalezas_sector: {e}")
        return {}


def get_distribucion_zscore_sector(ano=None, departamento=None):
    """
    Distribución de z-scores de puntaje global por sector (buckets).
    Fuente: gold.fact_icfes_resumen_global (zscore_global pre-calculado).
    """
    params  = []
    where_clauses = ["zscore_global IS NOT NULL", "source_level = 'SCHOOL'"]

    if ano:
        where_clauses.append("ano = ?")
        params.append(str(ano))

    if departamento:
        if isinstance(departamento, list):
            pl = ", ".join(["?"] * len(departamento))
            where_clauses.append(f"depto IN ({pl})")
            params.extend(departamento)
        else:
            where_clauses.append("depto = ?")
            params.append(departamento)
        
    where_stmt = " AND ".join(where_clauses)

    query = f"""
        SELECT
            {_SECTOR_NORM.replace('cole_naturaleza', 'cole_naturaleza')} AS sector_norm,
            CASE
                WHEN zscore_global < -2   THEN 'Muy bajo (<-2σ)'
                WHEN zscore_global < -1   THEN 'Bajo (-2σ a -1σ)'
                WHEN zscore_global <= 1   THEN 'Normal (-1σ a 1σ)'
                WHEN zscore_global <= 2   THEN 'Alto (1σ a 2σ)'
                ELSE                           'Muy alto (>2σ)'
            END AS bucket,
            COUNT(*) AS total_colegios
        FROM gold.fact_icfes_resumen_global
        WHERE {where_stmt}
        GROUP BY sector_norm, bucket
        HAVING sector_norm IS NOT NULL
        ORDER BY sector_norm, bucket
    """

    try:
        df = execute_query(query, params=params or None)
        if df.empty:
            return {}

        result = {}
        for _, row in df.iterrows():
            sector = row['sector_norm']
            if sector not in result:
                result[sector] = []
            result[sector].append({
                'bucket': row['bucket'],
                'total':  int(row['total_colegios']),
            })

        return result

    except Exception as e:
        logger.error(f"Error in get_distribucion_zscore_sector: {e}")
        return {}


# ============================================================================
# HISTORIA DE LA EDUCACIÓN COLOMBIANA - Story Data Functions
# ============================================================================

def get_historia_tendencia_nacional():
    """
    Serie anual nacional completa: promedio, estudiantes, colegios.
    Fuente: fct_estadisticas_anuales (2000-2024).
    """
    try:
        query = resolve_schema("""
            SELECT
                ano,
                ROUND(promedio_nacional, 2) AS promedio,
                total_estudiantes,
                total_colegios
            FROM gold.fct_estadisticas_anuales
            WHERE CAST(ano AS INTEGER) >= 2000
            ORDER BY ano
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(query).fetchall()
        return [
            {
                'ano': r[0],
                'promedio': float(r[1]) if r[1] else None,
                'total_estudiantes': int(r[2]) if r[2] else 0,
                'total_colegios': int(r[3]) if r[3] else 0,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error in get_historia_tendencia_nacional: {e}")
        return []


def get_historia_regiones(ano=None):
    """
    Scores y tendencia por región para el año dado (default: más reciente).
    Fuente: tendencias_regionales.
    """
    try:
        query = resolve_schema("""
            SELECT
                region,
                ano,
                ROUND(avg_punt_global, 2)              AS puntaje,
                ROUND(yoy_growth_global_pct, 2)        AS crecimiento_yoy,
                ROUND(tendencia_3y_global, 2)          AS tendencia_3y,
                clasificacion_tendencia,
                clasificacion_aceleracion,
                total_estudiantes,
                total_colegios
            FROM gold.tendencias_regionales
            WHERE ano = (
                SELECT MAX(ano) FROM gold.tendencias_regionales
            )
            ORDER BY puntaje DESC
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(query).fetchall()
        return [
            {
                'region': r[0],
                'ano': r[1],
                'puntaje': float(r[2]) if r[2] else None,
                'crecimiento_yoy': float(r[3]) if r[3] else None,
                'tendencia_3y': float(r[4]) if r[4] else None,
                'clasificacion_tendencia': r[5],
                'clasificacion_aceleracion': r[6],
                'total_estudiantes': int(r[7]) if r[7] else 0,
                'total_colegios': int(r[8]) if r[8] else 0,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error in get_historia_regiones: {e}")
        return []


def get_historia_brechas():
    """
    Evolución histórica de las brechas educativas clave.
    Fuente: brechas_educativas.
    """
    try:
        query = resolve_schema("""
            SELECT
                ano,
                tipo_brecha,
                ROUND(brecha_absoluta_puntos, 2) AS brecha_puntos,
                magnitud_brecha,
                tendencia_brecha
            FROM gold.brechas_educativas
            WHERE tipo_brecha IN (
                'Urbano vs Rural',
                'Regional: Líder vs Rezagada'
            )
            ORDER BY tipo_brecha, ano
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(query).fetchall()
        result = {}
        for r in rows:
            tipo = r[1]
            if tipo not in result:
                result[tipo] = []
            result[tipo].append({
                'ano': r[0],
                'brecha_puntos': float(r[2]) if r[2] else None,
                'magnitud_brecha': r[3],
                'tendencia_brecha': r[4],
            })
        return result
    except Exception as e:
        logger.error(f"Error in get_historia_brechas: {e}")
        return {}


def get_historia_convergencia():
    """
    Evolución de convergencia/divergencia regional año a año.
    Fuente: convergencia_regional.
    """
    try:
        query = resolve_schema("""
            SELECT
                ano,
                ROUND(brecha_lider_rezagado, 2)  AS brecha_lider_rezagado,
                ROUND(coef_variacion_pct, 2)      AS coef_variacion,
                estado_convergencia,
                tendencia_brecha
            FROM gold.convergencia_regional
            ORDER BY ano
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(query).fetchall()
        return [
            {
                'ano': r[0],
                'brecha_lider_rezagado': float(r[1]) if r[1] else None,
                'coef_variacion': float(r[2]) if r[2] else None,
                'estado_convergencia': r[3],
                'tendencia_brecha': r[4],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error in get_historia_convergencia: {e}")
        return []


def get_historia_riesgo():
    """
    Distribución de riesgo de declive por nivel para el año más reciente.
    Fuente: fct_riesgo_colegios.
    """
    try:
        query = resolve_schema("""
            SELECT
                nivel_riesgo,
                COUNT(*)                          AS colegios,
                ROUND(AVG(prob_declive) * 100, 1) AS prob_promedio
            FROM gold.fct_riesgo_colegios
            WHERE ano = (SELECT MAX(ano) FROM gold.fct_riesgo_colegios)
            GROUP BY nivel_riesgo
            ORDER BY prob_promedio DESC
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(query).fetchall()
        return [
            {
                'nivel_riesgo': r[0],
                'colegios': int(r[1]),
                'prob_promedio': float(r[2]) if r[2] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error in get_historia_riesgo: {e}")
        return []


# ============================================================================
# INTELIGENCIA EDUCATIVA - 4 ML-driven Story Data Functions
# ============================================================================

def get_inteligencia_trayectorias():
    """
    Distribución de trayectorias escolares por categoría y por región.
    Categorías: Mejora Significativa, Mejora Leve, Estable, Deterioro Leve, Deterioro Significativo.
    Fuente: fct_colegio_historico.clasificacion_tendencia (año más reciente).
    """
    try:
        q_nacional = resolve_schema("""
            SELECT
                clasificacion_tendencia,
                COUNT(*)                          AS colegios,
                ROUND(AVG(avg_punt_global), 2)    AS puntaje_promedio
            FROM gold.fct_colegio_historico
            WHERE ano = (SELECT MAX(ano) FROM gold.fct_colegio_historico)
            GROUP BY clasificacion_tendencia
            ORDER BY colegios DESC
        """)
        q_regional = resolve_schema("""
            SELECT
                dr.region,
                h.clasificacion_tendencia,
                COUNT(*) AS colegios
            FROM gold.fct_colegio_historico h
            JOIN gold.dim_departamentos_region dr
              ON UPPER(h.departamento) = UPPER(dr.departamento)
            WHERE h.ano = (SELECT MAX(ano) FROM gold.fct_colegio_historico)
            GROUP BY dr.region, h.clasificacion_tendencia
            ORDER BY dr.region, colegios DESC
        """)
        with get_duckdb_connection() as con:
            rows_nac = con.execute(q_nacional).fetchall()
            rows_reg = con.execute(q_regional).fetchall()

        nacional = [
            {
                'clasificacion': r[0],
                'colegios': int(r[1]),
                'puntaje_promedio': float(r[2]) if r[2] else None,
            }
            for r in rows_nac
        ]
        regional = {}
        for r in rows_reg:
            reg = r[0]
            if reg not in regional:
                regional[reg] = []
            regional[reg].append({'clasificacion': r[1], 'colegios': int(r[2])})

        return {'nacional': nacional, 'regional': regional}
    except Exception as e:
        logger.error(f"Error in get_inteligencia_trayectorias: {e}")
        return {}


def get_inteligencia_resilientes(limit=150):
    """
    Colegios OFICIALES en el top 40% nacional (percentil_nacional >= 60).
    Son los colegios públicos que superan la mayoría de los privados.
    Fuente: fct_colegio_comparacion_contexto (año más reciente).
    """
    try:
        q_list = resolve_schema("""
            SELECT
                ctx.nombre_colegio, ctx.departamento, ctx.municipio,
                ROUND(ctx.colegio_global, 1)    AS puntaje_global,
                ROUND(ctx.colegio_ingles, 1)    AS puntaje_ingles,
                ctx.percentil_nacional,
                ctx.clasificacion_vs_nacional,
                ctx.total_estudiantes
            FROM gold.fct_colegio_comparacion_contexto ctx
            WHERE ctx.sector = 'OFICIAL'
              AND ctx.percentil_nacional >= 60
              AND ctx.total_estudiantes >= 10
              AND CAST(ctx.ano AS INTEGER) = (
                SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_colegio_comparacion_contexto
              )
            ORDER BY ctx.percentil_nacional DESC
            LIMIT ?
        """)
        q_depto = resolve_schema("""
            SELECT ctx.departamento, COUNT(*) AS resilientes
            FROM gold.fct_colegio_comparacion_contexto ctx
            WHERE ctx.sector = 'OFICIAL'
              AND ctx.percentil_nacional >= 60
              AND ctx.total_estudiantes >= 10
              AND CAST(ctx.ano AS INTEGER) = (
                SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_colegio_comparacion_contexto
              )
            GROUP BY ctx.departamento
            ORDER BY resilientes DESC
            LIMIT 15
        """)
        with get_duckdb_connection() as con:
            rows_list  = con.execute(q_list,  [limit]).fetchall()
            rows_depto = con.execute(q_depto).fetchall()
            total = con.execute(resolve_schema("""
                SELECT COUNT(*) FROM gold.fct_colegio_comparacion_contexto
                WHERE sector='OFICIAL' AND percentil_nacional >= 60
                  AND total_estudiantes >= 10
                  AND CAST(ano AS INTEGER) = (SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_colegio_comparacion_contexto)
            """)).fetchone()[0]

        return {
            'total': int(total),
            'lista': [
                {
                    'nombre_colegio': r[0], 'departamento': r[1], 'municipio': r[2],
                    'puntaje_global': float(r[3]) if r[3] else None,
                    'puntaje_ingles': float(r[4]) if r[4] else None,
                    'percentil_nacional': float(r[5]) if r[5] else None,
                    'clasificacion_vs_nacional': r[6],
                    'total_estudiantes': int(r[7]) if r[7] else 0,
                }
                for r in rows_list
            ],
            'por_departamento': [
                {'departamento': r[0], 'resilientes': int(r[1])}
                for r in rows_depto
            ],
        }
    except Exception as e:
        logger.error(f"Error in get_inteligencia_resilientes: {e}")
        return {}


def get_inteligencia_movilidad(limit=25):
    """
    Escuelas con mayor escalada y mayor caída en el ranking nacional.
    cambio_ranking_nacional negativo = subió posiciones (mejoró).
    Fuente: fct_colegio_historico (año más reciente).
    """
    try:
        base = resolve_schema("""
            SELECT
                nombre_colegio, departamento, municipio, sector,
                ROUND(avg_punt_global, 1)   AS puntaje,
                ranking_nacional,
                cambio_ranking_nacional,
                total_estudiantes
            FROM gold.fct_colegio_historico
            WHERE ano = (SELECT MAX(ano) FROM gold.fct_colegio_historico)
              AND cambio_ranking_nacional IS NOT NULL
              AND total_estudiantes >= 10
            ORDER BY cambio_ranking_nacional {dir}
            LIMIT ?
        """)
        with get_duckdb_connection() as con:
            rows_esc = con.execute(base.replace('{dir}', 'ASC'),  [limit]).fetchall()
            rows_cai = con.execute(base.replace('{dir}', 'DESC'), [limit]).fetchall()

        def to_dict(r):
            return {
                'nombre_colegio': r[0], 'departamento': r[1], 'municipio': r[2],
                'sector': r[3],
                'puntaje': float(r[4]) if r[4] else None,
                'ranking_nacional': int(r[5]) if r[5] else None,
                'cambio_ranking': int(r[6]) if r[6] else None,
                'total_estudiantes': int(r[7]) if r[7] else 0,
            }

        return {
            'escaladores': [to_dict(r) for r in rows_esc],
            'caidas':      [to_dict(r) for r in rows_cai],
        }
    except Exception as e:
        logger.error(f"Error in get_inteligencia_movilidad: {e}")
        return {}


def get_inteligencia_promesa_ingles(limit=150):
    """
    Colegios OFICIALES cuyo puntaje de inglés supera el promedio NO OFICIAL.
    Colegios públicos que están rompiendo la barrera del inglés.
    Fuente: fct_colegio_comparacion_contexto (año más reciente).
    """
    try:
        q_thr = resolve_schema("""
            SELECT ROUND(AVG(colegio_ingles), 4)
            FROM gold.fct_colegio_comparacion_contexto
            WHERE sector = 'NO OFICIAL' AND total_estudiantes >= 10
              AND CAST(ano AS INTEGER) = (
                SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_colegio_comparacion_contexto
              )
        """)
        with get_duckdb_connection() as con:
            threshold = float(con.execute(q_thr).fetchone()[0] or 0)

            q_list = resolve_schema(f"""
                SELECT nombre_colegio, departamento, municipio,
                    ROUND(colegio_ingles, 1) AS ingles,
                    ROUND(colegio_global, 1) AS global,
                    percentil_nacional, total_estudiantes
                FROM gold.fct_colegio_comparacion_contexto
                WHERE sector = 'OFICIAL'
                  AND colegio_ingles >= {threshold}
                  AND total_estudiantes >= 10
                  AND CAST(ano AS INTEGER) = (
                    SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_colegio_comparacion_contexto
                  )
                ORDER BY colegio_ingles DESC
                LIMIT ?
            """)
            q_depto = resolve_schema(f"""
                SELECT departamento, COUNT(*) AS n
                FROM gold.fct_colegio_comparacion_contexto
                WHERE sector = 'OFICIAL' AND colegio_ingles >= {threshold}
                  AND total_estudiantes >= 10
                  AND CAST(ano AS INTEGER) = (
                    SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_colegio_comparacion_contexto
                  )
                GROUP BY departamento ORDER BY n DESC LIMIT 15
            """)
            q_total = resolve_schema(f"""
                SELECT COUNT(*) FROM gold.fct_colegio_comparacion_contexto
                WHERE sector = 'OFICIAL' AND colegio_ingles >= {threshold}
                  AND total_estudiantes >= 10
                  AND CAST(ano AS INTEGER) = (
                    SELECT MAX(CAST(ano AS INTEGER)) FROM gold.fct_colegio_comparacion_contexto
                  )
            """)
            rows_list  = con.execute(q_list, [limit]).fetchall()
            rows_depto = con.execute(q_depto).fetchall()
            total      = con.execute(q_total).fetchone()[0]

        return {
            'threshold_privado': round(threshold, 2),
            'total': int(total),
            'lista': [
                {
                    'nombre_colegio': r[0], 'departamento': r[1], 'municipio': r[2],
                    'ingles': float(r[3]) if r[3] else None,
                    'global': float(r[4]) if r[4] else None,
                    'percentil_nacional': float(r[5]) if r[5] else None,
                    'total_estudiantes': int(r[6]) if r[6] else 0,
                }
                for r in rows_list
            ],
            'por_departamento': [
                {'departamento': r[0], 'colegios': int(r[1])}
                for r in rows_depto
            ],
        }
    except Exception as e:
        logger.error(f"Error in get_inteligencia_promesa_ingles: {e}")
        return {}


def get_historia_riesgo_colegios(nivel_riesgo, limit=200):
    """
    Lista de colegios filtrada por nivel de riesgo (Alto / Medio / Bajo).
    Fuente: fct_riesgo_colegios (año más reciente).
    """
    try:
        query = resolve_schema("""
            SELECT
                nombre_colegio,
                departamento,
                sector,
                ROUND(avg_punt_global_actual, 1) AS puntaje_global,
                ROUND(prob_declive * 100, 1)     AS prob_declive_pct,
                factores_principales
            FROM gold.fct_riesgo_colegios
            WHERE ano = (SELECT MAX(ano) FROM gold.fct_riesgo_colegios)
              AND nivel_riesgo = ?
            ORDER BY prob_declive DESC
            LIMIT ?
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(query, [nivel_riesgo, limit]).fetchall()
        return [
            {
                'nombre_colegio': r[0],
                'departamento': r[1],
                'sector': r[2],
                'puntaje_global': float(r[3]) if r[3] else None,
                'prob_declive_pct': float(r[4]) if r[4] else None,
                'factores_principales': r[5],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error in get_historia_riesgo_colegios: {e}")
        return []


def get_historia_ingles():
    """
    Datos de Inglés para el capítulo 6 del storytelling:
    - Brecha privado/público en Inglés vs otras materias (año más reciente)
    - Evolución Inglés por sector 2018-2024
    - Inglés por región (año más reciente)
    Fuentes: fact_icfes_resumen_global, tendencias_regionales.
    """
    try:
        # 1. Brecha privado/público por materia
        q_brecha = resolve_schema("""
            SELECT
                ROUND(AVG(CASE WHEN cole_naturaleza = 'NO OFICIAL' THEN avg_ingles END)
                    - AVG(CASE WHEN cole_naturaleza = 'OFICIAL' THEN avg_ingles END), 2) AS brecha_ingles,
                ROUND(AVG(CASE WHEN cole_naturaleza = 'NO OFICIAL' THEN avg_matematicas END)
                    - AVG(CASE WHEN cole_naturaleza = 'OFICIAL' THEN avg_matematicas END), 2) AS brecha_matematicas,
                ROUND(AVG(CASE WHEN cole_naturaleza = 'NO OFICIAL' THEN avg_lectura END)
                    - AVG(CASE WHEN cole_naturaleza = 'OFICIAL' THEN avg_lectura END), 2) AS brecha_lectura,
                ROUND(AVG(CASE WHEN cole_naturaleza = 'NO OFICIAL' THEN avg_ciencias END)
                    - AVG(CASE WHEN cole_naturaleza = 'OFICIAL' THEN avg_ciencias END), 2) AS brecha_ciencias,
                ROUND(AVG(CASE WHEN cole_naturaleza = 'NO OFICIAL' THEN avg_sociales END)
                    - AVG(CASE WHEN cole_naturaleza = 'OFICIAL' THEN avg_sociales END), 2) AS brecha_sociales
            FROM gold.fact_icfes_resumen_global
            WHERE ano = (SELECT MAX(ano) FROM gold.fact_icfes_resumen_global)
              AND cole_naturaleza IN ('OFICIAL', 'NO OFICIAL')
              AND estudiantes > 0
        """)

        # 2. Evolución Inglés por sector 2018-2024
        q_tendencia = resolve_schema("""
            SELECT
                ano,
                cole_naturaleza AS sector,
                ROUND(AVG(avg_ingles), 2)      AS ingles,
                ROUND(AVG(avg_matematicas), 2) AS matematicas,
                ROUND(AVG(avg_lectura), 2)     AS lectura
            FROM gold.fact_icfes_resumen_global
            WHERE CAST(ano AS INTEGER) >= 2018
              AND cole_naturaleza IN ('OFICIAL', 'NO OFICIAL')
              AND estudiantes > 0
            GROUP BY ano, cole_naturaleza
            ORDER BY ano, cole_naturaleza
        """)

        # 3. Inglés por región (año más reciente desde tendencias_regionales)
        q_regiones = resolve_schema("""
            SELECT
                region,
                ROUND(avg_punt_ingles, 2)  AS ingles,
                ROUND(avg_punt_global, 2)  AS global
            FROM gold.tendencias_regionales
            WHERE ano = (SELECT MAX(ano) FROM gold.tendencias_regionales)
            ORDER BY ingles DESC
        """)

        with get_duckdb_connection() as con:
            row_brecha  = con.execute(q_brecha).fetchone()
            rows_tend   = con.execute(q_tendencia).fetchall()
            rows_regiones = con.execute(q_regiones).fetchall()

        brechas = {
            'Inglés':          float(row_brecha[0]) if row_brecha[0] else None,
            'Matemáticas':     float(row_brecha[1]) if row_brecha[1] else None,
            'Lectura Crítica': float(row_brecha[2]) if row_brecha[2] else None,
            'Ciencias':        float(row_brecha[3]) if row_brecha[3] else None,
            'Sociales':        float(row_brecha[4]) if row_brecha[4] else None,
        }

        tendencia = {}
        for r in rows_tend:
            s = r[1]
            if s not in tendencia:
                tendencia[s] = []
            tendencia[s].append({
                'ano': r[0],
                'ingles': float(r[2]) if r[2] else None,
                'matematicas': float(r[3]) if r[3] else None,
                'lectura': float(r[4]) if r[4] else None,
            })

        regiones = [
            {
                'region': r[0],
                'ingles': float(r[1]) if r[1] else None,
                'global': float(r[2]) if r[2] else None,
            }
            for r in rows_regiones
        ]

        return {
            'brechas_por_materia': brechas,
            'tendencia_sector':    tendencia,
            'regiones':            regiones,
        }

    except Exception as e:
        logger.error(f"Error in get_historia_ingles: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Inteligencia Educativa — Cap 5: Potencial Educativo Contextual (ML model)
# ──────────────────────────────────────────────────────────────────────────────

def get_inteligencia_potencial(limit=200):
    """
    Colegios que superan su potencial contextual predicho por GBM.
    Retorna: stats del modelo + colegios Excepcionales y Notables OFICIALES.
    """
    try:
        q_stats = resolve_schema("""
            SELECT
                COUNT(*)  FILTER (WHERE clasificacion = 'Excepcional' AND sector = 'OFICIAL') AS n_excepcionales,
                COUNT(*)  FILTER (WHERE clasificacion = 'Notable'     AND sector = 'OFICIAL') AS n_notables,
                COUNT(*)  FILTER (WHERE clasificacion = 'En Riesgo Contextual')               AS n_riesgo,
                ROUND(MAX(exceso), 1)                                                         AS max_exceso,
                ROUND(AVG(exceso) FILTER (WHERE sector = 'OFICIAL'), 1)                       AS avg_exceso_oficial,
                FIRST(model_r2)                                                               AS model_r2,
                FIRST(model_mae)                                                              AS model_mae,
                COUNT(*)                                                                      AS total_colegios
            FROM gold.fct_potencial_educativo
        """)

        q_top = resolve_schema(f"""
            SELECT
                colegio_bk,
                nombre_colegio,
                sector,
                region,
                departamento,
                ROUND(avg_global, 1)       AS score_real,
                ROUND(score_esperado, 1)   AS score_esperado,
                ROUND(exceso, 1)           AS exceso,
                ROUND(percentil_exceso, 1) AS percentil_exceso,
                ranking_exceso_nacional,
                clasificacion
            FROM gold.fct_potencial_educativo
            WHERE clasificacion IN ('Excepcional', 'Notable')
              AND sector = 'OFICIAL'
            ORDER BY exceso DESC
            LIMIT {limit}
        """)

        q_depto = resolve_schema("""
            SELECT
                departamento,
                COUNT(*) FILTER (WHERE clasificacion = 'Excepcional' AND sector = 'OFICIAL') AS n_excepcionales,
                COUNT(*) FILTER (WHERE clasificacion = 'Notable'     AND sector = 'OFICIAL') AS n_notables,
                ROUND(AVG(exceso) FILTER (WHERE sector = 'OFICIAL'), 1)                     AS avg_exceso
            FROM gold.fct_potencial_educativo
            GROUP BY departamento
            HAVING COUNT(*) FILTER (WHERE clasificacion IN ('Excepcional', 'Notable') AND sector = 'OFICIAL') > 0
            ORDER BY n_excepcionales DESC, n_notables DESC
            LIMIT 20
        """)

        with get_duckdb_connection() as con:
            s = con.execute(q_stats).fetchone()
            rows_top   = con.execute(q_top).fetchall()
            rows_depto = con.execute(q_depto).fetchall()

        cols_top = [
            'colegio_bk', 'nombre_colegio', 'sector', 'region', 'departamento',
            'score_real', 'score_esperado', 'exceso', 'percentil_exceso',
            'ranking_exceso_nacional', 'clasificacion',
        ]
        cols_depto = ['departamento', 'n_excepcionales', 'n_notables', 'avg_exceso']

        return {
            'stats': {
                'n_excepcionales':   int(s[0]) if s[0] else 0,
                'n_notables':        int(s[1]) if s[1] else 0,
                'n_riesgo':          int(s[2]) if s[2] else 0,
                'max_exceso':        float(s[3]) if s[3] else None,
                'avg_exceso_oficial': float(s[4]) if s[4] else None,
                'model_r2':          float(s[5]) if s[5] else None,
                'model_mae':         float(s[6]) if s[6] else None,
                'total_colegios':    int(s[7]) if s[7] else 0,
            },
            'colegios': [dict(zip(cols_top, r)) for r in rows_top],
            'por_departamento': [dict(zip(cols_depto, r)) for r in rows_depto],
        }

    except Exception as e:
        logger.error(f"Error in get_inteligencia_potencial: {e}")
        return {'stats': {}, 'colegios': [], 'por_departamento': []}


def get_inteligencia_potencial_scatter(sample=2000):
    """
    Muestra de colegios para scatter: score_real vs score_esperado,
    coloreado por clasificacion. Limitado a `sample` filas.
    """
    try:
        q = resolve_schema(f"""
            SELECT
                ROUND(avg_global, 1)     AS score_real,
                ROUND(score_esperado, 1) AS score_esperado,
                ROUND(exceso, 1)         AS exceso,
                clasificacion,
                sector,
                departamento
            FROM gold.fct_potencial_educativo
            USING SAMPLE {sample}
        """)

        with get_duckdb_connection() as con:
            rows = con.execute(q).fetchall()

        cols = ['score_real', 'score_esperado', 'exceso', 'clasificacion', 'sector', 'departamento']
        return [dict(zip(cols, r)) for r in rows]

    except Exception as e:
        logger.error(f"Error in get_inteligencia_potencial_scatter: {e}")
        return []
