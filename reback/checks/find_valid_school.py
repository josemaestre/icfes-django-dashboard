"""
Encontrar un colegio que exista en ambas tablas para probar
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\dev.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

print("Buscando colegios que existan en AMBAS tablas...\n")

# Obtener algunos códigos de dim_colegios_slugs
print("1. Obteniendo códigos de dim_colegios_slugs...")
slug_codes = conn.execute("""
    SELECT codigo, nombre_colegio, slug
    FROM gold.dim_colegios_slugs
    LIMIT 100
""").fetchall()

print(f"   Obtenidos {len(slug_codes)} códigos de slugs\n")

# Verificar cuáles existen en fct_colegio_historico
print("2. Verificando cuáles existen en fct_colegio_historico...\n")

found = []
for codigo, nombre, slug in slug_codes:
    count = conn.execute(f"""
        SELECT COUNT(*)
        FROM gold.fct_colegio_historico
        WHERE codigo_dane = '{codigo}'
        AND ano = '2024'
    """).fetchone()[0]
    
    if count > 0:
        found.append((codigo, nombre, slug, count))
        if len(found) >= 5:
            break

if found:
    print(f"✅ Encontrados {len(found)} colegios que existen en ambas tablas:\n")
    for codigo, nombre, slug, count in found:
        print(f"  Código: {codigo}")
        print(f"  Nombre: {nombre}")
        print(f"  Slug: {slug}")
        print(f"  Registros en histórico: {count}")
        print(f"  URL: http://127.0.0.1:8000/icfes/colegio/{slug}/\n")
else:
    print("❌ NO se encontraron colegios que existan en ambas tablas")
    print("\nEsto significa que dim_colegios_slugs y fct_colegio_historico")
    print("fueron generados con fuentes de datos completamente diferentes.")

conn.close()
