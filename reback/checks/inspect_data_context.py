
import duckdb
import pandas as pd
from pathlib import Path

# Paths to databases
DEV_DB = Path(r'c:\proyectos\dbt\icfes_processing\dev.duckdb')
PROD_DB = Path(r'c:\proyectos\dbt\icfes_processing\prod_v2.duckdb')

def inspect_db(db_path, env_name):
    print(f"\n{'='*50}")
    print(f"Inspecting {env_name} Database: {db_path}")
    print(f"{'='*50}")
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        
        # List tables in silver and gold schemas
        query = """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables 
            WHERE table_schema IN ('silver', 'gold')
            ORDER BY table_schema, table_name
        """
        tables = conn.execute(query).fetchall()
        
        for schema, table, type in tables:
            print(f"\n🔹 {schema}.{table} ({type})")
            
            # Get columns
            cols = conn.execute(f"DESCRIBE {schema}.{table}").fetchall()
            col_names = [c[0] for c in cols]
            print(f"   Columns ({len(cols)}): {', '.join(col_names[:10])} {'...' if len(col_names)>10 else ''}")
            
            # Get sample row
            try:
                sample = conn.execute(f"SELECT * FROM {schema}.{table} LIMIT 1").fetchone()
                if sample:
                    print(f"   Sample: {sample}")
                else:
                    print("   Sample: [Empty Table]")
            except Exception as e:
                print(f"   ⚠️ Could not fetch sample: {e}")

        conn.close()
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")

if __name__ == "__main__":
    inspect_db(DEV_DB, "DEVELOPMENT")
    # Uncomment to inspect prod if needed, but sticking to dev for context building primarily
    # inspect_db(PROD_DB, "PRODUCTION")
