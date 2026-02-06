"""
Script standalone para generar slugs de colegios.
Se puede ejecutar directamente sin Django management command.

Usage:
    python generate_school_slugs.py [--dry-run]
"""
import sys
import os
import argparse

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
import django
django.setup()

from reback.icfes_dashboard.db_utils import get_duckdb_connection
from reback.icfes_dashboard.landing_utils import generate_school_slug


def main():
    parser = argparse.ArgumentParser(description='Generate SEO-friendly slugs for all schools')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing to database')
    args = parser.parse_args()
    
    print('🚀 Starting slug generation...')
    
    try:
        conn = get_duckdb_connection()
        
        # Get all unique schools from 2024 data
        print('📊 Fetching schools from database...')
        schools_query = """
            SELECT DISTINCT
                cole_cod_dane_establecimiento as codigo,
                nombre_colegio,
                cole_nombre_municipio as municipio,
                cole_nombre_departamento as departamento,
                cole_naturaleza as sector,
                cole_jornada as jornada,
                cole_area_ubicacion as area
            FROM gold.fct_icfes_analytics
            WHERE ano = 2024
            ORDER BY nombre_colegio
        """
        
        schools_df = conn.execute(schools_query).fetchdf()
        total_schools = len(schools_df)
        
        print(f'✓ Found {total_schools} schools')
        
        # Generate slugs
        print('⚙️  Generating slugs...')
        slugs = []
        slug_counts = {}
        
        for idx, school in schools_df.iterrows():
            # Generate base slug
            slug = generate_school_slug(
                school['nombre_colegio'],
                school['municipio']
            )
            
            # Handle duplicates by appending codigo
            if slug in slug_counts:
                slug_counts[slug] += 1
                slug = f"{slug}-{school['codigo']}"
            else:
                slug_counts[slug] = 1
            
            slugs.append({
                'codigo': school['codigo'],
                'nombre_colegio': school['nombre_colegio'],
                'municipio': school['municipio'],
                'departamento': school['departamento'],
                'sector': school['sector'],
                'jornada': school['jornada'],
                'area': school['area'],
                'slug': slug
            })
            
            # Progress indicator
            if (idx + 1) % 1000 == 0:
                print(f'  Processed {idx + 1}/{total_schools} schools...')
        
        print(f'✓ Generated {len(slugs)} unique slugs')
        
        # Show sample
        print('\n📝 Sample slugs:')
        for i in range(min(10, len(slugs))):
            print(f'  {slugs[i]["slug"]} → {slugs[i]["nombre_colegio"]}')
        
        if args.dry_run:
            print('\n⚠️  --dry-run mode: Not writing to database')
            print('\nTo actually create the table, run without --dry-run:')
            print('  python generate_school_slugs.py')
            return
        
        # Create table in DuckDB
        print('\n💾 Creating/updating dim_colegios_slugs table...')
        
        # Drop existing table if exists
        conn.execute("DROP TABLE IF EXISTS gold.dim_colegios_slugs")
        
        # Create new table
        create_table_sql = """
            CREATE TABLE gold.dim_colegios_slugs (
                codigo VARCHAR PRIMARY KEY,
                nombre_colegio VARCHAR,
                municipio VARCHAR,
                departamento VARCHAR,
                sector VARCHAR,
                jornada VARCHAR,
                area VARCHAR,
                slug VARCHAR UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        conn.execute(create_table_sql)
        
        # Insert data in batches
        batch_size = 1000
        for i in range(0, len(slugs), batch_size):
            batch = slugs[i:i + batch_size]
            
            insert_sql = """
                INSERT INTO gold.dim_colegios_slugs 
                (codigo, nombre_colegio, municipio, departamento, sector, jornada, area, slug)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            values = [
                (
                    s['codigo'],
                    s['nombre_colegio'],
                    s['municipio'],
                    s['departamento'],
                    s['sector'],
                    s['jornada'],
                    s['area'],
                    s['slug']
                )
                for s in batch
            ]
            
            conn.executemany(insert_sql, values)
            
            print(f'  Inserted batch {i//batch_size + 1}/{(len(slugs)-1)//batch_size + 1}')
        
        # Create index on slug for fast lookups
        conn.execute("CREATE INDEX idx_slug ON gold.dim_colegios_slugs(slug)")
        
        # Verify
        count = conn.execute("SELECT COUNT(*) FROM gold.dim_colegios_slugs").fetchone()[0]
        
        print(f'\n✅ Successfully created table with {count} schools')
        print('✅ Created index on slug column')
        
        # Show some example URLs
        print('\n🌐 Example landing page URLs:')
        sample_slugs = conn.execute("""
            SELECT slug, nombre_colegio, municipio 
            FROM gold.dim_colegios_slugs 
            LIMIT 5
        """).fetchall()
        
        for slug, nombre, municipio in sample_slugs:
            url = f'/icfes/colegio/{slug}/'
            print(f'  {url}')
            print(f'    → {nombre} ({municipio})')
        
        print('\n🎉 Slug generation complete!')
        
    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
