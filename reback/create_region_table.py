# Script para crear tabla dim_departamentos_region en DuckDB

import duckdb

# Conectar a la base de datos
conn = duckdb.connect('c:/proyectos/dbt/icfes_processing/dev.duckdb')

# Crear tabla de mapeo departamento -> region
query = """
CREATE OR REPLACE TABLE gold.dim_departamentos_region AS
SELECT DISTINCT
    departamento,
    region
FROM gold.dim_colegios
WHERE region IS NOT NULL
ORDER BY region, departamento
"""

try:
    conn.execute(query)
    print("Tabla gold.dim_departamentos_region creada exitosamente")
    
    # Verificar contenido
    result = conn.execute("SELECT * FROM gold.dim_departamentos_region ORDER BY region, departamento").fetchall()
    print(f"\nTotal de departamentos mapeados: {len(result)}")
    print("\nPrimeros 10 registros:")
    for row in result[:10]:
        print(f"  {row[0]:30} -> {row[1]}")
    
    conn.close()
    print("\nProceso completado")
    
except Exception as e:
    print(f"Error: {e}")
    conn.close()
