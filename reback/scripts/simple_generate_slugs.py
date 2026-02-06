"""
Script SIMPLE para generar slugs - sin dependencias complejas.

Ejecutar: python simple_generate_slugs.py
"""
import duckdb
import re
from pathlib import Path

def slugify(text):
    """Convertir texto a slug SEO-friendly."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

def generate_slug(nombre, municipio):
    """Generar slug unico."""
    combined = f"{nombre} {municipio}"
    return slugify(combined)

# Conectar a DuckDB
db_path = Path("C:/proyectos/dbt/icfes_processing/prod_v2.duckdb")
print(f"Conectando a: {db_path}")

if not db_path.exists():
    print(f"ERROR: No se encontro {db_path}")
    print("   Verifica que prod_v2.duckdb este en el directorio correcto")
    exit(1)

conn = duckdb.connect(str(db_path))

# Obtener colegios
print("Obteniendo colegios...")
query = """
    SELECT DISTINCT
        colegio_bk as codigo,
        nombre_colegio,
        municipio,
        departamento,
        sector,
        'COMPLETA' as jornada,
        'URBANO' as area
    FROM dim_colegios
    ORDER BY nombre_colegio
"""

schools = conn.execute(query).fetchdf()
total = len(schools)
print(f"OK - Encontrados {total} colegios")

# Generar slugs
print("Generando slugs...")
slugs_data = []
slug_counts = {}

for idx, row in schools.iterrows():
    slug = generate_slug(row['nombre_colegio'], row['municipio'])
    
    # Manejar duplicados
    if slug in slug_counts:
        slug = f"{slug}-{row['codigo']}"
    slug_counts[slug] = 1
    
    slugs_data.append((
        row['codigo'],
        row['nombre_colegio'],
        row['municipio'],
        row['departamento'],
        row['sector'],
        row['jornada'],
        row['area'],
        slug
    ))
    
    if (idx + 1) % 1000 == 0:
        print(f"  Procesados {idx + 1}/{total}...")

print(f"OK - Generados {len(slugs_data)} slugs unicos")

# Mostrar ejemplos
print("\nEjemplos:")
for i in range(min(5, len(slugs_data))):
    print(f"  {slugs_data[i][7]} -> {slugs_data[i][1]}")

# Crear tabla en el esquema gold
print("\nCreando tabla gold.dim_colegios_slugs...")
conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
conn.execute("DROP TABLE IF EXISTS gold.dim_colegios_slugs")

conn.execute("""
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
""")

# Insertar datos
print("Insertando datos...")
conn.executemany(
    """INSERT INTO gold.dim_colegios_slugs 
       (codigo, nombre_colegio, municipio, departamento, sector, jornada, area, slug)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    slugs_data
)

# Crear indice
conn.execute("CREATE INDEX idx_slug ON gold.dim_colegios_slugs(slug)")

# Verificar
count = conn.execute("SELECT COUNT(*) FROM gold.dim_colegios_slugs").fetchone()[0]
print(f"\nOK - Tabla creada con {count} registros")

# Mostrar URLs de ejemplo
print("\nURLs de ejemplo:")
samples = conn.execute("""
    SELECT slug, nombre_colegio, municipio 
    FROM gold.dim_colegios_slugs 
    LIMIT 5
""").fetchall()

for slug, nombre, municipio in samples:
    print(f"  /icfes/colegio/{slug}/")
    print(f"    -> {nombre} ({municipio})")

print("\nCOMPLETADO!")
conn.close()
