"""
Management command: export_campaign_prospects
Exporta prospectos potenciales desde DuckDB a CSV para revision manual.

Uso:
    python manage.py export_campaign_prospects --output c:/tmp/campana_2.csv
"""
import re
import math
from pathlib import Path

from django.core.management.base import BaseCommand

from icfes_dashboard.db_utils import execute_query


CIUDADES_DEFAULT = [
    "Cali", "Barranquilla", "Cartagena", "Bucaramanga",
    "Pereira", "Santa Marta", "Valledupar", "Villavicencio",
    "Soledad", "Soacha",
]

CSV_COLUMNS = [
    "nombre_colegio",
    "rector",
    "email",
    "telefono",
    "telefono_clean",
    "municipio",
    "departamento",
    "sector",
    "sector_label",
    "id_colegio",
    "slug",
    "avg_punt_global",
    "categoria_desempeno",
    "percentile_sector_estudiante",
    "percentile_departamental",
    "top_sector_pct",
    "mejora_historica_abs",
    "mejora_historica_pct",
    "mensaje_mejora",
    "rank_municipio",
    "segmento_email",
    "ranking_text",
    "subject_dinamico",
    "demo_url",
    "demo_url_utm",
    "cta_text",
]

BASE_URL = "https://www.icfes-analytics.com/icfes"
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"\d{7,}")


def _normalize_email(raw_value):
    txt = (raw_value or "").strip()
    if not txt:
        return ""
    matches = EMAIL_RE.findall(txt)
    if not matches:
        return ""
    return matches[0].lower()


def _clean_phone(raw_value):
    txt = (raw_value or "").strip()
    if not txt:
        return ""
    match = PHONE_RE.search(txt)
    return match.group(0) if match else ""


def _categoria_desempeno(score):
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "Sin dato"
    if score < 230:
        return "Sin Motivacion"
    if score < 260:
        return "Muy Baja"
    if score < 290:
        return "Baja"
    if score < 320:
        return "Media"
    if score < 350:
        return "Alta"
    return "Muy Alta"


def _sector_label(sector):
    txt = (sector or "").upper()
    if txt in ("NO_OFICIAL", "NO OFICIAL"):
        return "Privado"
    if txt in ("OFICIAL",):
        return "Publico"
    return "Publico"


def _mensaje_mejora(mejora):
    if mejora is None or (isinstance(mejora, float) and math.isnan(mejora)):
        return "Sin informacion historica suficiente."
    if mejora > 5:
        return "El colegio ha mejorado significativamente en los ultimos anos."
    if mejora > 0:
        return "El colegio muestra una mejora sostenida en su desempeno."
    if mejora < 0:
        return "El colegio presenta oportunidades de mejora academica."
    return "Sin informacion historica suficiente."


def _score_text(score):
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "N/A"
    score_rounded = round(float(score), 1)
    if abs(score_rounded - round(score_rounded)) < 0.01:
        return str(int(round(score_rounded)))
    return f"{score_rounded:.2f}".rstrip("0").rstrip(".")


def _short_school_name(name):
    raw = (name or "").strip()
    if not raw:
        return ""
    prefixes = [
        "COLEGIO ", "INST ", "INSTITUTO ", "I.E ", "I.E. ", "IE ",
        "COL ", "CENTRO EDUCATIVO ", "C.E. ", "CENT EDUC ",
    ]
    upper = raw.upper()
    cleaned = raw
    for prefix in prefixes:
        if upper.startswith(prefix):
            cleaned = raw[len(prefix):].strip()
            break
    return cleaned


def _segmento_email(rank):
    r = int(rank or 0)
    if r <= 3:
        return "top_colegios"
    if r <= 10:
        return "alto"
    if r <= 30:
        return "medio"
    return "mejora"


