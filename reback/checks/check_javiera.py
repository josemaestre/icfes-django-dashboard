import duckdb

conn = duckdb.connect(r'C:\proyectos\dbt\icfes_processing\dev.duckdb', read_only=True)

codes = ['105001000876', '105001001562']

print("Verificando datos de JAVIERA LONDOÑO:\n")

for code in codes:
    count = conn.execute(
        f"SELECT COUNT(*) FROM gold.fct_colegio_historico WHERE codigo_dane = '{code}' AND ano = '2024'"
    ).fetchone()[0]
    
    slug_result = conn.execute(
        f"SELECT slug, nombre_colegio FROM gold.dim_colegios_slugs WHERE codigo = '{code}'"
    ).fetchone()
    
    if slug_result:
        slug, nombre = slug_result
        print(f"Codigo: {code}")
        print(f"Nombre: {nombre}")
        print(f"Slug: {slug}")
        print(f"Registros 2024: {count}")
        print(f"URL: http://127.0.0.1:8000/icfes/colegio/{slug}/")
        print()

conn.close()
