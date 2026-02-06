"""Check dim_colegios columns"""
import duckdb
conn = duckdb.connect("C:/proyectos/dbt/icfes_processing/prod_v2.duckdb", read_only=True)
print("Columns in dim_colegios:")
cols = conn.execute("DESCRIBE dim_colegios").fetchall()
for col in cols:
    print(f"  - {col[0]} ({col[1]})")

print("\nSample data:")
sample = conn.execute("SELECT * FROM dim_colegios LIMIT 3").fetchdf()
print(sample)
conn.close()
