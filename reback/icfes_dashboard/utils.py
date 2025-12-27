import duckdb
import pandas as pd

DB_PATH = 'icfes_base.duckdb'

def get_promedio_por_departamento():
    con = duckdb.connect(DB_PATH)
    query = """
        SELECT 
            ESTU_DEPTO_RESIDE AS depto,
            AVG(PUNT_GLOBAL) AS promedio_global,
            COUNT(*) AS total_estudiantes
        FROM v_icfes
        WHERE PUNT_GLOBAL IS NOT NULL
        GROUP BY ESTU_DEPTO_RESIDE
        ORDER BY promedio_global DESC;
    """
    df = con.sql(query).df()
    con.close()
    return df
