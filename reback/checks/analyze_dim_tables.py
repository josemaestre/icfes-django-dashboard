"""
Revisar estructura de dim_colegios y fct_colegio_historico
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\dev.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

print("=" * 80)
print("TABLAS DIM_COLEGIO EN GOLD SCHEMA")
print("=" * 80)

# Listar todas las tablas dim_colegio*
dim_tables = conn.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'gold'
    AND table_name LIKE 'dim_colegio%'
    ORDER BY table_name
""").fetchall()

print(f"\nEncontradas {len(dim_tables)} tablas dim_colegio*:\n")
for (table,) in dim_tables:
    print(f"  - {table}")
    
    # Mostrar columnas clave de cada tabla
    cols = conn.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'gold'
        AND table_name = '{table}'
        AND (column_name LIKE '%sk%' OR column_name LIKE '%codigo%' OR column_name LIKE '%dane%')
        ORDER BY ordinal_position
    """).fetchall()
    
    if cols:
        for col, dtype in cols:
            print(f"      {col:30} {dtype}")
    
    # Contar registros
    count = conn.execute(f"SELECT COUNT(*) FROM gold.{table}").fetchone()[0]
    print(f"      Total registros: {count:,}\n")

print("\n" + "=" * 80)
print("TABLA FCT_COLEGIO_HISTORICO")
print("=" * 80)

# Mostrar columnas clave de fct_colegio_historico
print("\nColumnas de identificación:")
hist_cols = conn.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'gold'
    AND table_name = 'fct_colegio_historico'
    AND (column_name LIKE '%sk%' OR column_name LIKE '%codigo%' OR column_name LIKE '%dane%' OR column_name LIKE '%nombre%')
    ORDER BY ordinal_position
""").fetchall()

for col, dtype in hist_cols:
    print(f"  {col:30} {dtype}")

# Buscar el colegio ABC por diferentes criterios
print("\n" + "=" * 80)
print("BUSCANDO A.B.C. CENTRO EDUCATIVO")
print("=" * 80)

# Buscar en dim_colegios_slugs
print("\n1. En dim_colegios_slugs:")
slug_result = conn.execute("""
    SELECT codigo, nombre_colegio, slug
    FROM gold.dim_colegios_slugs
    WHERE slug = 'abc-centro-educativo-medellin'
""").fetchone()

if slug_result:
    print(f"   codigo: {slug_result[0]}")
    print(f"   nombre: {slug_result[1]}")
    print(f"   slug: {slug_result[2]}")
    
    codigo_from_slug = slug_result[0]
    
    # Buscar en fct_colegio_historico por codigo_dane
    print(f"\n2. En fct_colegio_historico (buscando codigo_dane={codigo_from_slug}):")
    hist_by_dane = conn.execute(f"""
        SELECT COUNT(*), MIN(ano), MAX(ano)
        FROM gold.fct_colegio_historico
        WHERE codigo_dane = '{codigo_from_slug}'
    """).fetchone()
    print(f"   Registros: {hist_by_dane[0]}")
    if hist_by_dane[0] > 0:
        print(f"   Años: {hist_by_dane[1]} - {hist_by_dane[2]}")
    
    # Buscar por nombre
    print(f"\n3. En fct_colegio_historico (buscando por nombre):")
    hist_by_name = conn.execute("""
        SELECT colegio_sk, codigo_dane, nombre_colegio, COUNT(*) as registros
        FROM gold.fct_colegio_historico
        WHERE nombre_colegio LIKE '%A.B.C.%CENTRO%EDUCATIVO%'
        GROUP BY colegio_sk, codigo_dane, nombre_colegio
        LIMIT 5
    """).fetchall()
    
    if hist_by_name:
        for sk, dane, nombre, count in hist_by_name:
            print(f"   colegio_sk: {sk}, codigo_dane: {dane}")
            print(f"   nombre: {nombre}")
            print(f"   registros: {count}\n")
    else:
        print("   ❌ No encontrado por nombre")

conn.close()
