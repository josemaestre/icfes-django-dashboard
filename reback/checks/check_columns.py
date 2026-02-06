"""
Ver todas las columnas de fct_colegio_historico
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

print("=== COLUMNAS DE fct_colegio_historico ===\n")
cols = conn.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'fct_colegio_historico'
    ORDER BY ordinal_position
""").fetchall()

for col, dtype in cols:
    print(f"  {col}: {dtype}")

print(f"\nTotal: {len(cols)} columnas")
conn.close()
