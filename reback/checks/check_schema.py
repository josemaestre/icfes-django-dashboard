"""
Script simple para verificar la estructura de las tablas.
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb"

print("Conectando a la base de datos...")
conn = duckdb.connect(DB_PATH, read_only=True)

# Listar todos los esquemas
print("\n=== ESQUEMAS ===")
schemas = conn.execute("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name").fetchall()
for schema in schemas:
    print(f"  - {schema[0]}")

# Verificar tabla de slugs
print("\n=== TABLA gold.dim_colegios_slugs ===")
try:
    cols = conn.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'gold' AND table_name = 'dim_colegios_slugs'
        ORDER BY ordinal_position
    """).fetchall()
    
    if cols:
        print("Columnas:")
        for col, dtype in cols:
            print(f"  - {col}: {dtype}")
        
        count = conn.execute("SELECT COUNT(*) FROM gold.dim_colegios_slugs").fetchone()[0]
        print(f"\nRegistros: {count:,}")
    else:
        print("❌ Tabla no encontrada")
except Exception as e:
    print(f"❌ Error: {e}")

# Buscar tablas de colegios
print("\n=== TABLAS RELACIONADAS CON COLEGIOS ===")
tables = conn.execute("""
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_name LIKE '%colegio%'
    ORDER BY table_schema, table_name
""").fetchall()

for schema, table in tables:
    print(f"  - {schema}.{table}")

# Verificar una tabla específica para ver el nombre de la columna de código
print("\n=== COLUMNAS DE fct_colegio_historico ===")
try:
    cols = conn.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'fct_colegio_historico'
        ORDER BY ordinal_position
        LIMIT 10
    """).fetchall()
    
    for col in cols:
        print(f"  - {col[0]}")
except Exception as e:
    print(f"❌ Error: {e}")

conn.close()
print("\n✅ Verificación completada")
