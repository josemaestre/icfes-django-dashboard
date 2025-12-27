"""
Script para investigar la jerarquía geográfica de Bogotá
"""

import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / 'dbt' / 'icfes_processing' / 'dev.duckdb'

print("="*80)
print("INVESTIGACION: Jerarquia Geografica de Bogota")
print("="*80)

con = duckdb.connect(str(DB_PATH), read_only=True)

# 1. Ver todas las combinaciones de Bogotá
print("\n[1] Combinaciones de Region-Departamento-Municipio con 'BOGOTA':")
print("-"*80)
query1 = """
    SELECT DISTINCT 
        region, 
        departamento, 
        municipio
    FROM gold.vw_fct_colegios_region
    WHERE departamento LIKE '%BOGOT%' OR municipio LIKE '%BOGOT%'
    ORDER BY region, departamento, municipio
"""
result1 = con.execute(query1).fetchdf()
print(result1.to_string(index=False))

# 2. Conteo de registros por combinación
print("\n[2] Conteo de registros por combinacion:")
print("-"*80)
query2 = """
    SELECT 
        region, 
        departamento, 
        municipio, 
        COUNT(*) as total_registros
    FROM gold.vw_fct_colegios_region
    WHERE departamento LIKE '%BOGOT%' OR municipio LIKE '%BOGOT%'
    GROUP BY region, departamento, municipio
    ORDER BY total_registros DESC
"""
result2 = con.execute(query2).fetchdf()
print(result2.to_string(index=False))

# 3. Ver la fuente original - dim_colegios_ano
print("\n[3] Verificar en dim_colegios_ano (fuente original):")
print("-"*80)
query3 = """
    SELECT DISTINCT 
        region, 
        departamento, 
        municipio
    FROM gold.dim_colegios_ano
    WHERE departamento LIKE '%BOGOT%' OR municipio LIKE '%BOGOT%'
    ORDER BY region, departamento, municipio
"""
result3 = con.execute(query3).fetchdf()
print(result3.to_string(index=False))

# 4. Ver en la tabla geografica de silver
print("\n[4] Verificar en tabla geografica (silver):")
print("-"*80)
query4 = """
    SELECT DISTINCT 
        region, 
        departamento, 
        municipio
    FROM silver.geografica
    WHERE departamento LIKE '%BOGOT%' OR municipio LIKE '%BOGOT%'
    ORDER BY region, departamento, municipio
"""
result4 = con.execute(query4).fetchdf()
print(result4.to_string(index=False))

# 5. Investigar la división política oficial de Colombia
print("\n[5] Informacion de DIVIPOLA (division politica oficial):")
print("-"*80)
query5 = """
    SELECT DISTINCT 
        codigo_departamento,
        departamento,
        codigo_municipio,
        municipio,
        tipo
    FROM bronze.raw_divipola
    WHERE departamento LIKE '%BOGOT%' OR municipio LIKE '%BOGOT%'
    ORDER BY codigo_departamento, codigo_municipio
"""
result5 = con.execute(query5).fetchdf()
print(result5.to_string(index=False))

con.close()

print("\n" + "="*80)
print("ANALISIS COMPLETADO")
print("="*80)
print("\nNOTA: Bogota D.C. es un Distrito Capital, no un departamento ni municipio")
print("tradicional. En la division politica de Colombia:")
print("- Codigo departamento: 11 (BOGOTA D.C.)")
print("- Codigo municipio: 11001 (BOGOTA D.C.)")
print("- Es simultaneamente departamento Y municipio")
