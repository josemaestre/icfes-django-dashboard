"""
Script 2: Sync Gold Tables from Dev to Prod

This script copies all tables from the gold schema in dev.duckdb
to the gold schema in prod_v2.duckdb.

Run this script after generating slugs (01_generate_slugs.py).
"""
import duckdb
from pathlib import Path
import shutil
from datetime import datetime

# Database paths
DEV_DB = Path(r"C:\proyectos\dbt\icfes_processing\dev.duckdb")
PROD_DB = Path(r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb")

def create_backup(db_path):
    """Create a backup of the database before modifications."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
    
    print(f"   Creating backup: {backup_path.name}")
    shutil.copy2(db_path, backup_path)
    
    return backup_path

def get_gold_tables(conn):
    """Get list of all tables in gold schema."""
    tables = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'gold'
        ORDER BY table_name
    """).fetchall()
    
    return [t[0] for t in tables]

def main():
    print("=" * 80)
    print("STEP 2: SYNCING GOLD TABLES FROM DEV TO PROD")
    print("=" * 80)
    
    # Verify databases exist
    if not DEV_DB.exists():
        print(f"\n❌ ERROR: Dev database not found at {DEV_DB}")
        return False
    
    if not PROD_DB.exists():
        print(f"\n❌ ERROR: Prod database not found at {PROD_DB}")
        return False
    
    print(f"\n📂 Source (DEV): {DEV_DB}")
    print(f"📂 Target (PROD): {PROD_DB}")
    
    # Create backup of prod
    print("\n1. Creating backup of production database...")
    try:
        backup_path = create_backup(PROD_DB)
        print(f"   ✅ Backup created successfully")
    except Exception as e:
        print(f"   ❌ ERROR creating backup: {e}")
        return False
    
    # Connect to both databases
    print("\n2. Connecting to databases...")
    conn_dev = duckdb.connect(str(DEV_DB), read_only=True)
    conn_prod = duckdb.connect(str(PROD_DB), read_only=False)
    
    try:
        # Get list of gold tables from dev
        print("\n3. Fetching gold tables from dev...")
        gold_tables = get_gold_tables(conn_dev)
        print(f"   Found {len(gold_tables)} tables in gold schema")
        
        # Create gold schema in prod if it doesn't exist
        print("\n4. Ensuring gold schema exists in prod...")
        conn_prod.execute("CREATE SCHEMA IF NOT EXISTS gold")
        
        # Copy each table
        print("\n5. Copying tables from dev to prod...")
        
        copied_tables = []
        failed_tables = []
        
        for table_name in gold_tables:
            try:
                print(f"\n   Copying: gold.{table_name}")
                
                # Get row count from dev
                count_dev = conn_dev.execute(f"SELECT COUNT(*) FROM gold.{table_name}").fetchone()[0]
                print(f"      Dev rows: {count_dev:,}")
                
                # Drop both table and view in prod if they exist (handles both cases)
                conn_prod.execute(f"DROP TABLE IF EXISTS gold.{table_name}")
                conn_prod.execute(f"DROP VIEW IF EXISTS gold.{table_name}")
                
                # Fetch data from dev
                data = conn_dev.execute(f"SELECT * FROM gold.{table_name}").fetchdf()
                
                # Create table in prod with data
                conn_prod.execute(f"CREATE TABLE gold.{table_name} AS SELECT * FROM data")
                
                # Verify
                count_prod = conn_prod.execute(f"SELECT COUNT(*) FROM gold.{table_name}").fetchone()[0]
                print(f"      Prod rows: {count_prod:,}")
                
                if count_dev == count_prod:
                    print(f"      ✅ Success")
                    copied_tables.append(table_name)
                else:
                    print(f"      ⚠️  Row count mismatch!")
                    failed_tables.append(table_name)
                    
            except Exception as e:
                print(f"      ❌ ERROR: {e}")
                failed_tables.append(table_name)
        
        # Summary
        print("\n" + "=" * 80)
        print("SYNC SUMMARY")
        print("=" * 80)
        print(f"\n✅ Successfully copied: {len(copied_tables)} tables")
        
        if failed_tables:
            print(f"\n❌ Failed to copy: {len(failed_tables)} tables")
            for table in failed_tables:
                print(f"   - {table}")
            return False
        else:
            print("\n🎉 All tables synced successfully!")
            print(f"\n💾 Backup saved at: {backup_path}")
            return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn_dev.close()
        conn_prod.close()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
