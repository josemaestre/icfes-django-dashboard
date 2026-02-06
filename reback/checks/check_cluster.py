
import duckdb
import os

db_path = r'c:\proyectos\dbt\icfes_processing\dev.duckdb'

if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
    exit(1)

try:
    con = duckdb.connect(db_path, read_only=True)
    
    # Check if table exists in main schema
    tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'dim_colegios_cluster'").fetchall()
    
    if not tables:
        print("Table 'dim_colegios_cluster' NOT FOUND in 'main' schema.")
        # List all tables to see what's available
        all_tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
        print("Available tables in main:", [t[0] for t in all_tables])
    else:
        print("Table 'dim_colegios_cluster' FOUND in 'main' schema.")
        # Check count
        count = con.execute("SELECT COUNT(*) FROM main.dim_colegios_cluster").fetchone()[0]
        print(f"Row count: {count}")
        
        # Show sample data
        sample = con.execute("SELECT * FROM main.dim_colegios_cluster LIMIT 5").df()
        print("Sample data:")
        print(sample)
        
    con.close()

except Exception as e:
    print(f"Error: {e}")
