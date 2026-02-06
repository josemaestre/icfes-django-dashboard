"""
Ver una fila de ejemplo para confirmar nombres de columnas.
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

# Obtener una fila de ejemplo
print("Obteniendo una fila de ejemplo de fct_colegio_historico...\n")
result = conn.execute("""
    SELECT * FROM fct_colegio_historico 
    WHERE ano = 2024 
    LIMIT 1
""").fetchdf()

print("Columnas disponibles:")
for col in result.columns:
    print(f"  - {col}")

conn.close()
