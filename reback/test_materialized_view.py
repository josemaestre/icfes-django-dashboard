"""
Script para verificar que las queries actualizadas funcionan correctamente
con la nueva vista materializada vw_fct_colegios_region
"""

import duckdb
from pathlib import Path

# Ruta a la base de datos
DB_PATH = Path(__file__).parent.parent.parent / 'dbt' / 'icfes_processing' / 'dev.duckdb'

print("="*80)
print("VERIFICACION DE QUERIES ACTUALIZADAS CON vw_fct_colegios_region")
print("="*80)

con = duckdb.connect(str(DB_PATH), read_only=True)

# Test 1: api_distribucion_regional
print("\n[TEST 1] api_distribucion_regional - Distribucion por region")
print("-"*80)
query1 = """
    SELECT 
        region,
        SUM(total_estudiantes) as total_estudiantes,
        AVG(avg_punt_global) as promedio
    FROM gold.vw_fct_colegios_region
    WHERE ano = 2024 AND region IS NOT NULL
    GROUP BY region
    ORDER BY total_estudiantes DESC
"""
result1 = con.execute(query1).fetchdf()
print(result1.to_string(index=False))
print(f"\n[OK] Retorno {len(result1)} regiones")

# Test 2: hierarchy_regions - Regiones con estadisticas
print("\n[TEST 2] hierarchy_regions - Regiones con Z-scores")
print("-"*80)
query2 = """
    WITH current_year AS (
        SELECT 
            region,
            AVG(avg_punt_global) as punt_global,
            AVG(avg_punt_matematicas) as punt_matematicas,
            SUM(total_estudiantes) as total_estudiantes
        FROM gold.vw_fct_colegios_region
        WHERE ano = 2024 AND region IS NOT NULL
        GROUP BY region
    ),
    previous_year AS (
        SELECT 
            region,
            AVG(avg_punt_global) as punt_global_anterior
        FROM gold.vw_fct_colegios_region
        WHERE ano = 2023 AND region IS NOT NULL
        GROUP BY region
    ),
    national_stats AS (
        SELECT 
            AVG(punt_global) as media_nacional,
            STDDEV(punt_global) as std_nacional
        FROM current_year
    )
    SELECT 
        c.region,
        c.punt_global,
        c.punt_matematicas,
        c.total_estudiantes,
        ROW_NUMBER() OVER (ORDER BY c.punt_global DESC) as ranking,
        COALESCE(((c.punt_global - p.punt_global_anterior) / NULLIF(p.punt_global_anterior, 0) * 100), 0) as cambio_anual,
        COALESCE(((c.punt_global - n.media_nacional) / NULLIF(n.std_nacional, 0)), 0) as z_score
    FROM current_year c
    LEFT JOIN previous_year p ON c.region = p.region
    CROSS JOIN national_stats n
    ORDER BY c.punt_global DESC
"""
result2 = con.execute(query2).fetchdf()
print(result2.to_string(index=False))
print(f"\n[OK] Retorno {len(result2)} regiones con estadisticas")

# Test 3: hierarchy_departments - Departamentos de una region
print("\n[TEST 3] hierarchy_departments - Departamentos de Region ANDINA")
print("-"*80)
query3 = """
    WITH current_year AS (
        SELECT 
            departamento,
            AVG(avg_punt_global) as punt_global,
            SUM(total_estudiantes) as total_estudiantes
        FROM gold.vw_fct_colegios_region
        WHERE ano = 2024 AND region = 'Región Centro Oriente'
        GROUP BY departamento
    )
    SELECT 
        departamento,
        punt_global,
        total_estudiantes,
        ROW_NUMBER() OVER (ORDER BY punt_global DESC) as ranking
    FROM current_year
    ORDER BY punt_global DESC
    LIMIT 10
"""
result3 = con.execute(query3).fetchdf()
print(result3.to_string(index=False))
print(f"\n[OK] Retorno {len(result3)} departamentos")

# Test 4: Comparacion de rendimiento (opcional)
print("\n[TEST 4] Comparacion de rendimiento: JOIN vs Vista Materializada")
print("-"*80)

import time

# Con JOIN (metodo anterior)
start = time.time()
query_join = """
    SELECT 
        dc.region,
        AVG(f.avg_punt_global) as promedio
    FROM gold.fct_agg_colegios_ano f
    INNER JOIN gold.dim_colegios_ano dc ON f.colegio_sk = dc.colegio_sk AND f.ano = dc.ano
    WHERE f.ano = 2024
    GROUP BY dc.region
"""
con.execute(query_join).fetchdf()
time_join = time.time() - start

# Con vista materializada (metodo nuevo)
start = time.time()
query_view = """
    SELECT 
        region,
        AVG(avg_punt_global) as promedio
    FROM gold.vw_fct_colegios_region
    WHERE ano = 2024 AND region IS NOT NULL
    GROUP BY region
"""
con.execute(query_view).fetchdf()
time_view = time.time() - start

print(f"Tiempo con JOIN:              {time_join*1000:.2f} ms")
print(f"Tiempo con Vista Materializada: {time_view*1000:.2f} ms")
print(f"Mejora de rendimiento:         {((time_join - time_view) / time_join * 100):.1f}%")

con.close()

print("\n" + "="*80)
print("[OK] TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
print("="*80)
