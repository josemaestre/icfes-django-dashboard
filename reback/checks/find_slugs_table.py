"""
Verificar qué esquema tiene la tabla dim_colegios_slugs
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

print("Buscando tabla dim_colegios_slugs en todos los esquemas...\n")

# Buscar en todos los esquemas
result = conn.execute("""
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_name = 'dim_colegios_slugs'
""").fetchall()

if result:
    print("✅ Tabla encontrada:")
    for schema, table in result:
        print(f"   {schema}.{table}")
        # Contar registros
        count = conn.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
        print(f"   Registros: {count:,}")
else:
    print("❌ Tabla NO encontrada en ningún esquema")

# Verificar si existe vista gold.dim_colegios_slugs
print("\n\nVerificando vistas en esquema gold...")
views = conn.execute("""
    SELECT table_name
    FROM information_schema.views
    WHERE table_schema = 'gold'
    AND table_name LIKE '%slug%'
""").fetchall()

if views:
    print("Vistas con 'slug' en gold:")
    for (view,) in views:
        print(f"   - {view}")
else:
    print("No hay vistas con 'slug' en gold")

conn.close()