class Command(BaseCommand):
    help = "Extrae top N colegios desde DuckDB y los exporta a CSV para revision."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            required=True,
            help="Ruta absoluta del CSV de salida",
        )
        parser.add_argument(
            "--segmento", type=str, default="ciudad", choices=["ciudad", "departamento"],
            help="Segmentacion: ciudad o departamento"
        )
        parser.add_argument(
            "--ciudades", type=str,
            default=",".join(CIUDADES_DEFAULT),
            help="Ciudades separadas por coma (segmento=ciudad)"
        )
        parser.add_argument(
            "--departamentos", type=str, default="",
            help="Departamentos separados por coma (segmento=departamento)"
        )
        parser.add_argument(
            "--top", type=int, default=10,
            help="Top N colegios por segmento"
        )
        parser.add_argument(
            "--ano", type=int, default=2024,
            help="Ano de referencia para puntajes (segmento=ciudad)"
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"]).expanduser().resolve()
        segmento = options["segmento"]
        top_n = options["top"]
        ano = options["ano"]
        ciudades = [c.strip() for c in options["ciudades"].split(",") if c.strip()]
        departamentos = [d.strip() for d in options["departamentos"].split(",") if d.strip()]

        if top_n <= 0:
            self.stderr.write(self.style.ERROR("--top debe ser mayor que 0"))
            return

        if segmento == "ciudad" and not ciudades:
            self.stderr.write(self.style.ERROR("Debe indicar al menos una ciudad para segmento=ciudad"))
            return

        if segmento == "ciudad":
            placeholders = ", ".join(["?" for _ in ciudades])
            query = f"""
                WITH target_scores AS (
                    SELECT
                        f.colegio_bk,
                        f.avg_punt_global,
                        f.avg_percentile_sector_estudiante,
                        f.ranking_departamental_general,
                        f.count_colegios_departamento
                    FROM gold.fct_agg_colegios_ano f
                    WHERE f.ano = CAST(? AS VARCHAR)
                      AND f.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND f.avg_punt_global IS NOT NULL
                      AND f.avg_punt_global > 0
                ),
                prev_scores AS (
                    SELECT
                        f.colegio_bk,
                        f.avg_punt_global,
                        ROW_NUMBER() OVER (
                            PARTITION BY f.colegio_bk
                            ORDER BY CAST(f.ano AS INTEGER) DESC
                        ) AS rn
                    FROM gold.fct_agg_colegios_ano f
                    WHERE CAST(f.ano AS INTEGER) < CAST(? AS INTEGER)
                      AND f.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND f.avg_punt_global IS NOT NULL
                      AND f.avg_punt_global > 0
                ),
                score_base AS (
                    SELECT
                        ts.colegio_bk,
                        ts.avg_punt_global,
                        ts.avg_percentile_sector_estudiante,
                        ts.ranking_departamental_general,
                        ts.count_colegios_departamento,
                        ps.avg_punt_global AS avg_punt_global_prev
                    FROM target_scores ts
                    LEFT JOIN prev_scores ps
                        ON ps.colegio_bk = ts.colegio_bk
                       AND ps.rn = 1
                ),
                slug_one AS (
                    SELECT
                        codigo,
                        MIN(slug) AS slug
                    FROM gold.dim_colegios_slugs
                    GROUP BY codigo
                ),
                ranked AS (
                    SELECT
                        d.colegio_bk AS id_colegio,
                        d.nombre_colegio,
                        d.rector,
                        d.email,
                        d.telefono,
                        d.municipio,
                        d.departamento,
                        d.sector,
                        COALESCE(s.slug, '') AS slug,
                        sb.avg_punt_global,
                        sb.avg_percentile_sector_estudiante AS percentile_sector_estudiante,
                        CASE
                            WHEN sb.count_colegios_departamento > 1
                                 AND sb.ranking_departamental_general IS NOT NULL
                            THEN 100.0 * (
                                (sb.count_colegios_departamento - sb.ranking_departamental_general)::DOUBLE
                                / (sb.count_colegios_departamento - 1)::DOUBLE
                            )
                            ELSE NULL
                        END AS percentile_departamental,
                        (sb.avg_punt_global - sb.avg_punt_global_prev) AS mejora_historica_abs,
                        CASE
                            WHEN sb.avg_punt_global_prev > 0
                            THEN 100.0 * (sb.avg_punt_global - sb.avg_punt_global_prev) / sb.avg_punt_global_prev
                            ELSE NULL
                        END AS mejora_historica_pct,
                        ROW_NUMBER() OVER (
                            PARTITION BY d.departamento
                            ORDER BY sb.avg_punt_global DESC, d.nombre_colegio ASC
                        ) AS rank_departamento,
                        ROW_NUMBER() OVER (
                            PARTITION BY d.municipio
                            ORDER BY sb.avg_punt_global DESC, d.nombre_colegio ASC
                        ) AS rank_municipio
                    FROM score_base sb
                    INNER JOIN gold.dim_colegios d
                        ON d.colegio_bk = sb.colegio_bk
                    LEFT JOIN slug_one s
                        ON s.codigo = d.colegio_bk
                    WHERE d.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND d.municipio IN ({placeholders})
                      AND d.email IS NOT NULL
                      AND TRIM(d.email) != ''
                )
                SELECT *
                FROM ranked
                WHERE rank_municipio <= ?
                ORDER BY municipio, rank_municipio
            """
            params = [ano, ano] + ciudades + [top_n]
        else:
            dep_filter = ""
            dep_params = []
            if departamentos:
                dep_placeholders = ", ".join(["?" for _ in departamentos])
                dep_filter = f"AND d.departamento IN ({dep_placeholders})"
                dep_params = departamentos

            query = f"""
                WITH ult_puntaje AS (
                    SELECT
                        colegio_bk,
                        avg_punt_global,
                        avg_percentile_sector_estudiante,
                        ranking_departamental_general,
                        count_colegios_departamento,
                        LEAD(avg_punt_global) OVER (
                            PARTITION BY colegio_bk
                            ORDER BY CAST(ano AS INTEGER) DESC
                        ) AS avg_punt_global_prev,
                        ROW_NUMBER() OVER (
                            PARTITION BY colegio_bk
                            ORDER BY CAST(ano AS INTEGER) DESC
                        ) AS rn
                    FROM gold.fct_agg_colegios_ano
                    WHERE sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND avg_punt_global IS NOT NULL
                      AND avg_punt_global > 0
                ),
                score_base AS (
                    SELECT
                        colegio_bk,
                        avg_punt_global,
                        avg_percentile_sector_estudiante,
                        ranking_departamental_general,
                        count_colegios_departamento,
                        avg_punt_global_prev
                    FROM ult_puntaje
                    WHERE rn = 1
                ),
                slug_one AS (
                    SELECT
                        codigo,
                        MIN(slug) AS slug
                    FROM gold.dim_colegios_slugs
                    GROUP BY codigo
                ),
                ranked AS (
                    SELECT
                        d.colegio_bk AS id_colegio,
                        d.nombre_colegio,
                        d.rector,
                        d.email,
                        d.telefono,
                        d.municipio,
                        d.departamento,
                        d.sector,
                        COALESCE(s.slug, '') AS slug,
                        sb.avg_punt_global,
                        sb.avg_percentile_sector_estudiante AS percentile_sector_estudiante,
                        CASE
                            WHEN sb.count_colegios_departamento > 1
                                 AND sb.ranking_departamental_general IS NOT NULL
                            THEN 100.0 * (
                                (sb.count_colegios_departamento - sb.ranking_departamental_general)::DOUBLE
                                / (sb.count_colegios_departamento - 1)::DOUBLE
                            )
                            ELSE NULL
                        END AS percentile_departamental,
                        (sb.avg_punt_global - sb.avg_punt_global_prev) AS mejora_historica_abs,
                        CASE
                            WHEN sb.avg_punt_global_prev > 0
                            THEN 100.0 * (sb.avg_punt_global - sb.avg_punt_global_prev) / sb.avg_punt_global_prev
                            ELSE NULL
                        END AS mejora_historica_pct,
                        ROW_NUMBER() OVER (
                            PARTITION BY d.departamento
                            ORDER BY sb.avg_punt_global DESC, d.nombre_colegio ASC
                        ) AS rank_departamento,
                        ROW_NUMBER() OVER (
                            PARTITION BY d.municipio
                            ORDER BY sb.avg_punt_global DESC, d.nombre_colegio ASC
                        ) AS rank_municipio
                    FROM score_base sb
                    INNER JOIN gold.dim_colegios d
                        ON d.colegio_bk = sb.colegio_bk
                    LEFT JOIN slug_one s
                        ON s.codigo = d.colegio_bk
                    WHERE d.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND d.email IS NOT NULL
                      AND TRIM(d.email) != ''
                      {dep_filter}
                )
                SELECT *
                FROM ranked
                WHERE rank_departamento <= ?
                ORDER BY departamento, rank_departamento, municipio
            """
            params = dep_params + [top_n]

        self.stdout.write("Consultando DuckDB...", ending=" ")
        df = execute_query(query, params=params)
        if df.empty:
            self.stderr.write(self.style.WARNING("No se encontraron prospectos para los filtros dados."))
            return
        self.stdout.write(self.style.SUCCESS(f"OK ({len(df)} filas)"))

        # Completa columnas operativas esperadas por el import posterior.
        df["email"] = df["email"].apply(_normalize_email)
        df = df[df["email"] != ""].copy()
        if df.empty:
            self.stderr.write(self.style.WARNING("No quedaron filas con email valido tras limpieza."))
            return
        df["slug"] = df["slug"].fillna("")
        df["demo_url"] = df["slug"].apply(lambda slug: f"{BASE_URL}/colegio/{slug}/" if slug else BASE_URL)
        df["avg_punt_global_num"] = df["avg_punt_global"].fillna(0).astype(float).round(1)
        df["percentile_sector_estudiante"] = df["percentile_sector_estudiante"].astype(float)
        df.loc[
            df["percentile_sector_estudiante"].notna() & (df["percentile_sector_estudiante"] <= 1.0),
            "percentile_sector_estudiante"
        ] = df["percentile_sector_estudiante"] * 100.0
        df["percentile_sector_estudiante"] = df["percentile_sector_estudiante"].round(0).astype("Int64")
        df["percentile_departamental"] = df["percentile_departamental"].astype(float).round(0).astype("Int64")
        df["top_sector_pct"] = (100 - df["percentile_sector_estudiante"]).astype("Int64")
        df["mejora_historica_abs"] = df["mejora_historica_abs"].astype(float).round(2)
        df["mejora_historica_pct"] = df["mejora_historica_pct"].astype(float).round(2)
        df["rank_municipio"] = df["rank_municipio"].fillna(0).astype(int)
        df["telefono_clean"] = df["telefono"].apply(_clean_phone)
        df["sector_label"] = df["sector"].apply(_sector_label)
        df["categoria_desempeno"] = df["avg_punt_global_num"].apply(_categoria_desempeno)
        df["mensaje_mejora"] = df["mejora_historica_abs"].apply(_mensaje_mejora)
        df["segmento_email"] = df["rank_municipio"].apply(_segmento_email)
        df["ranking_text"] = df.apply(
            lambda row: f"Ocupa el puesto #{int(row['rank_municipio'])} en {row['municipio']}",
            axis=1,
        )
        df["avg_punt_global"] = df["avg_punt_global_num"].apply(_score_text)
        df["subject_dinamico"] = df.apply(
            lambda row: (
                f"{_short_school_name(row['nombre_colegio'])}: #{int(row['rank_municipio'])} en "
                f"{row['municipio']} - ICFES {row['avg_punt_global']}"
            ),
            axis=1,
        )
        df["cta_text"] = "Ver analisis completo del colegio"
        df["demo_url_utm"] = df["demo_url"].apply(
            lambda url: f"{url}?utm_source=email&utm_campaign=rectores_icfes&utm_medium=brevo"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df[CSV_COLUMNS].to_csv(output_path, index=False, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"CSV generado: {output_path}"))
