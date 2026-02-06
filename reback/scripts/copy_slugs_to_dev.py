"""
Copiar tabla dim_colegios_slugs de prod_v2.duckdb a dev.duckdb
"""
import duckdb
from pathlib import Path

print("Copiando tabla dim_colegios_slugs de prod a dev...\n")

# Rutas
prod_db = Path(r"C:\proyectos\dbt\icfes_processing\prod_v2.duckdb")
dev_db = Path(r"C:\proyectos\dbt\icfes_processing\dev.duckdb")

# Conectar a prod (read-only)
print(f"1. Conectando a {prod_db.name}...")
conn_prod = duckdb.connect(str(prod_db), read_only=True)

# Leer datos de la tabla
print("2. Leyendo datos de gold.dim_colegios_slugs...")
data = conn_prod.execute("SELECT * FROM gold.dim_colegios_slugs").fetchdf()
print(f"   ✅ {len(data):,} registros leídos")

conn_prod.close()

# Conectar a dev (read-write)
print(f"\n3. Conectando a {dev_db.name}...")
conn_dev = duckdb.connect(str(dev_db), read_only=False)

# Crear esquema gold si no existe
print("4. Creando esquema gold...")
conn_dev.execute("CREATE SCHEMA IF NOT EXISTS gold")

# Eliminar tabla si existe
print("5. Eliminando tabla existente (si existe)...")
conn_dev.execute("DROP TABLE IF EXISTS gold.dim_colegios_slugs")

# Crear tabla con los datos
print("6. Creando tabla gold.dim_colegios_slugs...")
conn_dev.execute("""
    CREATE TABLE gold.dim_colegios_slugs AS 
    SELECT * FROM data
""")

# Crear índice
print("7. Creando índice en slug...")
conn_dev.execute("CREATE INDEX IF NOT EXISTS idx_slug ON gold.dim_colegios_slugs(slug)")

# Verificar
count = conn_dev.execute("SELECT COUNT(*) FROM gold.dim_colegios_slugs").fetchone()[0]
print(f"\n✅ Tabla copiada exitosamente: {count:,} registros")

# Mostrar ejemplos
print("\nEjemplos de slugs:")
samples = conn_dev.execute("""
    SELECT slug, nombre_colegio, municipio 
    FROM gold.dim_colegios_slugs 
    LIMIT 3
""").fetchall()

for slug, nombre, municipio in samples:
    print(f"  - {slug}")
    print(f"    {nombre} ({municipio})")

conn_dev.close()

print("\n" + "=" * 80)
print("✅ PROCESO COMPLETADO")
print("=" * 80)
print("\nAhora dev.duckdb tiene la tabla dim_colegios_slugs")
print("El servidor Django puede usar dev.duckdb en desarrollo local")
