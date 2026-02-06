"""
Verificar todas las tablas en gold schema de dev.duckdb
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\dev.duckdb"

print("Verificando tablas en dev.duckdb...\n")
print("=" * 80)

conn = duckdb.connect(DB_PATH, read_only=True)

# Listar todos los esquemas
print("\n📁 ESQUEMAS DISPONIBLES:")
schemas = conn.execute("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name").fetchall()
for (schema,) in schemas:
    print(f"  - {schema}")

# Listar tablas en gold
print("\n📊 TABLAS EN ESQUEMA GOLD:")
gold_tables = conn.execute("""
    SELECT table_name, table_type
    FROM information_schema.tables
    WHERE table_schema = 'gold'
    ORDER BY table_name
""").fetchall()

if gold_tables:
    for table, ttype in gold_tables:
        # Contar registros
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM gold.{table}").fetchone()[0]
            print(f"  ✅ {table} ({ttype}) - {count:,} registros")
        except Exception as e:
            print(f"  ⚠️  {table} ({ttype}) - Error: {e}")
else:
    print("  ❌ No hay tablas en gold")

# Listar tablas en main
print("\n📊 TABLAS EN ESQUEMA MAIN:")
main_tables = conn.execute("""
    SELECT table_name, table_type
    FROM information_schema.tables
    WHERE table_schema = 'main'
    ORDER BY table_name
""").fetchall()

if main_tables:
    for table, ttype in main_tables[:10]:  # Solo primeras 10
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0]
            print(f"  ✅ {table} ({ttype}) - {count:,} registros")
        except Exception as e:
            print(f"  ⚠️  {table} ({ttype}) - Error: {e}")
    
    if len(main_tables) > 10:
        print(f"  ... y {len(main_tables) - 10} tablas más")
else:
    print("  ❌ No hay tablas en main")

# Buscar específicamente las tablas que necesita la landing page
print("\n🔍 TABLAS NECESARIAS PARA LANDING PAGE:")
needed_tables = [
    'fct_colegio_historico',
    'fct_colegio_comparacion_contexto',
    'dim_colegios_cluster',
    'dim_colegios_slugs'
]

for table in needed_tables:
    # Buscar en todos los esquemas
    result = conn.execute(f"""
        SELECT table_schema, COUNT(*) as count
        FROM information_schema.tables
        WHERE table_name = '{table}'
        GROUP BY table_schema
    """).fetchall()
    
    if result:
        for schema, _ in result:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
                print(f"  ✅ {schema}.{table} - {count:,} registros")
            except:
                print(f"  ⚠️  {schema}.{table} - Error al contar")
    else:
        print(f"  ❌ {table} - NO EXISTE en ningún esquema")

conn.close()

print("\n" + "=" * 80)
