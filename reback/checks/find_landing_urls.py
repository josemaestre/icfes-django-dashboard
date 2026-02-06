import duckdb

conn = duckdb.connect(r'C:\proyectos\dbt\icfes_processing\dev.duckdb', read_only=True)

# Buscar algunos colegios populares
query = """
SELECT 
    nombre_colegio,
    municipio,
    slug
FROM gold.dim_colegios_slugs
WHERE nombre_colegio LIKE '%GIMNASIO%'
   OR nombre_colegio LIKE '%LICEO%'
   OR nombre_colegio LIKE '%SAN JOSE%'
LIMIT 10
"""

results = conn.execute(query).fetchall()

print("Ejemplos de URLs de Landing Pages:\n")
print("=" * 80)

for nombre, municipio, slug in results:
    url = f"http://127.0.0.1:8000/icfes/colegio/{slug}/"
    print(f"\n{nombre[:60]}")
    print(f"  📍 {municipio}")
    print(f"  🔗 {url}")

conn.close()
