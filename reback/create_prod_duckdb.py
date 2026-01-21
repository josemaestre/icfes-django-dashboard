"""
Script to create production DuckDB database with only gold tables.
Uses EXPORT/IMPORT to avoid memory issues with large tables.
"""
import duckdb
import os
import tempfile
import shutil
from pathlib import Path

# Configuration
DEV_DB_PATH = r"C:\Proyectos\dbt\icfes_processing\dev.duckdb"
PROD_DB_PATH = r"C:\Proyectos\dbt\icfes_processing\prod.duckdb"

def get_gold_tables(conn):
    """Get list of all tables from the gold schema."""
    query = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'gold'
    ORDER BY table_name
    """
    result = conn.execute(query).fetchall()
    return [row[0] for row in result]

def create_production_db():
    """Create production database with only gold tables."""
    
    print("Connecting to development database...")
    dev_conn = duckdb.connect(DEV_DB_PATH, read_only=True)
    
    print("Finding gold tables...")
    gold_tables = get_gold_tables(dev_conn)
    
    if not gold_tables:
        print("ERROR: No gold tables found!")
        return
    
    print(f"Found {len(gold_tables)} gold tables:")
    for table in gold_tables:
        print(f"   - {table}")
    
    # Delete existing prod.duckdb if it exists
    if os.path.exists(PROD_DB_PATH):
        print(f"\nRemoving existing {PROD_DB_PATH}...")
        os.remove(PROD_DB_PATH)
    
    print(f"\nCreating production database: {PROD_DB_PATH}")
    prod_conn = duckdb.connect(PROD_DB_PATH)
    
    # Create temporary directory for exports
    temp_dir = tempfile.mkdtemp()
    print(f"Using temp directory: {temp_dir}")
    
    try:
        # Copy each gold table
        total_rows = 0
        for i, table in enumerate(gold_tables, 1):
            print(f"\n[{i}/{len(gold_tables)}] Copying {table}...")
            
            # Get row count
            count_query = f"SELECT COUNT(*) FROM gold.{table}"
            row_count = dev_conn.execute(count_query).fetchone()[0]
            
            # Export to parquet file
            export_path = os.path.join(temp_dir, f"{table}.parquet")
            export_query = f"COPY gold.{table} TO '{export_path}' (FORMAT PARQUET)"
            dev_conn.execute(export_query)
            
            # Import into prod database
            import_query = f"CREATE TABLE {table} AS SELECT * FROM '{export_path}'"
            prod_conn.execute(import_query)
            
            # Delete temp file
            os.remove(export_path)
            
            print(f"   OK: Copied {row_count:,} rows")
            total_rows += row_count
    
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Close connections
    dev_conn.close()
    prod_conn.close()
    
    # Get file sizes
    dev_size = os.path.getsize(DEV_DB_PATH) / (1024**3)  # GB
    prod_size = os.path.getsize(PROD_DB_PATH) / (1024**3)  # GB
    
    print("\n" + "="*60)
    print("SUCCESS: Production database created!")
    print("="*60)
    print(f"Statistics:")
    print(f"   - Tables copied: {len(gold_tables)}")
    print(f"   - Total rows: {total_rows:,}")
    print(f"   - Dev DB size: {dev_size:.2f} GB")
    print(f"   - Prod DB size: {prod_size:.2f} GB")
    print(f"   - Size reduction: {((dev_size - prod_size) / dev_size * 100):.1f}%")
    print(f"\nProduction database: {os.path.abspath(PROD_DB_PATH)}")
    print("\nReady to upload to Railway!")

if __name__ == "__main__":
    try:
        create_production_db()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
