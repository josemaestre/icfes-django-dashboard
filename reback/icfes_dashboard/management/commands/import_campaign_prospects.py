"""
Management command: import_campaign_prospects
Importa los top N colegios privados por ciudad desde DuckDB → Postgres (Campaign + CampaignProspect).

Uso básico:
    python manage.py import_campaign_prospects

Con opciones:
    python manage.py import_campaign_prospects \\
        --nombre "Campaña #1 - Top Privados Ciudades Principales" \\
        --lote 1 \\
        --ciudades "Bogotá,Medellín,Cali,Barranquilla,Bucaramanga,Cartagena,Manizales,Pereira" \\
        --top 10 \\
        --ano 2024

El comando:
1. Crea un registro Campaign en Postgres (estado=borrador)
2. Consulta DuckDB (read-only) para obtener los top N privados por ciudad
3. Inserta CampaignProspect por cada colegio encontrado
4. Muestra resumen con pipeline por ciudad
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from icfes_dashboard.models import Campaign, CampaignProspect
from icfes_dashboard.db_utils import execute_query


CIUDADES_DEFAULT = [
    # Ciudades con datos en gold layer (Bogotá y Medellín ausentes — gap de pipeline)
    'Cali', 'Barranquilla', 'Cartagena', 'Bucaramanga',
    'Pereira', 'Santa Marta', 'Valledupar', 'Villavicencio',
    'Soledad', 'Soacha',
]

BASE_URL = 'https://www.icfes-analytics.com/icfes'


class Command(BaseCommand):
    help = 'Importa top N colegios privados por ciudad desde DuckDB a una Campaign en Postgres.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--nombre', type=str,
            default='Campaña #1 — Top Privados Ciudades Principales',
            help='Nombre de la campaña'
        )
        parser.add_argument(
            '--lote', type=int, default=1,
            help='Número de lote (1, 2, 3...)'
        )
        parser.add_argument(
            '--ciudades', type=str,
            default=','.join(CIUDADES_DEFAULT),
            help='Ciudades separadas por coma'
        )
        parser.add_argument(
            '--top', type=int, default=10,
            help='Top N colegios por ciudad'
        )
        parser.add_argument(
            '--ano', type=int, default=2024,
            help='Año de referencia para puntajes (default: 2024)'
        )
        parser.add_argument(
            '--email-remitente', type=str, default='icfes@sabededatos.com',
        )
        parser.add_argument(
            '--nombre-remitente', type=str, default='Jose Maestre',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra los resultados, no inserta en BD'
        )

    def handle(self, *args, **options):
        ciudades = [c.strip() for c in options['ciudades'].split(',') if c.strip()]
        top_n    = options['top']
        ano      = options['ano']
        dry_run  = options['dry_run']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'='*60}\n  IMPORTAR PROSPECTOS DE CAMPAÑA\n{'='*60}"
        ))
        self.stdout.write(f"  Ciudades   : {', '.join(ciudades)}")
        self.stdout.write(f"  Top N      : {top_n} por ciudad")
        self.stdout.write(f"  Año        : {ano}")
        self.stdout.write(f"  Dry run    : {'SÍ' if dry_run else 'NO'}")
        self.stdout.write("")

        # ── 1. Query DuckDB ────────────────────────────────────────────
        placeholders = ', '.join(['?' for _ in ciudades])

        # Join via colegio_sk (MD5 hash) para obtener puntajes reales de fct_agg_colegios_ano.
        # Filtra colegios sin datos ICFES (avg_punt_global = 0 o NULL).
        # Ordena por puntaje DESC — los mejores colegios privados de cada ciudad primero.
        # sector usa IN para compatibilidad con dev ('NO OFICIAL') y prod ('NO_OFICIAL').
        query = f"""
            WITH ranked AS (
                SELECT
                    d.nombre_colegio,
                    d.rector,
                    d.email,
                    d.telefono,
                    d.municipio,
                    d.departamento,
                    COALESCE(s.slug, '') AS slug,
                    f.avg_punt_global,
                    ROW_NUMBER() OVER (
                        PARTITION BY d.municipio
                        ORDER BY f.avg_punt_global DESC
                    ) AS rank_municipio
                FROM gold.dim_colegios d
                JOIN gold.fct_agg_colegios_ano f
                    ON f.colegio_sk = d.colegio_sk
                    AND f.ano = CAST(? AS VARCHAR)
                    AND f.sector = 'NO OFICIAL'
                LEFT JOIN gold.dim_colegios_slugs s
                    ON s.codigo = d.colegio_bk
                WHERE d.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                  AND d.municipio IN ({placeholders})
                  AND d.email IS NOT NULL
                  AND TRIM(d.email) != ''
                  AND f.avg_punt_global > 0
            )
            SELECT *
            FROM ranked
            WHERE rank_municipio <= ?
            ORDER BY municipio, rank_municipio
        """

        params = [ano] + ciudades + [top_n]

        self.stdout.write("  Consultando DuckDB...", ending=' ')
        try:
            df = execute_query(query, params=params)
        except Exception as e:
            err = str(e)
            self.stderr.write(self.style.ERROR(f"Error en DuckDB: {err}"))
            if 'icfes_silver' in err or 'colegios' in err.lower():
                self.stderr.write(self.style.WARNING(
                    "\n  NOTA: El prod DuckDB solo tiene tablas gold (sin icfes_silver.colegios).\n"
                    "  Corre este comando LOCALMENTE apuntando al Postgres de Railway:\n\n"
                    "    DATABASE_URL=<railway_postgres_url> \\\n"
                    "    python manage.py import_campaign_prospects --settings=config.settings.railway\n\n"
                    "  Esto usa tu DuckDB local (con emails) y escribe en Railway Postgres."
                ))
            return

        if df.empty:
            self.stderr.write(self.style.WARNING(
                "No se encontraron prospectos. Verifica los nombres de ciudades y el año."
            ))
            return

        total = len(df)
        self.stdout.write(self.style.SUCCESS(f"OK — {total} prospectos encontrados"))

        # ── 2. Resumen por ciudad ───────────────────────────────────────
        self.stdout.write("\n  Resumen por ciudad:")
        for ciudad, grp in df.groupby('municipio'):
            self.stdout.write(f"    {ciudad:<20} {len(grp)} colegios")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n  DRY RUN — no se insertó nada en BD."))
            # Mostrar muestra
            self.stdout.write("\n  Primeros 5 prospectos:")
            for _, row in df.head(5).iterrows():
                self.stdout.write(
                    f"    [{row['rank_municipio']}] {row['nombre_colegio']} "
                    f"({row['municipio']}) — {row['email']} — puntaje {row['avg_punt_global']:.1f}"
                )
            return

        # ── 3. Crear Campaign en Postgres ──────────────────────────────
        campaign = Campaign.objects.create(
            nombre           = options['nombre'],
            lote             = options['lote'],
            estado           = 'borrador',
            descripcion      = (
                f"Importada automáticamente. Ciudades: {', '.join(ciudades)}. "
                f"Top {top_n} privados por ciudad. Año referencia: {ano}."
            ),
            email_remitente  = options['email_remitente'],
            nombre_remitente = options['nombre_remitente'],
            ciudades_objetivo= ', '.join(ciudades),
            top_n_por_ciudad = top_n,
        )
        self.stdout.write(f"\n  Campaign creada: ID={campaign.pk} — «{campaign.nombre}»")

        # ── 4. Insertar CampaignProspect ───────────────────────────────
        self.stdout.write("  Insertando prospectos...", ending=' ')
        prospectos = []
        skipped    = 0

        for _, row in df.iterrows():
            slug     = row.get('slug', '')
            demo_url = f"{BASE_URL}/colegio/{slug}/" if slug else BASE_URL

            prospectos.append(CampaignProspect(
                campaign        = campaign,
                nombre_colegio  = row.get('nombre_colegio', ''),
                rector          = row.get('rector', '') or '',
                email           = row.get('email', ''),
                telefono        = row.get('telefono', '') or '',
                municipio       = row.get('municipio', ''),
                departamento    = row.get('departamento', ''),
                slug            = slug,
                avg_punt_global = float(row.get('avg_punt_global', 0) or 0),
                rank_municipio  = int(row.get('rank_municipio', 0)),
                demo_url        = demo_url,
                estado          = 'pendiente',
            ))

        try:
            created = CampaignProspect.objects.bulk_create(
                prospectos,
                ignore_conflicts=True,   # unique_together(campaign, email) — evita duplicados
            )
            self.stdout.write(self.style.SUCCESS(f"OK — {len(created)} insertados ({skipped} duplicados ignorados)"))
        except Exception as e:
            campaign.delete()
            self.stderr.write(self.style.ERROR(f"Error al insertar prospectos: {e}"))
            return

        # ── 5. Resumen final ───────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\n"
            f"  IMPORTACION COMPLETADA\n"
            f"{'='*60}\n"
            f"  Campaign ID  : {campaign.pk}\n"
            f"  Nombre       : {campaign.nombre}\n"
            f"  Prospectos   : {len(created)}\n"
            f"  Estado       : Borrador (lista para lanzar)\n\n"
            f"  Proximos pasos:\n"
            f"  1. Ve al Django Admin > Campanas > [{campaign.pk}]\n"
            f"  2. Revisa los prospectos importados\n"
            f"  3. Haz clic en LANZAR CAMPANA cuando estes listo\n\n"
            f"  URL Admin: /admin/icfes_dashboard/campaign/{campaign.pk}/change/\n"
            f"{'='*60}\n"
        ))
