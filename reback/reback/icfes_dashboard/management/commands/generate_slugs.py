"""
Django management command to generate SEO-friendly slugs for all schools.

Usage:
    python manage.py generate_slugs
    
This command:
1. Reads all schools from DuckDB
2. Generates unique slugs for each school
3. Creates/updates dim_colegios_slugs table in DuckDB
4. Handles duplicate slugs by appending codigo
"""
from django.core.management.base import BaseCommand
from reback.icfes_dashboard.db_utils import get_duckdb_connection
from reback.icfes_dashboard.landing_utils import generate_school_slug
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate SEO-friendly slugs for all schools and store in DuckDB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview slugs without writing to database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('Starting slug generation...'))
        
        try:
            conn = get_duckdb_connection()
            
            # Get all unique schools from 2024 data
            self.stdout.write('Fetching schools from database...')
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
            
            self.stdout.write(f'Found {total_schools} schools')
            
            # Generate slugs
            self.stdout.write('Generating slugs...')
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
                    self.stdout.write(f'  Processed {idx + 1}/{total_schools} schools...')
            
            self.stdout.write(self.style.SUCCESS(f'✓ Generated {len(slugs)} unique slugs'))
            
            # Show sample
            self.stdout.write('\nSample slugs:')
            for i in range(min(10, len(slugs))):
                self.stdout.write(f'  {slugs[i]["slug"]} → {slugs[i]["nombre_colegio"]}')
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\n--dry-run mode: Not writing to database'))
                return
            
            # Create table in DuckDB
            self.stdout.write('\nCreating/updating dim_colegios_slugs table...')
            
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
                
                self.stdout.write(f'  Inserted batch {i//batch_size + 1}/{(len(slugs)-1)//batch_size + 1}')
            
            # Create index on slug for fast lookups
            conn.execute("CREATE INDEX idx_slug ON gold.dim_colegios_slugs(slug)")
            
            # Verify
            count = conn.execute("SELECT COUNT(*) FROM gold.dim_colegios_slugs").fetchone()[0]
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully created table with {count} schools'))
            self.stdout.write(self.style.SUCCESS('✓ Created index on slug column'))
            
            # Show some example URLs
            self.stdout.write('\nExample landing page URLs:')
            sample_slugs = conn.execute("""
                SELECT slug, nombre_colegio, municipio 
                FROM gold.dim_colegios_slugs 
                LIMIT 5
            """).fetchall()
            
            for slug, nombre, municipio in sample_slugs:
                url = f'/icfes/colegio/{slug}/'
                self.stdout.write(f'  {url}')
                self.stdout.write(f'    → {nombre} ({municipio})')
            
            self.stdout.write(self.style.SUCCESS('\n✓ Slug generation complete!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            logger.error(f"Error generating slugs: {str(e)}", exc_info=True)
            raise
