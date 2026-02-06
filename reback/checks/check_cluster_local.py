
import duckdb
import os

try:
    print("Checking DEV DB...")
    con = duckdb.connect(r'c:/proyectos/dbt/icfes_processing/dev.duckdb', read_only=True)
    res = con.execute("SELECT * FROM information_schema.tables WHERE table_name = 'dim_colegios_cluster'").fetchall()
    print("DEV DB dim_colegios_cluster:", res)
    con.close()
except Exception as e:
    print("Error checking DEV DB:", e)

try:
    print("Checking PROD_V2 DB...")
    con2 = duckdb.connect(r'c:/proyectos/dbt/icfes_processing/prod_v2.duckdb', read_only=True)
    res2 = con2.execute("SELECT * FROM information_schema.tables WHERE table_name = 'dim_colegios_cluster'").fetchall()
    print("PROD_V2 DB dim_colegios_cluster:", res2)
    con2.close()
except Exception as e:
    print("Error checking PROD_V2 DB:", e)
