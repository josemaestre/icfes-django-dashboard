"""
Verificar solo las tablas necesarias para landing page
"""
import duckdb

DB_PATH = r"C:\proyectos\dbt\icfes_processing\dev.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

print("Verificando tablas necesarias en dev.duckdb:\n")

tables_to_check = [
    ('gold', 'dim_colegios_slugs'),
    ('gold', 'fct_colegio_historico'),
    ('gold', 'fct_colegio_comparacion_contexto'),
    ('gold', 'dim_colegios_cluster'),
]

all_exist = True

for schema, table in tables_to_check:
    full_name = f"{schema}.{table}"
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {full_name}").fetchone()[0]
        print(f"✅ {full_name:50} {count:>10,} registros")
    except Exception as e:
        print(f"❌ {full_name:50} NO EXISTE")
        all_exist = False

conn.close()

print("\n" + "=" * 70)
if all_exist:
    print("✅ TODAS LAS TABLAS EXISTEN")
    print("\nEl problema debe ser otro. Revisando logs del servidor...")
else:
    print("❌ FALTAN TABLAS")
    print("\nNecesitas ejecutar dbt para generar las tablas faltantes")
