
import os
import sys
import django
from pathlib import Path

# Setup paths
current_path = Path('c:\\proyectos\\www\\reback').resolve()
sys.path.append(str(current_path))
sys.path.append(str(current_path / "reback"))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from django.conf import settings
from icfes_dashboard.db_utils import execute_query

print(f"Using database: {settings.ICFES_DUCKDB_PATH}")

print("Checking tables in database...")
try:
    # Check tables in gold schema
    df_tables = execute_query("SELECT * FROM information_schema.tables WHERE table_schema = 'gold'")
    print(f"Found {len(df_tables)} tables in gold schema:")
    print(df_tables['table_name'].tolist())
    
    # Check tables in main schema
    df_tables_main = execute_query("SELECT * FROM information_schema.tables WHERE table_schema = 'main'")
    print(f"Found {len(df_tables_main)} tables in main schema:")
    print(df_tables_main['table_name'].tolist())

    print("\nChecking for dim_colegios_cluster...")
    
    found_gold = 'dim_colegios_cluster' in df_tables['table_name'].values
    found_main = 'dim_colegios_cluster' in df_tables_main['table_name'].values
    
    if found_gold:
        print("Found dim_colegios_cluster in GOLD schema")
        df_cluster = execute_query("SELECT * FROM gold.dim_colegios_cluster LIMIT 5")
        if df_cluster.empty:
            print("Table gold.dim_colegios_cluster is EMPTY")
        else:
            print("Table gold.dim_colegios_cluster has data:")
            print(df_cluster)
            
    elif found_main:
        print("Found dim_colegios_cluster in MAIN schema (but not gold)")
        df_cluster = execute_query("SELECT * FROM main.dim_colegios_cluster LIMIT 5")
        if df_cluster.empty:
            print("Table main.dim_colegios_cluster is EMPTY")
        else:
            print("Table main.dim_colegios_cluster has data:")
            print(df_cluster)
    else:
        print("dim_colegios_cluster NOT FOUND in either schema")

except Exception as e:
    print(f"Error: {e}")
