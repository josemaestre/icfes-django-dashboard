import duckdb
import pandas as pd
# Asume que ya tienes una conexión 'con' a tu base de datos DuckDB
# Si no la tienes, debes conectarte primero:
# Muestra todas las filas (hasta 500, puedes ajustar el número)
pd.set_option('display.max_rows', 500) 

# Muestra todas las columnas (DuckDB solo te da 4 o 5, así que 50 es suficiente)
pd.set_option('display.max_columns', 50) 

# También puedes aumentar el ancho de la columna si los nombres siguen viéndose cortados
pd.set_option('display.width', 1000) 
pd.set_option('display.max_colwidth', None) # Muestra



con = duckdb.connect(database='icfes_base.duckdb', read_only=False)

# Ejecutar la consulta en la tabla de metadatos de DuckDB
esquema_completo = con.execute("""
    SELECT 
        column_name, 
        data_type,
        is_nullable
    FROM 
        duckdb_columns 
    WHERE 
        table_name = 'test_all'
    ORDER BY 
        column_name;
""").fetchdf()

# Mostrar el resultado (un DataFrame de Pandas)
print(esquema_completo)