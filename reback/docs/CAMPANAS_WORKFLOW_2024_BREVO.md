# Workflow de Campañas ICFES (2024 + Brevo)

## Objetivo
Estandarizar el proceso de campañas B2B para colegios usando:
- score ICFES base del año 2024,
- contactos por colegio (`colegio_bk`) con fallback histórico,
- CSV enriquecido para Brevo,
- gráfica dinámica por slug en el email.

---

## Flujo operativo (resumen)
1. Extraer candidatos desde DuckDB con `export_campaign_prospects`.
2. Forzar base de score por año (`--ano 2024`).
3. Enriquecer contacto por colegio:
   - primero `gold.dim_colegios` (actual),
   - fallback a `gold.dim_colegios_ano` (último email no vacío).
4. Exportar CSV para revisión manual.
5. Cargar en Brevo y usar plantilla HTML con personalización por contacto.

---

## Comando oficial de generación (campaña 2024)
```bash
cd C:\proyectos\www\reback
python manage.py export_campaign_prospects \
  --output c:/proyectos/tmp/campana_base_2024_fallback_email.csv \
  --segmento departamento \
  --top 20 \
  --ano 2024
```

Notas:
- `ano_icfes` debe salir en `2024` para todas las filas.
- `avg_punt_global` se exporta como entero (sin decimales).

---

## Validaciones rápidas (post-export)
### 1) Verificar año base único
```bash
python - <<'PY'
import pandas as pd
df = pd.read_csv(r"c:/proyectos/tmp/campana_base_2024_fallback_email.csv")
print("filas:", len(df))
print("anos_unicos:", sorted(df["ano_icfes"].dropna().unique().tolist()))
print("no_2024:", int((df["ano_icfes"] != 2024).sum()))
PY
```

### 2) Verificar emails vacíos
```bash
python - <<'PY'
import pandas as pd
df = pd.read_csv(r"c:/proyectos/tmp/campana_base_2024_fallback_email.csv")
s = df["email"].fillna("").str.strip()
print("emails_vacios:", int((s == "").sum()))
PY
```

---

## Campos clave del CSV para Brevo
- `NOMBRE_COLEGIO`
- `RECTOR`
- `EMAIL`
- `MUNICIPIO`
- `DEPARTAMENTO`
- `SECTOR_LABEL`
- `SLUG`
- `ANO_ICFES`
- `AVG_PUNT_GLOBAL`
- `CATEGORIA_DESEMPENO`
- `TOP_SECTOR_PCT`
- `MENSAJE_MEJORA`
- `RANKING_TEXT`
- `SUBJECT_DINAMICO`
- `DEMO_URL_UTM`
- `CTA_TEXT`

---

## Plantilla Brevo (HTML) - guía de uso
Tu plantilla actual es correcta en estructura. Mantener:
- subject por contacto: `{{ contact.SUBJECT_DINAMICO }}`
- URL del reporte: `{{ contact.DEMO_URL_UTM }}`
- gráfica dinámica:
  - `https://www.icfes-analytics.com/email-graphs/{{ contact.SLUG }}.png?years=5`

### Variables que deben quedar exactas (evitar typos)
- `{{ contact.CATEGORIA_DESEMPENO }}` (no `CATEGORIA_DESE`)
- `{{ contact.SECTOR_LABEL }}` (no `SECTOR_LEBEL`)

---

## Endpoint de gráfica dinámica
Formato:
```text
https://www.icfes-analytics.com/email-graphs/<slug>.png?years=5
```

Ejemplo:
```text
https://www.icfes-analytics.com/email-graphs/colegio-corazonista-medellin.png?years=5
```

---

## Razón del fallback de contacto
En la capa analítica, los scores 2024 existen; el gap estaba en cobertura de email en `dim_colegios` para años recientes.
Por eso se usa fallback de contacto histórico por `colegio_bk` desde `dim_colegios_ano`, sin cambiar el año base del score (2024).

---

## Troubleshooting
### "No se encontraron prospectos para los filtros dados"
Revisar:
- `--ano` demasiado restrictivo para el segmento/filtro elegido.
- apertura de `dev.duckdb` por otro proceso (ej: DBeaver).

### `dev.duckdb` bloqueado en Windows
Cerrar clientes que tengan el archivo abierto y volver a correr el comando.

---

## Estado actual del proceso
- Score base: 2024
- Contacto: por colegio con fallback histórico
- Puntaje global en CSV: entero
- CSV listo para personalización en Brevo
- Gráfica personalizada en email: on-the-fly por slug
