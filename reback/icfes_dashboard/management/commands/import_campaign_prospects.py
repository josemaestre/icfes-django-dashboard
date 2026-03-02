"""
Management command: import_campaign_prospects
Importa los top N colegios privados por ciudad/departamento desde DuckDB → Postgres
(Campaign + CampaignProspect).

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
2. Consulta DuckDB (read-only) para obtener los top N privados por segmento
3. Inserta CampaignProspect por cada colegio encontrado
4. Muestra resumen con pipeline por segmento
"""
from django.core.management.base import BaseCommand

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
    help = 'Importa top N colegios privados por ciudad/departamento desde DuckDB a una Campaign en Postgres.'

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
            '--departamentos', type=str, default='',
            help='Departamentos separados por coma. Si se omite en segmento departamento, usa todos con datos.'
        )
        parser.add_argument(
            '--segmento', type=str, default='ciudad', choices=['ciudad', 'departamento'],
            help='Segmentación de campaña: ciudad o departamento'
        )
        parser.add_argument(
            '--top', type=int, default=10,
            help='Top N colegios por segmento'
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
        departamentos = [d.strip() for d in options['departamentos'].split(',') if d.strip()]
        segmento = options['segmento']
        top_n    = options['top']
        ano      = options['ano']
        dry_run  = options['dry_run']

        if segmento == 'ciudad' and not ciudades:
            self.stderr.write(self.style.ERROR("Debe indicar al menos una ciudad para segmento=ciudad"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'='*60}\n  IMPORTAR PROSPECTOS DE CAMPAÑA\n{'='*60}"
        ))
        self.stdout.write(f"  Segmento   : {segmento}")
        if segmento == 'ciudad':
            self.stdout.write(f"  Ciudades   : {', '.join(ciudades)}")
            self.stdout.write(f"  Año        : {ano}")
        else:
            self.stdout.write(f"  Departamentos : {', '.join(departamentos) if departamentos else '[TODOS]'}")
            self.stdout.write("  Año puntaje   : último disponible por colegio")
        self.stdout.write(f"  Top N      : {top_n} por {segmento}")
        self.stdout.write(f"  Dry run    : {'SÍ' if dry_run else 'NO'}")
        self.stdout.write("")

        # ── 1. Query DuckDB ────────────────────────────────────────────
        # NOTA: Usamos colegio_bk (código DANE normalizado) como join key en lugar
        # de colegio_sk, ya que es el identificador de negocio estable. El JOIN
        # con fct_agg_colegios_ano es LEFT JOIN opcional: la mayoría de colegios
        # con email en dim_colegios son jardines/escuelas que no presentan ICFES.
        # Si hay score disponible, se usa para ranking; si no, se ordena por nombre.
        if segmento == 'ciudad':
            placeholders = ', '.join(['?' for _ in ciudades])
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
                            ORDER BY
                                CASE WHEN f.avg_punt_global IS NULL THEN 1 ELSE 0 END,
                                COALESCE(f.avg_punt_global, 0) DESC,
                                d.nombre_colegio ASC
                        ) AS rank_municipio
                    FROM gold.dim_colegios d
                    LEFT JOIN gold.fct_agg_colegios_ano f
                        ON f.colegio_bk = d.colegio_bk
                        AND f.ano = CAST(? AS VARCHAR)
                        AND f.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                    LEFT JOIN gold.dim_colegios_slugs s
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
            params = [ano] + ciudades + [top_n]
        else:
            dep_filter = ""
            dep_params = []
            if departamentos:
                placeholders = ', '.join(['?' for _ in departamentos])
                dep_filter = f"AND d.departamento IN ({placeholders})"
                dep_params = departamentos

            query = f"""
                WITH ult_puntaje AS (
                    SELECT
                        colegio_bk,
                        avg_punt_global,
                        ROW_NUMBER() OVER (
                            PARTITION BY colegio_bk
                            ORDER BY CAST(ano AS INTEGER) DESC
                        ) AS rn
                    FROM gold.fct_agg_colegios_ano
                    WHERE sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND avg_punt_global IS NOT NULL
                      AND avg_punt_global > 0
                ),
                ranked AS (
                    SELECT
                        d.nombre_colegio,
                        d.rector,
                        d.email,
                        d.telefono,
                        d.municipio,
                        d.departamento,
                        COALESCE(s.slug, '') AS slug,
                        u.avg_punt_global,
                        ROW_NUMBER() OVER (
                            PARTITION BY d.departamento
                            ORDER BY
                                CASE WHEN u.avg_punt_global IS NULL THEN 1 ELSE 0 END,
                                COALESCE(u.avg_punt_global, 0) DESC,
                                d.nombre_colegio ASC
                        ) AS rank_municipio
                    FROM gold.dim_colegios d
                    LEFT JOIN ult_puntaje u
                        ON u.colegio_bk = d.colegio_bk
                       AND u.rn = 1
                    LEFT JOIN gold.dim_colegios_slugs s
                        ON s.codigo = d.colegio_bk
                    WHERE d.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND d.email IS NOT NULL
                      AND TRIM(d.email) != ''
                      {dep_filter}
                )
                SELECT *
                FROM ranked
                WHERE rank_municipio <= ?
                ORDER BY departamento, rank_municipio, municipio
            """
            params = dep_params + [top_n]

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
            if segmento == 'ciudad':
                diag_query = f"""
                    SELECT
                        COUNT(*) AS total_join,
                        SUM(CASE WHEN d.email IS NOT NULL AND TRIM(d.email) != '' THEN 1 ELSE 0 END) AS con_email,
                        SUM(CASE WHEN f.avg_punt_global > 0 THEN 1 ELSE 0 END) AS con_puntaje,
                        SUM(
                            CASE
                                WHEN d.email IS NOT NULL
                                     AND TRIM(d.email) != ''
                                THEN 1 ELSE 0
                            END
                        ) AS aptos
                    FROM gold.dim_colegios d
                    LEFT JOIN gold.fct_agg_colegios_ano f
                        ON f.colegio_bk = d.colegio_bk
                        AND f.ano = CAST(? AS VARCHAR)
                        AND f.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                    WHERE d.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND d.municipio IN ({placeholders})
                """
                diag_params = [ano] + ciudades
            else:
                dep_filter = ""
                diag_params = []
                if departamentos:
                    dep_placeholders = ', '.join(['?' for _ in departamentos])
                    dep_filter = f"AND d.departamento IN ({dep_placeholders})"
                    diag_params = departamentos
                diag_query = f"""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN d.email IS NOT NULL AND TRIM(d.email) != '' THEN 1 ELSE 0 END) AS con_email,
                        SUM(CASE WHEN u.avg_punt_global IS NOT NULL THEN 1 ELSE 0 END) AS con_puntaje
                    FROM gold.dim_colegios d
                    LEFT JOIN (
                        SELECT colegio_bk, avg_punt_global
                        FROM (
                            SELECT
                                colegio_bk,
                                avg_punt_global,
                                ROW_NUMBER() OVER (
                                    PARTITION BY colegio_bk
                                    ORDER BY CAST(ano AS INTEGER) DESC
                                ) AS rn
                            FROM gold.fct_agg_colegios_ano
                            WHERE sector IN ('NO OFICIAL', 'NO_OFICIAL')
                              AND avg_punt_global IS NOT NULL
                              AND avg_punt_global > 0
                        ) t
                        WHERE rn = 1
                    ) u ON u.colegio_bk = d.colegio_bk
                    WHERE d.sector IN ('NO OFICIAL', 'NO_OFICIAL')
                      AND d.email IS NOT NULL
                      AND TRIM(d.email) != ''
                      {dep_filter}
                """
            try:
                diag_df = execute_query(diag_query, params=diag_params)
                if not diag_df.empty:
                    diag = diag_df.iloc[0]
                    total_join = int(diag.get('total_join') or diag.get('total') or 0)
                    con_email = int(diag.get('con_email') or 0)
                    con_puntaje = int(diag.get('con_puntaje') or 0)
                    aptos = int(diag.get('aptos') or 0)
                    self.stderr.write(
                        self.style.WARNING(
                            "Diagnóstico filtros: "
                            f"total/join={total_join}, "
                            f"con_email={con_email}, "
                            f"con_puntaje={con_puntaje}, "
                            f"aptos={aptos}"
                        )
                    )
            except Exception as diag_error:
                self.stderr.write(
                    self.style.WARNING(f"No fue posible ejecutar diagnóstico adicional: {diag_error}")
                )
            self.stderr.write(self.style.WARNING(
                "No se encontraron prospectos. Verifica los nombres de ciudades y el año."
            ))
            return

        total = len(df)
        sin_score = int((df['avg_punt_global'].isna() | (df['avg_punt_global'] <= 0)).sum())
        if sin_score > 0:
            self.stdout.write(self.style.WARNING(
                f"  ⚠  {sin_score}/{total} prospectos sin puntaje ICFES "
                "(colegios SINEB que no presentan ICFES — se incluyen con score=0)."
            ))
        self.stdout.write(self.style.SUCCESS(f"OK — {total} prospectos encontrados"))

        # ── 2. Resumen por segmento ─────────────────────────────────────
        if segmento == 'ciudad':
            self.stdout.write("\n  Resumen por ciudad:")
            for ciudad, grp in df.groupby('municipio'):
                self.stdout.write(f"    {ciudad:<20} {len(grp)} colegios")
        else:
            self.stdout.write("\n  Resumen por departamento:")
            for dep, grp in df.groupby('departamento'):
                self.stdout.write(f"    {dep:<20} {len(grp)} colegios")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n  DRY RUN — no se insertó nada en BD."))
            # Mostrar muestra
            self.stdout.write("\n  Primeros 5 prospectos:")
            for _, row in df.head(5).iterrows():
                score = row.get('avg_punt_global')
                score_txt = f"{float(score):.1f}" if score is not None else "N/A"
                self.stdout.write(
                    f"    [{row['rank_municipio']}] {row['nombre_colegio']} "
                    f"({row['municipio']}) — {row['email']} — puntaje {score_txt}"
                )
            return

        # ── 3. Crear Campaign en Postgres ──────────────────────────────
        campaign = Campaign.objects.create(
            nombre           = options['nombre'],
            lote             = options['lote'],
            estado           = 'borrador',
            descripcion      = (
                (
                    f"Importada automáticamente. Ciudades: {', '.join(ciudades)}. "
                    f"Top {top_n} privados por ciudad. Año referencia: {ano}."
                    if segmento == 'ciudad' else
                    f"Importada automáticamente. Departamentos: "
                    f"{', '.join(departamentos) if departamentos else 'TODOS'}. "
                    f"Top {top_n} privados por departamento. Puntaje: último disponible."
                )
            ),
            email_remitente  = options['email_remitente'],
            nombre_remitente = options['nombre_remitente'],
            ciudades_objetivo= ', '.join(ciudades) if segmento == 'ciudad' else (
                ', '.join(departamentos) if departamentos else 'TODOS'
            ),
            top_n_por_ciudad = top_n,
        )
        self.stdout.write(f"\n  Campaign creada: ID={campaign.pk} — «{campaign.nombre}»")

        # ── 4. Insertar CampaignProspect ───────────────────────────────
        self.stdout.write("  Insertando prospectos...", ending=' ')
        prospectos = []

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
            skipped = total - len(created)
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
