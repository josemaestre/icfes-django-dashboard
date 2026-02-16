
from django.core.management.base import BaseCommand
from django.conf import settings
import duckdb
import os

class Command(BaseCommand):
    help = 'Backfills municipality aggregation data for Tuluá to fix 2015-2024 gap caused by accent in source data'

    def handle(self, *args, **options):
        db_path = settings.ICFES_DUCKDB_PATH
        self.stdout.write(f"Connecting to DB at: {db_path}")
        
        try:
            conn = duckdb.connect(db_path, read_only=False)
            
            # Check current state
            pre_count = conn.execute(
                "SELECT count(*) FROM gold.fct_agg_colegios_ano WHERE municipio = 'TULUA' AND CAST(ano AS INTEGER) > 2014"
            ).fetchone()[0]
            self.stdout.write(f"Records for TULUA > 2014 before fix: {pre_count}")
            
            if pre_count > 0:
                self.stdout.write(self.style.WARNING("Data already exists. Running this might duplicate records if not careful."))
                # Proceeding anyway as the query is idempotent in logic (it inserts based on source), but we could add a verification.
                # Ideally we should delete first to be safe or use INSERT OR IGNORE if supported/applicable. 
                # Given DuckDB simplicity, deleting specific range for Tuluá first is safer to avoid dupes.
                self.stdout.write("Cleaning up existing > 2014 data for TULUA to avoid duplicates...")
                conn.execute("DELETE FROM gold.fct_agg_colegios_ano WHERE municipio = 'TULUA' AND CAST(ano AS INTEGER) > 2014")

            self.stdout.write("Executing Backfill...")
            # Select from 'TULUÁ' (accented) or 'TULUA' (unaccented) from source
            # Insert as 'TULUA' (unaccented) to target
            insert_query = """
                INSERT INTO gold.fct_agg_colegios_ano (ano, departamento, municipio, colegio_bk, colegio_sk, nombre_colegio, sector, total_estudiantes, avg_punt_global)
                SELECT 
                    ano, 
                    departamento, 
                    'TULUA' as municipio, 
                    codigo_dane, 
                    colegio_sk, 
                    nombre_colegio, 
                    sector, 
                    1,
                    avg_punt_global
                FROM gold.fct_colegio_historico
                WHERE (municipio = 'TULUÁ' OR municipio = 'TULUA')
                  AND CAST(ano AS INTEGER) > 2014
            """
            conn.execute(insert_query)
            
            # Verify
            post_count = conn.execute(
                "SELECT count(*) FROM gold.fct_agg_colegios_ano WHERE municipio = 'TULUA' AND CAST(ano AS INTEGER) > 2014"
            ).fetchone()[0]
            
            self.stdout.write(self.style.SUCCESS(f"Successfully backfilled Tuluá data. Records > 2014: {post_count}"))
            
            conn.close()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
