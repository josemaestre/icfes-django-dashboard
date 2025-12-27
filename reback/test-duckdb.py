import duckdb

# Conectar a tu base
con = duckdb.connect('icfes_2010-2023.duckdb')

# Ver las tablas existentes
print("Tablas disponibles:")
print(con.sql("SHOW TABLES").df())

# Contar registros en v_icfes
print("\nConteo de registros:")
print(con.sql("SELECT COUNT(*) FROM v_icfes").df())

# Ver muestra
print("\nEjemplo de registros:")
print(con.sql("SELECT * FROM v_icfes LIMIT 5").df())
