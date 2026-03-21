# Railway — Infraestructura DuckDB

## Configuración de memoria (Railway)

| Recurso | Valor configurado |
|---------|------------------|
| RAM Railway | **5 GB** |
| DuckDB `memory_limit` | **3.5 GB** |
| DuckDB `threads` por conexión | 2 |
| Gunicorn workers | 2 |
| Gunicorn threads por worker | 4 |

### Reparto de los 5 GB

```
5 GB total
├── DuckDB buffer pool:  3.5 GB  ← caché de queries analíticas
├── Gunicorn 2 workers:  0.6 GB  ← Django + Python
├── OS + sistema:        0.2 GB
└── Headroom picos:      0.7 GB
```

> Si se aumenta la RAM de Railway, ajustar `memory_limit` en `icfes_dashboard/db_utils.py`
> proporcionalmente: `RAM_Railway - 1.5 GB = memory_limit para DuckDB`.

---

## Base de datos en S3

- **Ruta S3**: configurada en variable de entorno `DUCKDB_S3_PATH` (ej. `s3://bucket/prod_v2.duckdb`)
- **Ruta local en volumen**: `/app/data/prod.duckdb`
- **Tamaño aproximado**: ~3.5 GB

### Lógica de descarga (`db_utils._ensure_db_file`)

Al arrancar cada worker, la primera query que llega dispara `_ensure_db_file()`:

1. Si el archivo **no existe** o pesa **< 1 GB** → descarga desde S3 con `aws s3 cp`
2. Si el archivo **existe y pesa ≥ 1 GB** → usa el archivo del volumen sin descargar
3. Si `FORCE_DB_REDOWNLOAD=1` → descarga siempre, ignorando el tamaño

Los logs de la descarga aparecen como `WARNING [DuckDB] ...` para que sean visibles en Railway.

### Forzar actualización de la BD en Railway

Cuando se sube una nueva versión de `prod_v2.duckdb` a S3:

1. En Railway Dashboard → Variables → agregar `FORCE_DB_REDOWNLOAD=1`
2. Triggear un redeploy
3. Esperar los logs:
   ```
   WARNING [DuckDB] Downloading s3://...prod_v2.duckdb → /app/data/prod.duckdb ...
   WARNING [DuckDB] Download complete — 3.54 GB
   ```
4. Una vez activo, **borrar** la variable `FORCE_DB_REDOWNLOAD` para deploys futuros

> Sin el paso 4, cada restart del worker descargará la BD desde S3 innecesariamente.

---

## Conexiones DuckDB (thread-local)

Con `gunicorn --workers 2 --threads 4` hay **8 threads** en total.
Cada thread crea su propia conexión DuckDB al primer uso y la mantiene abierta
para toda la vida del worker (`_thread_local.conn`).

En modo `read_only`, DuckDB **comparte el buffer pool** entre todas las conexiones
al mismo archivo, por lo que el `memory_limit=3.5GB` aplica globalmente, no por conexión.

```python
# db_utils.py — parámetros clave
conn.execute("SET memory_limit='3.5GB'")
conn.execute("SET threads=2")
```

---

## Señales de alerta en Railway

| Síntoma | Causa probable | Acción |
|---------|---------------|--------|
| OOM / reinicios al arrancar | `memory_limit` muy alto para la RAM de Railway | Reducir `memory_limit` o aumentar RAM |
| BD sirve datos viejos | Volumen tiene el archivo viejo y no descargó | Activar `FORCE_DB_REDOWNLOAD=1` y redeploy |
| No aparece log `[DuckDB]` en arranque | El logger estaba en INFO (ya corregido a WARNING) | Verificar que el código actualizado esté deployado |
| Descarga lenta al arrancar (~3-4 min) | Normal — 3.5 GB desde S3 | Esperar; requests se encolan en el `_download_lock` |

---

## Historial de cambios relevantes

| Fecha | Commit | Cambio |
|-------|--------|--------|
| 2026-03-21 | `54e5d21` | Agrega `FORCE_DB_REDOWNLOAD` + logs como WARNING |
| 2026-03-21 | `d433426` | Agrega `memory_limit=1.5GB` (Railway 3GB) |
| 2026-03-21 | `39f2768` | Sube `memory_limit=3.5GB` para Railway 5GB |
