"""
Management command: generate_campaign_email_graphs

Genera un PNG por colegio (slug) para uso en emails, con evolucion de
puntaje global en los ultimos N anos.

DEPRECATED:
Usar endpoint dinamico:
  /email-graphs/<slug>.png?years=4
"""
from __future__ import annotations

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from icfes_dashboard.db_utils import execute_query


def _safe_slug(value: str) -> str:
    txt = (value or "").strip().lower()
    return "".join(ch for ch in txt if ch.isalnum() or ch in ("-", "_"))


class Command(BaseCommand):
    help = (
        "[DEPRECATED] Genera graficas PNG por colegio para emails (ultimos N anos). "
        "Preferir /email-graphs/<slug>.png?years=4"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input-csv",
            required=True,
            type=str,
            help="Ruta del CSV de campana que contiene columna 'slug'",
        )
        parser.add_argument(
            "--years",
            type=int,
            default=4,
            help="Cuantos anos historicos incluir (default: 4)",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default="",
            help="Directorio de salida para PNG (default: <repo>/reback/static/email_graphs)",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Sobrescribe PNG existentes",
        )
        parser.add_argument(
            "--min-points",
            type=int,
            default=2,
            help="Minimo de puntos historicos para dibujar grafica (default: 2)",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "DEPRECATED: Este comando sera retirado. "
                "Usa /email-graphs/<slug>.png?years=4."
            )
        )
        input_csv = Path(options["input_csv"]).expanduser().resolve()
        years = max(1, int(options["years"]))
        min_points = max(1, int(options["min_points"]))
        overwrite = bool(options["overwrite"])

        if not input_csv.exists():
            self.stderr.write(self.style.ERROR(f"No existe input CSV: {input_csv}"))
            return

        if options["output_dir"]:
            output_dir = Path(options["output_dir"]).expanduser().resolve()
        else:
            output_dir = Path(settings.BASE_DIR) / "reback" / "static" / "email_graphs"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1) Slugs desde CSV de campana
        slugs = []
        with input_csv.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if "slug" not in (reader.fieldnames or []):
                self.stderr.write(self.style.ERROR("El CSV no tiene columna 'slug'."))
                return
            for row in reader:
                slug = _safe_slug(row.get("slug", ""))
                if slug:
                    slugs.append(slug)

        slugs = sorted(set(slugs))
        if not slugs:
            self.stderr.write(self.style.WARNING("No hay slugs validos en el CSV."))
            return

        self.stdout.write(f"Slugs unicos en campana: {len(slugs)}")
        self.stdout.write(f"Salida PNG: {output_dir}")

        # 2) Historial desde DuckDB (solo slugs en campana)
        placeholders = ", ".join(["?" for _ in slugs])
        query = f"""
            WITH hist AS (
                SELECT
                    s.slug,
                    CAST(f.ano AS INTEGER) AS ano,
                    f.avg_punt_global,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.slug
                        ORDER BY CAST(f.ano AS INTEGER) DESC
                    ) AS rn
                FROM gold.fct_agg_colegios_ano f
                INNER JOIN gold.dim_colegios_slugs s
                    ON s.codigo = f.colegio_bk
                WHERE s.slug IN ({placeholders})
                  AND f.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                  AND f.avg_punt_global IS NOT NULL
                  AND f.avg_punt_global > 0
            )
            SELECT slug, ano, avg_punt_global
            FROM hist
            WHERE rn <= ?
            ORDER BY slug, ano
        """
        params = slugs + [years]
        df = execute_query(query, params=params)
        if df.empty:
            self.stderr.write(self.style.WARNING("No se encontro historia para los slugs dados."))
            return

        # 3) Render PNG por slug
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        generated = 0
        skipped = 0
        for slug, grp in df.groupby("slug"):
            grp = grp.sort_values("ano")
            if len(grp) < min_points:
                skipped += 1
                continue

            out_path = output_dir / f"{slug}.png"
            if out_path.exists() and not overwrite:
                skipped += 1
                continue

            years_arr = grp["ano"].astype(int).tolist()
            scores_arr = grp["avg_punt_global"].astype(float).tolist()

            fig, ax = plt.subplots(figsize=(7.2, 2.8))  # ~560 px ancho a 78 dpi
            ax.plot(years_arr, scores_arr, marker="o", linewidth=2.0)
            ax.set_title("Evolucion del puntaje global (SABER 11)")
            ax.set_xlabel("Ano")
            ax.set_ylabel("Puntaje")
            ax.grid(alpha=0.25)

            ymin = max(0, min(scores_arr) - 15)
            ymax = max(scores_arr) + 15
            ax.set_ylim(ymin, ymax)

            fig.tight_layout()
            fig.savefig(out_path, dpi=120)
            plt.close(fig)
            generated += 1

        self.stdout.write(self.style.SUCCESS(f"PNG generados: {generated}"))
        self.stdout.write(self.style.WARNING(f"Slugs omitidos: {skipped}"))
        self.stdout.write(
            "Tip: En email usa <img src='https://TU_DOMINIO/static/email_graphs/<slug>.png'>"
        )
