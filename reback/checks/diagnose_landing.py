"""
Script de diagnóstico para probar la vista de landing page.
"""
import duckdb
import sys

DB_PATH = r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb"

print("=" * 80)
print("DIAGNÓSTICO DE LANDING PAGE")
print("=" * 80)

try:
    # Simular exactamente lo que hace la vista
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    slug = "abc-centro-educativo-medellin"
    print(f"\n1. Buscando colegio con slug: {slug}")
    
    school_query = """
        SELECT 
            codigo,
            nombre_colegio,
            municipio,
            departamento,
            sector,
            jornada,
            area
        FROM gold.dim_colegios_slugs
        WHERE slug = ?
        LIMIT 1
    """
    
    school_result = conn.execute(school_query, [slug]).fetchone()
    
    if not school_result:
        print("❌ ERROR: Colegio no encontrado")
        print("\nVerificando slugs disponibles...")
        samples = conn.execute("""
            SELECT slug FROM gold.dim_colegios_slugs 
            WHERE slug LIKE 'abc%' 
            LIMIT 5
        """).fetchall()
        print("Slugs que empiezan con 'abc':")
        for s in samples:
            print(f"  - {s[0]}")
        sys.exit(1)
    
    print(f"✅ Colegio encontrado: {school_result[1]}")
    codigo = school_result[0]
    print(f"   Código: {codigo}")
    
    # Probar query de estadísticas
    print(f"\n2. Obteniendo estadísticas 2024...")
    stats_query = """
        SELECT 
            ano,
            avg_punt_global,
            avg_punt_matematicas,
            avg_punt_lectura_critica,
            avg_punt_ciencias_naturales,
            avg_punt_sociales_ciudadanas,
            avg_punt_ingles
        FROM fct_colegio_historico
        WHERE codigo_dane = ?
        AND ano = 2024
        LIMIT 1
    """
    
    stats = conn.execute(stats_query, [codigo]).fetchone()
    
    if stats:
        print(f"✅ Estadísticas encontradas")
        print(f"   Puntaje Global: {stats[1]:.1f}")
    else:
        print("⚠️  No hay estadísticas 2024")
        # Verificar qué años hay disponibles
        years = conn.execute("""
            SELECT DISTINCT ano 
            FROM fct_colegio_historico 
            WHERE codigo_dane = ?
            ORDER BY ano DESC
        """, [codigo]).fetchall()
        print(f"   Años disponibles: {[y[0] for y in years]}")
    
    # Probar query histórica
    print(f"\n3. Obteniendo datos históricos...")
    historico_query = """
        SELECT 
            ano,
            avg_punt_global
        FROM fct_colegio_historico
        WHERE codigo_dane = ?
        AND ano >= 2015
        ORDER BY ano ASC
    """
    
    historico = conn.execute(historico_query, [codigo]).fetchdf()
    
    if not historico.empty:
        print(f"✅ Datos históricos: {len(historico)} registros")
        print(f"   Años: {historico['ano'].min()} - {historico['ano'].max()}")
    else:
        print("⚠️  No hay datos históricos")
    
    # Probar query de comparación
    print(f"\n4. Obteniendo datos de comparación...")
    comparacion_query = """
        SELECT 
            brecha_global_municipal,
            brecha_global_departamental,
            brecha_global_nacional,
            promedio_municipal,
            promedio_departamental,
            promedio_nacional
        FROM fct_colegio_comparacion_contexto
        WHERE codigo_dane = ?
        AND ano = 2024
        LIMIT 1
    """
    
    comparacion = conn.execute(comparacion_query, [codigo]).fetchone()
    
    if comparacion:
        print(f"✅ Datos de comparación encontrados")
        print(f"   Brecha Nacional: {comparacion[2]:.1f}")
    else:
        print("⚠️  No hay datos de comparación 2024")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ DIAGNÓSTICO COMPLETADO - Todo parece estar bien")
    print("=" * 80)
    print("\nEl problema puede estar en cómo Django maneja la conexión.")
    print("Revisar el código de get_duckdb_connection() en db_utils.py")
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
