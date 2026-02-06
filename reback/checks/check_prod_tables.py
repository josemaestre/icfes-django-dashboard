"""
Quick script to check what tables exist in prod_v2.duckdb
"""
import duckdb

conn = duckdb.connect("C:/proyectos/dbt/icfes_processing/prod_v2.duckdb", read_only=True)

print("Schemas:")
schemas = conn.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
for schema in schemas:
    print(f"  - {schema[0]}")

print("\nTables in gold schema:")
tables = conn.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'gold'
    ORDER BY table_name
""").fetchall()

for table in tables:
    print(f"  - gold.{table[0]}")

print("\nTables without schema prefix:")
tables2 = conn.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'main'
    ORDER BY table_name
""").fetchall()

for table in tables2:
    print(f"  - {table[0]}")

conn.close()
