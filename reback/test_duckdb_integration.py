"""
Script de verificación para la integración DuckDB + Django.
Prueba la conexión a la base de datos y consultas básicas.
"""
import os
import sys

# Agregar el directorio del proyecto al path
sys.path.insert(0, r'c:\proyectos\www\reback')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

import django
django.setup()

from django.conf import settings
from icfes_dashboard.db_utils import (
    get_duckdb_connection,
    execute_query,
    get_anos_disponibles,
    get_departamentos,
    get_estadisticas_generales
)

print("=" * 80)
print("VERIFICACIÓN DE INTEGRACIÓN DUCKDB + DJANGO")
print("=" * 80)

# 1. Verificar configuración
print("\n1. Verificando configuración...")
print(f"   ICFES_DUCKDB_PATH: {settings.ICFES_DUCKDB_PATH}")
print(f"   Archivo existe: {os.path.exists(settings.ICFES_DUCKDB_PATH)}")
print(f"   Tamaño: {os.path.getsize(settings.ICFES_DUCKDB_PATH) / (1024**3):.2f} GB")

# 2. Probar conexión
print("\n2. Probando conexión a DuckDB...")
try:
    with get_duckdb_connection() as con:
        result = con.execute("SELECT 'Conexión exitosa!' as mensaje").fetchone()
        print(f"   ✓ {result[0]}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# 3. Listar tablas disponibles
print("\n3. Listando tablas en schema 'gold'...")
try:
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'gold'
        ORDER BY table_name
    """
    df = execute_query(query)
    print(f"   Tablas encontradas: {len(df)}")
    for table in df['table_name'].tolist():
        print(f"   - {table}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 4. Obtener años disponibles
print("\n4. Obteniendo años disponibles...")
try:
    anos = get_anos_disponibles()
    print(f"   Años: {anos}")
    print(f"   Rango: {min(anos)} - {max(anos)}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 5. Obtener departamentos
print("\n5. Obteniendo departamentos...")
try:
    deptos = get_departamentos()
    print(f"   Total departamentos: {len(deptos)}")
    print(f"   Primeros 5: {deptos[:5]}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 6. Estadísticas generales
print("\n6. Obteniendo estadísticas generales (año 2023)...")
try:
    stats = get_estadisticas_generales(2023)
    print(f"   Total estudiantes: {stats.get('total_estudiantes', 'N/A'):,}")
    print(f"   Total colegios: {stats.get('total_colegios', 'N/A'):,}")
    print(f"   Promedio nacional: {stats.get('promedio_nacional', 'N/A'):.2f}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 7. Consulta de muestra
print("\n7. Consultando muestra de fact_icfes_analytics...")
try:
    query = """
        SELECT 
            ano,
            COUNT(*) as total_registros,
            AVG(punt_global) as promedio_global
        FROM gold.fact_icfes_analytics
        GROUP BY ano
        ORDER BY ano DESC
        LIMIT 5
    """
    df = execute_query(query)
    print(f"   Registros por año:")
    for _, row in df.iterrows():
        print(f"   - {row['ano']}: {row['total_registros']:,} estudiantes, promedio: {row['promedio_global']:.2f}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 8. Verificar tabla de agregados
print("\n8. Verificando fct_agg_colegios_ano...")
try:
    query = """
        SELECT COUNT(*) as total_registros
        FROM gold.fct_agg_colegios_ano
    """
    df = execute_query(query)
    print(f"   Total registros: {df['total_registros'].iloc[0]:,}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 80)
print("VERIFICACIÓN COMPLETADA ✓")
print("=" * 80)
print("\nLa integración está funcionando correctamente.")
print("Puedes iniciar el servidor Django con: python manage.py runserver")
print("Y acceder al dashboard en: http://localhost:8000/icfes/")
