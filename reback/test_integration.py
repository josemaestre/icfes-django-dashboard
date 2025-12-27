"""
Script de prueba para verificar la integración con DuckDB.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

import duckdb
from django.conf import settings
from icfes_dashboard.db_utils import (
    get_duckdb_connection,
    execute_query,
    get_anos_disponibles,
    get_departamentos,
    get_estadisticas_generales
)

def test_duckdb_installation():
    """Verifica que DuckDB esté instalado."""
    print("=" * 80)
    print("1. VERIFICANDO INSTALACIÓN DE DUCKDB")
    print("=" * 80)
    print(f"✓ DuckDB version: {duckdb.__version__}")
    print(f"✓ Ruta configurada: {settings.ICFES_DUCKDB_PATH}")
    print(f"✓ Archivo existe: {os.path.exists(settings.ICFES_DUCKDB_PATH)}")
    print()

def test_connection():
    """Prueba la conexión básica a DuckDB."""
    print("=" * 80)
    print("2. PROBANDO CONEXIÓN A DUCKDB")
    print("=" * 80)
    try:
        with get_duckdb_connection() as con:
            result = con.execute("SELECT 'Conexión exitosa!' as mensaje").df()
            print(f"✓ {result.iloc[0]['mensaje']}")
            print()
            return True
    except Exception as e:
        print(f"✗ Error en conexión: {e}")
        print()
        return False

def test_tables_exist():
    """Verifica que las tablas gold existan."""
    print("=" * 80)
    print("3. VERIFICANDO TABLAS GOLD")
    print("=" * 80)
    
    tables = [
        'gold.fact_icfes_analytics',
        'gold.dim_colegios',
        'gold.dim_colegios_ano',
        'gold.fct_agg_colegios_ano',
        'gold.tendencias_regionales',
        'gold.brechas_educativas',
        'gold.colegios_destacados'
    ]
    
    for table in tables:
        try:
            query = f"SELECT COUNT(*) as count FROM {table}"
            df = execute_query(query)
            count = df.iloc[0]['count']
            print(f"✓ {table}: {count:,} registros")
        except Exception as e:
            print(f"✗ {table}: Error - {e}")
    print()

def test_db_utils():
    """Prueba las funciones de db_utils."""
    print("=" * 80)
    print("4. PROBANDO FUNCIONES DE DB_UTILS")
    print("=" * 80)
    
    try:
        # Test get_anos_disponibles
        anos = get_anos_disponibles()
        print(f"✓ get_anos_disponibles(): {len(anos)} años encontrados")
        print(f"  Rango: {min(anos)} - {max(anos)}")
        
        # Test get_departamentos
        deptos = get_departamentos()
        print(f"✓ get_departamentos(): {len(deptos)} departamentos encontrados")
        
        # Test get_estadisticas_generales
        stats = get_estadisticas_generales(ano=2023)
        print(f"✓ get_estadisticas_generales(2023):")
        print(f"  - Total estudiantes: {stats.get('total_estudiantes', 0):,}")
        print(f"  - Total colegios: {stats.get('total_colegios', 0):,}")
        print(f"  - Promedio nacional: {stats.get('promedio_nacional', 0):.2f}")
        
    except Exception as e:
        print(f"✗ Error en db_utils: {e}")
    print()

def test_sample_queries():
    """Ejecuta queries de muestra."""
    print("=" * 80)
    print("5. EJECUTANDO QUERIES DE MUESTRA")
    print("=" * 80)
    
    # Query 1: Top 5 colegios 2023
    try:
        query = """
            SELECT 
                nombre_colegio,
                departamento,
                avg_punt_global,
                ranking_nacional
            FROM gold.colegios_destacados
            WHERE ano = 2023
            ORDER BY ranking_nacional
            LIMIT 5
        """
        df = execute_query(query)
        print("✓ Top 5 Colegios 2023:")
        for idx, row in df.iterrows():
            print(f"  {row['ranking_nacional']}. {row['nombre_colegio']} ({row['departamento']}) - {row['avg_punt_global']:.2f}")
    except Exception as e:
        print(f"✗ Error en query top colegios: {e}")
    
    print()
    
    # Query 2: Tendencias regionales recientes
    try:
        query = """
            SELECT 
                region,
                ano,
                avg_punt_global,
                total_estudiantes
            FROM gold.tendencias_regionales
            WHERE ano >= 2022
            ORDER BY ano DESC, avg_punt_global DESC
            LIMIT 10
        """
        df = execute_query(query)
        print(f"✓ Tendencias Regionales (últimos años): {len(df)} registros")
    except Exception as e:
        print(f"✗ Error en query tendencias: {e}")
    
    print()

def main():
    """Ejecuta todas las pruebas."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "PRUEBAS DE INTEGRACIÓN ICFES-DBT" + " " * 25 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    test_duckdb_installation()
    
    if test_connection():
        test_tables_exist()
        test_db_utils()
        test_sample_queries()
    
    print("=" * 80)
    print("PRUEBAS COMPLETADAS")
    print("=" * 80)
    print()

if __name__ == '__main__':
    main()
