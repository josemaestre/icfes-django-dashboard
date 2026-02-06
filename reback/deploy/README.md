# Proceso de Deploy - Dev a Prod

Este directorio contiene los scripts necesarios para el proceso de deploy de la base de datos desde el ambiente de desarrollo (`dev.duckdb`) al ambiente de producción (`prod_v2.duckdb`).

## Orden de Ejecución

1. **`01_generate_slugs.py`** - Genera slugs para todos los colegios
2. **`02_sync_gold_to_prod.py`** - Copia todas las tablas gold de dev a prod
3. **`03_verify_deployment.py`** - Verifica que el deploy fue exitoso

## Uso

```bash
# Ejecutar todo el proceso de deploy
python deploy/01_generate_slugs.py
python deploy/02_sync_gold_to_prod.py
python deploy/03_verify_deployment.py
```

## Notas

- Los scripts deben ejecutarse en orden
- Cada script valida que el anterior se haya ejecutado correctamente
- Se crean backups automáticos antes de modificar prod
