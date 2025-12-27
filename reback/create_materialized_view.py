"""
Script para crear la vista materializada vw_fct_colegios_region directamente en DuckDB.
Esto es una alternativa si dbt no puede ejecutar el modelo.
"""

import duckdb
from pathlib import Path

# Ruta a la base de datos
DB_PATH = Path(__file__).parent.parent.parent / 'dbt' / 'icfes_processing' / 'dev.duckdb'

print(f"Conectando a: {DB_PATH}")

# Conectar a DuckDB
con = duckdb.connect(str(DB_PATH), read_only=False)

# Crear la vista materializada
print("Creando vista materializada vw_fct_colegios_region...")

create_view_sql = """
CREATE OR REPLACE TABLE gold.vw_fct_colegios_region AS
SELECT 
    f.ano,
    f.colegio_sk,
    f.colegio_bk,
    f.nombre_colegio,
    
    -- Información geográfica de la dimensión
    d.region,
    f.departamento,
    f.municipio,
    f.sector,
    
    -- Métricas de estudiantes
    f.total_estudiantes,
    
    -- Conteos de colegios
    f.count_colegios_nacional,
    f.count_colegios_departamento,
    f.count_colegios_municipio,
    f.count_colegios_sector_depto,
    f.count_colegios_sector_municipio,
    
    -- Puntajes promedio
    f.avg_punt_global,
    f.median_punt_global,
    f.avg_global_zscore,
    f.avg_punt_c_naturales,
    f.avg_punt_lectura_critica,
    f.avg_punt_matematicas,
    f.avg_punt_sociales_ciudadanas,
    f.avg_punt_ingles,
    
    -- Métricas de valor agregado
    f.gap_municipio_promedio,
    f.rendimiento_relativo_municipal,
    
    -- Percentiles promedio
    f.avg_percentile_sector_estudiante,
    f.avg_percentile_c_naturales_sector,
    f.avg_percentile_lectura_critica_sector,
    f.avg_percentile_matematicas_sector,
    f.avg_percentile_sociales_ciudadanas_sector,
    f.avg_percentile_ingles_sector,
    
    -- Rankings
    f.ranking_nacional,
    f.ranking_departamental_general,
    f.ranking_sector_departamental,
    f.ranking_sector_municipal,
    
    -- Metadata
    f.fecha_carga
    
FROM gold.fct_agg_colegios_ano f
JOIN gold.dim_colegios_ano d 
    ON f.colegio_sk = d.colegio_sk 
    AND f.ano = d.ano
"""

try:
    con.execute(create_view_sql)
    print("[OK] Vista materializada creada exitosamente!")
    
    # Verificar la vista
    result = con.execute("SELECT COUNT(*) as total FROM gold.vw_fct_colegios_region").fetchone()
    print(f"[OK] Total de registros en la vista: {result[0]:,}")
    
    # Verificar que tiene región
    result = con.execute("""
        SELECT region, COUNT(*) as total 
        FROM gold.vw_fct_colegios_region 
        GROUP BY region 
        ORDER BY region
    """).fetchdf()
    print("\n[INFO] Distribucion por region:")
    print(result.to_string(index=False))
    
except Exception as e:
    print(f"[ERROR] Error al crear la vista: {e}")
finally:
    con.close()

print("\n[OK] Proceso completado!")

