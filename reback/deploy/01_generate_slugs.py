"""
Script 1: Generate Slugs for All Schools

This script generates SEO-friendly slugs for all schools in the database
and stores them in the dim_colegios_slugs table.

Run this script first in the deployment process.
"""
import duckdb
import re
import unicodedata
from pathlib import Path
from collections import defaultdict

# Database paths
DEV_DB = Path(r"C:\proyectos\dbt\icfes_processing\dev.duckdb")

def slugify(text):
    """
    Convert text to URL-friendly slug.
    - Normalizes Unicode characters (removes accents)
    - Converts to lowercase
    - Replaces spaces and special chars with hyphens
    - Removes consecutive hyphens
    """
    # Normalize Unicode (NFD = decompose accents from letters)
    text = unicodedata.normalize('NFD', text)
    # Remove diacritical marks (accents)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text

def generate_school_slug(nombre, municipio, departamento, sector):
    """
    Generate unique slug for a school using multiple attributes.
    Format: nombre-municipio
    """
    base_slug = f"{slugify(nombre)}-{slugify(municipio)}"
    return base_slug

def main():
    print("=" * 80)
    print("STEP 1: GENERATING SLUGS FOR ALL SCHOOLS")
    print("=" * 80)
    
    if not DEV_DB.exists():
        print(f"\n❌ ERROR: Database not found at {DEV_DB}")
        return False
    
    print(f"\n📂 Using database: {DEV_DB}")
    
    conn = duckdb.connect(str(DEV_DB), read_only=False)
    
    try:
        # Get all schools from dim_colegios
        print("\n1. Fetching schools from gold.dim_colegios...")
        schools = conn.execute("""
            SELECT 
                colegio_bk as codigo_dane,
                nombre_colegio,
                municipio,
                departamento,
                sector
            FROM gold.dim_colegios
            WHERE colegio_bk IS NOT NULL
            ORDER BY colegio_bk
        """).fetchall()
        
        print(f"   Found {len(schools):,} schools")
        
        # Generate slugs
        print("\n2. Generating slugs...")
        slugs_data = []
        slug_counts = defaultdict(int)
        
        for codigo, nombre, municipio, depto, sector in schools:
            base_slug = generate_school_slug(nombre, municipio, depto, sector)
            
            # Handle duplicates
            slug_counts[base_slug] += 1
            if slug_counts[base_slug] > 1:
                slug = f"{base_slug}-{slug_counts[base_slug]}"
            else:
                slug = base_slug
            
            slugs_data.append({
                'codigo': codigo,
                'nombre_colegio': nombre,
                'municipio': municipio,
                'departamento': depto,
                'sector': sector,
                'slug': slug
            })
        
        print(f"   Generated {len(slugs_data):,} unique slugs")
        
        # Create or replace the slugs table
        print("\n3. Creating gold.dim_colegios_slugs table...")
        
        conn.execute("DROP TABLE IF EXISTS gold.dim_colegios_slugs")
        
        conn.execute("""
            CREATE TABLE gold.dim_colegios_slugs (
                codigo VARCHAR PRIMARY KEY,
                nombre_colegio VARCHAR,
                municipio VARCHAR,
                departamento VARCHAR,
                sector VARCHAR,
                slug VARCHAR UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert data
        print("\n4. Inserting slug data...")
        
        for data in slugs_data:
            conn.execute("""
                INSERT INTO gold.dim_colegios_slugs 
                (codigo, nombre_colegio, municipio, departamento, sector, slug)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                data['codigo'],
                data['nombre_colegio'],
                data['municipio'],
                data['departamento'],
                data['sector'],
                data['slug']
            ])
        
        # Create index
        print("\n5. Creating index on slug column...")
        conn.execute("CREATE INDEX idx_slug ON gold.dim_colegios_slugs(slug)")
        
        # Verify
        count = conn.execute("SELECT COUNT(*) FROM gold.dim_colegios_slugs").fetchone()[0]
        
        print("\n" + "=" * 80)
        print(f"✅ SUCCESS: Generated {count:,} slugs")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
