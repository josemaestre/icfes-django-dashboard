"""
Verificar columnas de fct_colegio_historico
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\dev.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

print("Columnas en gold.fct_colegio_historico:\n")

columns = conn.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'gold'
    AND table_name = 'fct_colegio_historico'
    ORDER BY ordinal_position
""").fetchall()

for col, dtype in columns:
    print(f"  {col:40} {dtype}")

print(f"\nTotal: {len(columns)} columnas")

# Verificar si existe codigo_dane o colegio_sk
print("\n¿Qué columna de identificación tiene?")
for col, _ in columns:
    if 'codigo' in col.lower() or 'colegio_sk' in col.lower():
        print(f"  ✅ {col}")

conn.close()
