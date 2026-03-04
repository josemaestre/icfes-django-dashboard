"""
Management command: import_campaign_prospects_from_csv
Importa un CSV previamente exportado y crea Campaign + CampaignProspect en Postgres.
"""
import csv
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand

from icfes_dashboard.models import Campaign, CampaignProspect


BASE_URL = "https://www.icfes-analytics.com/icfes"

REQUIRED_COLUMNS = [
    "nombre_colegio",
    "email",
    "municipio",
    "departamento",
]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _to_int(value, default=0):
    if value is None:
        return default
    txt = str(value).strip()
    if not txt:
        return default
    try:
        return int(float(txt))
    except (ValueError, TypeError):
        return default


def _to_float(value, default=0.0):
    if value is None:
        return default
    txt = str(value).strip()
    if not txt:
        return default
    try:
        return float(txt)
    except (ValueError, TypeError):
        return default


def _normalize_email(raw_value):
    txt = (raw_value or "").strip()
    if not txt:
        return ""
    matches = EMAIL_RE.findall(txt)
    if not matches:
        return ""
    return matches[0].lower()


def _canon_col(name):
    txt = (name or "").strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = txt.replace(" ", "_")
    return txt


class Command(BaseCommand):
    help = "Importa prospectos desde CSV a Campaign/CampaignProspect."

    def add_arguments(self, parser):
        parser.add_argument("--input", type=str, required=True, help="Ruta del CSV de entrada")
        parser.add_argument("--nombre", type=str, required=True, help="Nombre de la campana")
        parser.add_argument("--lote", type=int, default=1, help="Numero de lote")
        parser.add_argument("--descripcion", type=str, default="", help="Descripcion opcional")
        parser.add_argument("--email-remitente", type=str, default="icfes@sabededatos.com")
        parser.add_argument("--nombre-remitente", type=str, default="Jose Maestre")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valida CSV y muestra resumen, pero no inserta en Postgres",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["input"]).expanduser().resolve()
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"No existe el archivo: {csv_path}"))
            return

        rows = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
            canonical_map = {_canon_col(h): h for h in headers}
            missing = [col for col in REQUIRED_COLUMNS if col not in canonical_map]
            if missing:
                self.stderr.write(
                    self.style.ERROR(
                        f"CSV invalido. Faltan columnas requeridas: {', '.join(missing)}"
                    )
                )
                return
            for row in reader:
                normalized_row = {}
                for col in REQUIRED_COLUMNS:
                    original = canonical_map.get(col)
                    normalized_row[col] = (row.get(original) or "").strip()

                # Campos opcionales usados por el import
                for optional_col in [
                    "rector",
                    "telefono",
                    "slug",
                    "demo_url",
                    "avg_punt_global",
                    "rank_municipio",
                ]:
                    original = canonical_map.get(optional_col)
                    normalized_row[optional_col] = (row.get(original) or "").strip() if original else ""

                rows.append(normalized_row)

        if not rows:
            self.stderr.write(self.style.WARNING("El CSV no tiene filas para importar."))
            return

        emails = set()
        duplicate_emails = 0
        invalid_emails = 0
        for row in rows:
            email = _normalize_email(row.get("email"))
            if not email:
                invalid_emails += 1
                continue
            if email in emails:
                duplicate_emails += 1
            emails.add(email)

        self.stdout.write(f"Archivo: {csv_path}")
        self.stdout.write(f"Filas totales: {len(rows)}")
        self.stdout.write(f"Emails duplicados en archivo: {duplicate_emails}")
        self.stdout.write(f"Filas con email invalido: {invalid_emails}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN: no se inserto nada."))
            return

        campaign = Campaign.objects.create(
            nombre=options["nombre"],
            lote=options["lote"],
            estado="borrador",
            descripcion=options["descripcion"] or f"Importada desde CSV: {csv_path.name}",
            email_remitente=options["email_remitente"],
            nombre_remitente=options["nombre_remitente"],
            ciudades_objetivo="Importada desde CSV",
            top_n_por_ciudad=0,
        )

        prospectos = []
        for row in rows:
            email = _normalize_email(row.get("email"))
            if not email:
                continue

            slug = (row.get("slug") or "").strip()
            demo_url = (row.get("demo_url") or "").strip()
            if not demo_url:
                demo_url = f"{BASE_URL}/colegio/{slug}/" if slug else BASE_URL

            prospectos.append(
                CampaignProspect(
                    campaign=campaign,
                    nombre_colegio=(row.get("nombre_colegio") or "").strip(),
                    rector=(row.get("rector") or "").strip(),
                    email=email,
                    telefono=(row.get("telefono") or "").strip(),
                    municipio=(row.get("municipio") or "").strip(),
                    departamento=(row.get("departamento") or "").strip(),
                    slug=slug,
                    avg_punt_global=round(_to_float(row.get("avg_punt_global"), default=0.0), 2),
                    rank_municipio=_to_int(row.get("rank_municipio"), default=0),
                    demo_url=demo_url,
                    estado="pendiente",
                )
            )

        try:
            created = CampaignProspect.objects.bulk_create(
                prospectos,
                ignore_conflicts=True,  # unique_together(campaign, email)
            )
        except Exception as exc:
            campaign.delete()
            self.stderr.write(self.style.ERROR(f"Error insertando prospectos: {exc}"))
            return

        skipped = len(prospectos) - len(created)
        self.stdout.write(self.style.SUCCESS(f"Campana creada: ID={campaign.pk}"))
        self.stdout.write(self.style.SUCCESS(f"Prospectos insertados: {len(created)}"))
        if skipped > 0:
            self.stdout.write(self.style.WARNING(f"Prospectos omitidos por conflicto: {skipped}"))
