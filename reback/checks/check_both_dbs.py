"""
Verificar qué base de datos tiene la tabla dim_colegios_slugs
"""
import duckdb
from pathlib import Path

base_path = Path(r"C:\proyectos\dbt\icfes_processing")

databases = {
    'dev.duckdb': base_path / 'dev.duckdb',
    'prod_v2.duckdb': base_path / 'prod_v2.duckdb'
}

print("Verificando tabla dim_colegios_slugs en ambas bases de datos...\n")
print("=" * 80)

for db_name, db_path in databases.items():
    print(f"\n📁 {db_name}")
    
    if not db_path.exists():
        print(f"   ❌ Archivo no existe")
        continue
    
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        
        # Buscar tabla
        result = conn.execute("""
            SELECT table_schema, COUNT(*) as count
            FROM information_schema.tables
            WHERE table_name = 'dim_colegios_slugs'
            GROUP BY table_schema
        """).fetchall()
        
        if result:
            for schema, count in result:
                # Contar registros
                records = conn.execute(f"SELECT COUNT(*) FROM {schema}.dim_colegios_slugs").fetchone()[0]
                print(f"   ✅ {schema}.dim_colegios_slugs - {records:,} registros")
        else:
            print(f"   ❌ Tabla dim_colegios_slugs NO existe")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 80)
print("\nRecomendación:")
print("Si dev.duckdb NO tiene la tabla, debes usar prod_v2.duckdb para desarrollo local")
print("o copiar la tabla de prod_v2 a dev")
