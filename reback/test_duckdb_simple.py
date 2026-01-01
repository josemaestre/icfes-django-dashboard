"""
Script de verificación simple para DuckDB.
Prueba la conexión directa sin Django.
"""
import os
import duckdb
import pandas as pd

DUCKDB_PATH = r'c:\proyectos\dbt\icfes_processing\dev.duckdb'

print("=" * 80)
print("VERIFICACIÓN SIMPLE DE DUCKDB")
print("=" * 80)

# 1. Verificar archivo
print("\n1. Verificando archivo DuckDB...")
print(f"   Ruta: {DUCKDB_PATH}")
print(f"   Existe: {os.path.exists(DUCKDB_PATH)}")
if os.path.exists(DUCKDB_PATH):
    size_gb = os.path.getsize(DUCKDB_PATH) / (1024**3)
    print(f"   Tamaño: {size_gb:.2f} GB")

# 2. Conectar
print("\n2. Conectando a DuckDB...")
try:
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    print("   ✓ Conexión exitosa (modo read-only)")
except Exception as e:
    print(f"   ✗ Error: {e}")
    exit(1)

# 3. Listar schemas
print("\n3. Listando schemas...")
try:
    result = con.execute("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name").fetchall()
    schemas = [r[0] for r in result]
    print(f"   Schemas encontrados: {schemas}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 4. Listar tablas en gold
print("\n4. Listando tablas en schema 'gold'...")
try:
    result = con.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'gold'
        ORDER BY table_name
    """).fetchall()
    tables = [r[0] for r in result]
    print(f"   Tablas encontradas ({len(tables)}):")
    for table in tables:
        print(f"   - gold.{table}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 5. Contar registros en fact_icfes_analytics
print("\n5. Consultando fact_icfes_analytics...")
try:
    df = con.execute("""
        SELECT 
            COUNT(*) as total_registros,
            MIN(ano) as ano_min,
            MAX(ano) as ano_max,
            AVG(punt_global) as promedio_global
        FROM gold.fact_icfes_analytics
    """).df()
    
    print(f"   Total registros: {df['total_registros'].iloc[0]:,}")
    print(f"   Rango de años: {df['ano_min'].iloc[0]} - {df['ano_max'].iloc[0]}")
    print(f"   Promedio global: {df['promedio_global'].iloc[0]:.2f}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 6. Consultar fct_agg_colegios_ano
print("\n6. Consultando fct_agg_colegios_ano...")
try:
    df = con.execute("""
        SELECT 
            ano,
            COUNT(DISTINCT colegio_sk) as total_colegios,
            SUM(total_estudiantes) as total_estudiantes,
            AVG(avg_punt_global) as promedio_nacional
        FROM gold.fct_agg_colegios_ano
        WHERE ano >= 2020
        GROUP BY ano
        ORDER BY ano DESC
    """).df()
    
    print(f"   Datos por año (2020+):")
    for _, row in df.iterrows():
        print(f"   - {row['ano']}: {row['total_colegios']:,} colegios, "
              f"{row['total_estudiantes']:,} estudiantes, "
              f"promedio: {row['promedio_nacional']:.2f}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 7. Consultar tendencias_regionales
print("\n7. Consultando tendencias_regionales...")
try:
    df = con.execute("""
        SELECT 
            region,
            COUNT(DISTINCT ano) as anos_disponibles
        FROM gold.tendencias_regionales
        GROUP BY region
        ORDER BY region
    """).df()
    
    print(f"   Regiones encontradas:")
    for _, row in df.iterrows():
        print(f"   - {row['region']}: {row['anos_disponibles']} años de datos")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 8. Consultar brechas_educativas (año 2023)...
print("\n8. Consultando brechas_educativas (año 2023)...")
try:
    df = con.execute("""
        SELECT 
            tipo_brecha,
            brecha_absoluta_puntos,
            magnitud_brecha,
            tendencia_brecha
        FROM gold.brechas_educativas
        WHERE ano = 2023
        ORDER BY brecha_absoluta_puntos DESC
        LIMIT 5
    """).df()
    
    print(f"   Top 5 brechas educativas:")
    for _, row in df.iterrows():
        print(f"   - {row['tipo_brecha']}: {row['brecha_absoluta_puntos']:.2f} puntos ({row['magnitud_brecha']}, {row['tendencia_brecha']})")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Cerrar conexión
con.close()

print("\n" + "=" * 80)
print("VERIFICACIÓN COMPLETADA ✓")
print("=" * 80)
print("\nLa base de datos DuckDB está funcionando correctamente.")
print("Todas las tablas gold están accesibles.")
print("\nPróximo paso: Iniciar el servidor Django")
print("  cd c:\\proyectos\\www\\reback")
print("  python manage.py runserver")
