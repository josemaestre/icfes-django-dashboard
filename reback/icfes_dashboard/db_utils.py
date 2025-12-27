"""
Utilidades para trabajar con DuckDB en el dashboard ICFES.
"""
import duckdb
import pandas as pd
import numpy as np
from django.conf import settings
from contextlib import contextmanager


@contextmanager
def get_duckdb_connection(read_only=True):
    """
    Context manager para obtener una conexión a DuckDB.
    
    Args:
        read_only: Si True, abre la BD en modo solo lectura (default: True)
    
    Yields:
        duckdb.DuckDBPyConnection: Conexión a DuckDB
    
    Example:
        with get_duckdb_connection() as con:
            df = con.execute("SELECT * FROM gold.fact_icfes_analytics LIMIT 10").df()
    """
    con = None
    try:
        con = duckdb.connect(settings.ICFES_DUCKDB_PATH, read_only=read_only)
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
    query = f"SELECT * FROM {table_name}"
    
    if filters:
        where_clauses = []
        for key, value in filters.items():
            if isinstance(value, str):
                where_clauses.append(f"{key} = '{value}'")
            else:
                where_clauses.append(f"{key} = {value}")
        query += " WHERE " + " AND ".join(where_clauses)
    
    if order_by:
        if isinstance(order_by, list):
            query += f" ORDER BY {', '.join(order_by)}"
        else:
            query += f" ORDER BY {order_by}"
    
    if limit:
        query += f" LIMIT {limit}"
    
    return execute_query(query)


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
    query = f"""
        SELECT DISTINCT municipio 
        FROM gold.dim_colegios 
        WHERE departamento = '{departamento}'
        ORDER BY municipio
    """
    df = execute_query(query)
    return df['municipio'].tolist()


def get_estadisticas_generales(ano=None):
    """
    Obtiene estadísticas generales del sistema.
    
    Args:
        ano: Año específico (opcional, si None usa todos los años)
    
    Returns:
        dict: Diccionario con estadísticas
    """
    filters = {'ano': ano} if ano else None
    
    query = f"""
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
        {f"WHERE ano = {ano}" if ano else ""}
    """
    
    df = execute_query(query)
    return df.iloc[0].to_dict() if not df.empty else {}
