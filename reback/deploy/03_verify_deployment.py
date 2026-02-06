"""
Script 3: Verify Deployment

This script verifies that the deployment was successful by checking:
1. All gold tables exist in prod
2. Row counts match between dev and prod
3. dim_colegios_slugs table exists and has data
4. Sample queries work correctly

Run this script after syncing tables (02_sync_gold_to_prod.py).
"""
import duckdb
from pathlib import Path

# Database paths
DEV_DB = Path(r"C:\proyectos\dbt\icfes_processing\dev.duckdb")
PROD_DB = Path(r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb")

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
    print("STEP 3: VERIFYING DEPLOYMENT")
    print("=" * 80)
    
    # Verify databases exist
    if not DEV_DB.exists():
        print(f"\n❌ ERROR: Dev database not found at {DEV_DB}")
        return False
    
    if not PROD_DB.exists():
        print(f"\n❌ ERROR: Prod database not found at {PROD_DB}")
        return False
    
    print(f"\n📂 Dev: {DEV_DB}")
    print(f"📂 Prod: {PROD_DB}")
    
    # Connect to both databases
    conn_dev = duckdb.connect(str(DEV_DB), read_only=True)
    conn_prod = duckdb.connect(str(PROD_DB), read_only=True)
    
    try:
        # Check 1: Verify all tables exist
        print("\n1. Verifying all gold tables exist in prod...")
        
        dev_tables = set(get_gold_tables(conn_dev))
        prod_tables = set(get_gold_tables(conn_prod))
        
        missing_tables = dev_tables - prod_tables
        extra_tables = prod_tables - dev_tables
        
        if missing_tables:
            print(f"   ❌ Missing tables in prod: {missing_tables}")
            return False
        else:
            print(f"   ✅ All {len(dev_tables)} tables exist in prod")
        
        if extra_tables:
            print(f"   ℹ️  Extra tables in prod (not in dev): {extra_tables}")
        
        # Check 2: Verify row counts match
        print("\n2. Verifying row counts match...")
        
        mismatches = []
        
        for table in sorted(dev_tables):
            count_dev = conn_dev.execute(f"SELECT COUNT(*) FROM gold.{table}").fetchone()[0]
            count_prod = conn_prod.execute(f"SELECT COUNT(*) FROM gold.{table}").fetchone()[0]
            
            if count_dev != count_prod:
                mismatches.append((table, count_dev, count_prod))
                print(f"   ❌ {table}: dev={count_dev:,}, prod={count_prod:,}")
            else:
                print(f"   ✅ {table}: {count_dev:,} rows")
        
        if mismatches:
            print(f"\n   ❌ Found {len(mismatches)} tables with row count mismatches")
            return False
        
        # Check 3: Verify dim_colegios_slugs
        print("\n3. Verifying dim_colegios_slugs table...")
        
        if 'dim_colegios_slugs' not in prod_tables:
            print("   ❌ dim_colegios_slugs table not found in prod")
            return False
        
        slug_count = conn_prod.execute("SELECT COUNT(*) FROM gold.dim_colegios_slugs").fetchone()[0]
        print(f"   ✅ Found {slug_count:,} slugs in prod")
        
        # Check for duplicates
        dup_count = conn_prod.execute("""
            SELECT COUNT(*) 
            FROM (
                SELECT slug, COUNT(*) as cnt 
                FROM gold.dim_colegios_slugs 
                GROUP BY slug 
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        
        if dup_count > 0:
            print(f"   ⚠️  Warning: Found {dup_count} duplicate slugs")
        else:
            print("   ✅ No duplicate slugs found")
        
        # Check 4: Sample queries
        print("\n4. Testing sample queries...")
        
        # Test 1: Get a random school by slug
        sample_slug = conn_prod.execute("""
            SELECT slug, nombre_colegio 
            FROM gold.dim_colegios_slugs 
            LIMIT 1
        """).fetchone()
        
        if sample_slug:
            slug, nombre = sample_slug
            print(f"\n   Test 1: Lookup school by slug")
            print(f"      Slug: {slug}")
            print(f"      Name: {nombre}")
            
            # Try to get historical data for this school
            codigo = conn_prod.execute(f"""
                SELECT codigo 
                FROM gold.dim_colegios_slugs 
                WHERE slug = '{slug}'
            """).fetchone()[0]
            
            hist_count = conn_prod.execute(f"""
                SELECT COUNT(*) 
                FROM gold.fct_colegio_historico 
                WHERE codigo_dane = '{codigo}'
            """).fetchone()[0]
            
            print(f"      Historical records: {hist_count}")
            
            if hist_count > 0:
                print("      ✅ Can retrieve historical data")
            else:
                print("      ⚠️  No historical data for this school")
        
        # Summary
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)
        print(f"\n✅ All tables synced: {len(dev_tables)} tables")
        print(f"✅ All row counts match")
        print(f"✅ Slugs table ready: {slug_count:,} slugs")
        print("\n🎉 Deployment verified successfully!")
        
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
