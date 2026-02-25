"""
Management command: generate_ingles_ia_analisis
================================================
Genera análisis narrativos con Claude AI del módulo de inglés,
guardando los resultados en PostgreSQL (icfes_dashboard_inglesanalisiaia).

Modos:
  Nacional   → 1 análisis con visión de todo el país (clusters, brechas, top/riesgo)
  Departamental → 1 análisis por departamento con contexto local vs nacional

Diseño:
  - Cada análisis archiva el anterior al regenerar (historial disponible)
  - Secciones parseadas individualmente para render selectivo en frontend
  - Solo requiere ANTHROPIC_API_KEY durante el deploy, no en runtime web

Uso:
    python manage.py generate_ingles_ia_analisis                # nacional 2024
    python manage.py generate_ingles_ia_analisis --ano 2023
    python manage.py generate_ingles_ia_analisis --departamento BOGOTA
    python manage.py generate_ingles_ia_analisis --departamento ALL  # los 33
    python manage.py generate_ingles_ia_analisis --dry-run
    python manage.py generate_ingles_ia_analisis --forzar
"""

import re
import time
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_IA   = "claude-sonnet-4-6"
MAX_TOKENS = 4096
ANO_DEFAULT = 2024


# ---------------------------------------------------------------------------
# 1. Extracción de datos desde DuckDB
# ---------------------------------------------------------------------------

def _get_duckdb_data_nacional(ano: int) -> dict:
    """Datos para análisis nacional."""
    from icfes_dashboard.db_utils import execute_query

    data = {}

    data['kpis'] = execute_query(f"""
        SELECT
            ROUND(AVG(avg_ingles), 2)                        AS promedio_nacional,
            COUNT(DISTINCT cole_cod_dane_establecimiento)     AS total_colegios,
            SUM(estudiantes)                                  AS total_estudiantes,
            ROUND(MIN(avg_ingles), 1)                        AS minimo,
            ROUND(MAX(avg_ingles), 1)                        AS maximo
        FROM gold.icfes_master_resumen
        WHERE CAST(ano AS INTEGER) = {ano}
          AND avg_ingles > 0 AND estudiantes >= 5
    """).iloc[0].to_dict()

    data['tendencia'] = execute_query(f"""
        SELECT CAST(ano AS INTEGER) AS ano, ROUND(AVG(avg_ingles), 2) AS promedio
        FROM gold.icfes_master_resumen
        WHERE CAST(ano AS INTEGER) BETWEEN {ano-4} AND {ano} AND avg_ingles > 0
        GROUP BY ano ORDER BY ano
    """).to_dict(orient='records')

    data['mcer'] = execute_query(f"""
        SELECT nivel_ingles_mcer AS nivel, COUNT(*) AS estudiantes,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) AS pct
        FROM gold.fact_icfes_analytics
        WHERE CAST(ano AS INTEGER) = {ano} AND nivel_ingles_mcer IS NOT NULL
        GROUP BY nivel_ingles_mcer ORDER BY nivel_ingles_mcer
    """).to_dict(orient='records')

    data['clusters'] = execute_query("""
        SELECT cluster_label,
               COUNT(*)                           AS n_departamentos,
               ROUND(AVG(promedio_reciente), 2)   AS promedio_reciente,
               ROUND(AVG(tendencia_pendiente), 3) AS tendencia_pts_ano,
               STRING_AGG(departamento, ', ')      AS departamentos
        FROM gold.fct_clusters_depto_ingles
        GROUP BY cluster_label ORDER BY promedio_reciente DESC
    """).to_dict(orient='records')

    data['prediccion'] = {
        'top_mejora': execute_query("""
            SELECT nombre_colegio, departamento,
                   avg_ingles_actual, avg_ingles_predicho, cambio_predicho
            FROM gold.fct_prediccion_ingles ORDER BY cambio_predicho DESC LIMIT 5
        """).to_dict(orient='records'),
        'top_riesgo': execute_query("""
            SELECT nombre_colegio, departamento,
                   avg_ingles_actual, avg_ingles_predicho, cambio_predicho
            FROM gold.fct_prediccion_ingles ORDER BY cambio_predicho ASC LIMIT 5
        """).to_dict(orient='records'),
        'distribucion': execute_query("""
            SELECT tendencia, COUNT(*) AS n_colegios,
                   ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) AS pct
            FROM gold.fct_prediccion_ingles GROUP BY tendencia
        """).to_dict(orient='records'),
    }

    df_story = execute_query("""
        SELECT hogar_postgrado, hogar_ninguno, n_postgrado, n_ninguno
        FROM gold.fct_ingles_story_educacion
    """)
    data['brechas'] = {
        'por_estrato': execute_query("""
            SELECT estrato, avg_ingles, n_estudiantes
            FROM gold.fct_ingles_brecha_estrato ORDER BY estrato
        """).to_dict(orient='records'),
        'story': df_story.iloc[0].to_dict() if not df_story.empty else {},
    }

    return data


def _get_duckdb_data_depto(ano: int, departamento: str) -> dict:
    """Datos para análisis de un departamento específico + benchmark nacional."""
    from icfes_dashboard.db_utils import execute_query

    data = {}

    # KPIs del departamento vs nacional
    df_depto = execute_query(f"""
        SELECT
            ROUND(AVG(avg_ingles), 2)                       AS promedio_depto,
            COUNT(DISTINCT cole_cod_dane_establecimiento)    AS total_colegios,
            SUM(estudiantes)                                 AS total_estudiantes,
            ROUND(MIN(avg_ingles), 1)                       AS minimo,
            ROUND(MAX(avg_ingles), 1)                       AS maximo
        FROM gold.icfes_master_resumen
        WHERE CAST(ano AS INTEGER) = {ano}
          AND avg_ingles > 0 AND estudiantes >= 5
          AND UPPER(cole_depto_ubicacion) = UPPER('{departamento}')
    """)
    df_nacional = execute_query(f"""
        SELECT ROUND(AVG(avg_ingles), 2) AS promedio_nacional
        FROM gold.icfes_master_resumen
        WHERE CAST(ano AS INTEGER) = {ano} AND avg_ingles > 0 AND estudiantes >= 5
    """)
    data['kpis'] = {
        **df_depto.iloc[0].to_dict(),
        'promedio_nacional': float(df_nacional.iloc[0]['promedio_nacional']),
    }

    # Ranking del departamento en el año
    df_ranking = execute_query(f"""
        SELECT UPPER(cole_depto_ubicacion) AS depto,
               ROUND(AVG(avg_ingles), 2)   AS promedio
        FROM gold.icfes_master_resumen
        WHERE CAST(ano AS INTEGER) = {ano} AND avg_ingles > 0
        GROUP BY cole_depto_ubicacion
        ORDER BY promedio DESC
    """)
    ranking_list = df_ranking['depto'].str.upper().tolist()
    data['ranking_nacional'] = (
        ranking_list.index(departamento.upper()) + 1 if departamento.upper() in ranking_list else None
    )
    data['total_departamentos'] = len(ranking_list)

    # Tendencia histórica del departamento
    data['tendencia'] = execute_query(f"""
        SELECT CAST(ano AS INTEGER) AS ano,
               ROUND(AVG(avg_ingles), 2) AS promedio_depto
        FROM gold.icfes_master_resumen
        WHERE CAST(ano AS INTEGER) BETWEEN {ano-4} AND {ano}
          AND avg_ingles > 0
          AND UPPER(cole_depto_ubicacion) = UPPER('{departamento}')
        GROUP BY ano ORDER BY ano
    """).to_dict(orient='records')

    # Tendencia nacional para comparar
    data['tendencia_nacional'] = execute_query(f"""
        SELECT CAST(ano AS INTEGER) AS ano,
               ROUND(AVG(avg_ingles), 2) AS promedio_nacional
        FROM gold.icfes_master_resumen
        WHERE CAST(ano AS INTEGER) BETWEEN {ano-4} AND {ano} AND avg_ingles > 0
        GROUP BY ano ORDER BY ano
    """).to_dict(orient='records')

    # Cluster al que pertenece
    df_cluster = execute_query(f"""
        SELECT cluster_label, promedio_reciente, tendencia_pendiente,
               cambio_abs, n_colegios_activos
        FROM gold.fct_clusters_depto_ingles
        WHERE UPPER(departamento) = UPPER('{departamento}')
        LIMIT 1
    """)
    data['cluster'] = df_cluster.iloc[0].to_dict() if not df_cluster.empty else {}

    # Otros departamentos en el mismo cluster
    if data['cluster']:
        df_mismo_cluster = execute_query(f"""
            SELECT departamento, promedio_reciente, tendencia_pendiente
            FROM gold.fct_clusters_depto_ingles
            WHERE cluster_label = '{data["cluster"]["cluster_label"]}'
              AND UPPER(departamento) != UPPER('{departamento}')
            ORDER BY promedio_reciente DESC
        """)
        data['cluster_pares'] = df_mismo_cluster.to_dict(orient='records')
    else:
        data['cluster_pares'] = []

    # Predicciones 2025 para colegios de este departamento
    data['prediccion'] = {
        'top_mejora': execute_query(f"""
            SELECT nombre_colegio, avg_ingles_actual, avg_ingles_predicho, cambio_predicho
            FROM gold.fct_prediccion_ingles
            WHERE UPPER(departamento) = UPPER('{departamento}')
            ORDER BY cambio_predicho DESC LIMIT 5
        """).to_dict(orient='records'),
        'top_riesgo': execute_query(f"""
            SELECT nombre_colegio, avg_ingles_actual, avg_ingles_predicho, cambio_predicho
            FROM gold.fct_prediccion_ingles
            WHERE UPPER(departamento) = UPPER('{departamento}')
            ORDER BY cambio_predicho ASC LIMIT 5
        """).to_dict(orient='records'),
        'distribucion': execute_query(f"""
            SELECT tendencia, COUNT(*) AS n_colegios,
                   ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) AS pct
            FROM gold.fct_prediccion_ingles
            WHERE UPPER(departamento) = UPPER('{departamento}')
            GROUP BY tendencia
        """).to_dict(orient='records'),
    }

    return data


# ---------------------------------------------------------------------------
# 2. Construcción del prompt
# ---------------------------------------------------------------------------

def _build_prompt_nacional(data: dict, ano: int) -> str:
    kpis     = data.get('kpis', {})
    tendencia = data.get('tendencia', [])
    clusters  = data.get('clusters', [])
    pred      = data.get('prediccion', {})
    brechas   = data.get('brechas', {})
    story     = brechas.get('story', {})

    tendencia_str = ' | '.join(f"{r['ano']}: {r['promedio']:.1f}" for r in tendencia)
    clusters_str  = '\n'.join(
        f"  - {r['cluster_label']} ({r['n_departamentos']} dptos, "
        f"{r['promedio_reciente']:.1f} pts, {r['tendencia_pts_ano']:+.3f} pts/año): {r['departamentos']}"
        for r in clusters
    )
    pred_mejora_str = '\n'.join(
        f"  [{r['cambio_predicho']:+.1f}] {r['nombre_colegio']} ({r['departamento']}): "
        f"{r['avg_ingles_actual']:.1f} -> {r['avg_ingles_predicho']:.1f}"
        for r in pred.get('top_mejora', [])
    )
    pred_riesgo_str = '\n'.join(
        f"  [{r['cambio_predicho']:+.1f}] {r['nombre_colegio']} ({r['departamento']}): "
        f"{r['avg_ingles_actual']:.1f} -> {r['avg_ingles_predicho']:.1f}"
        for r in pred.get('top_riesgo', [])
    )
    dist_str    = ', '.join(f"{r['tendencia']}: {r['n_colegios']} ({r['pct']}%)" for r in pred.get('distribucion', []))
    estrato_str = ' | '.join(f"E{r['estrato']}: {r['avg_ingles']:.1f}" for r in brechas.get('por_estrato', []))

    return f"""Eres un analista experto en educación colombiana. Analiza ÚNICAMENTE los datos proporcionados, sin inventar cifras.

## DATOS — INGLÉS NACIONAL {ano}

KPIs: promedio={kpis.get('promedio_nacional','?'):.1f} pts | colegios={kpis.get('total_colegios','?'):,.0f} | estudiantes={kpis.get('total_estudiantes','?'):,.0f} | rango={kpis.get('minimo','?'):.1f}–{kpis.get('maximo','?'):.1f}

Tendencia: {tendencia_str}

Clusters departamentales:
{clusters_str}

Predicciones 2025 (GBM R²=0.875, MAE=2.66 pts):
  Distribución: {dist_str}
  Top mejora:
{pred_mejora_str}
  Top riesgo:
{pred_riesgo_str}

Brechas: {estrato_str}
Hogar con Postgrado={story.get('hogar_postgrado','?')} pts ({story.get('n_postgrado',0):,} estudiantes) vs Sin educación={story.get('hogar_ninguno','?')} pts ({story.get('n_ninguno',0):,} estudiantes)

---
Genera análisis ejecutivo en español para secretarías de educación y Ministerio.
Usa este formato EXACTO:

###SITUACION###
[2-3 párrafos: estado actual en {ano}, cifras clave, tendencia reciente, nivel MCER dominante]

###GEOGRAFIA###
[2 párrafos: patrones por cluster, departamentos que lideran y rezagados, concentración geográfica del riesgo]

###PREDICCION###
[2 párrafos: qué predice el modelo para {ano+1}, dónde se concentran mejoras y riesgos, implicaciones territoriales]

###BRECHA###
[2 párrafos: brecha socioeconómica por estrato y capital educativo del hogar; menciona que es correlación, no causalidad]

###RECOMENDACION###
[3 recomendaciones concretas para política pública, basadas solo en los datos anteriores]

Tono: técnico pero accesible. Usa cifras exactas de los datos."""


def _build_prompt_depto(data: dict, ano: int, departamento: str) -> str:
    kpis    = data.get('kpis', {})
    cluster = data.get('cluster', {})
    tendencia = data.get('tendencia', [])
    tendencia_nac = data.get('tendencia_nacional', [])
    pred    = data.get('prediccion', {})
    ranking = data.get('ranking_nacional')
    total_d = data.get('total_departamentos', 33)
    pares   = data.get('cluster_pares', [])

    tendencia_str = ' | '.join(
        f"{r['ano']}: {r['promedio_depto']:.1f}"
        for r in tendencia
    )
    # Añadir nacional como referencia
    nac_by_ano = {r['ano']: r['promedio_nacional'] for r in tendencia_nac}
    tendencia_vs = ' | '.join(
        f"{r['ano']}: dpto={r['promedio_depto']:.1f} vs nac={nac_by_ano.get(r['ano'], '?'):.1f}"
        for r in tendencia
    )

    pares_str = ', '.join(r['departamento'].title() for r in pares[:6])
    pred_mejora_str = '\n'.join(
        f"  [{r['cambio_predicho']:+.1f}] {r['nombre_colegio']}: "
        f"{r['avg_ingles_actual']:.1f} -> {r['avg_ingles_predicho']:.1f}"
        for r in pred.get('top_mejora', [])
    )
    pred_riesgo_str = '\n'.join(
        f"  [{r['cambio_predicho']:+.1f}] {r['nombre_colegio']}: "
        f"{r['avg_ingles_actual']:.1f} -> {r['avg_ingles_predicho']:.1f}"
        for r in pred.get('top_riesgo', [])
    )
    dist_str = ', '.join(f"{r['tendencia']}: {r['n_colegios']} ({r['pct']}%)" for r in pred.get('distribucion', []))

    return f"""Eres un analista experto en educación colombiana. Analiza ÚNICAMENTE los datos proporcionados, sin inventar cifras.

## DATOS — INGLÉS {departamento.upper()} {ano}

KPIs departamento: promedio={kpis.get('promedio_depto','?'):.1f} pts | colegios={kpis.get('total_colegios','?'):,.0f} | estudiantes={kpis.get('total_estudiantes','?'):,.0f}
Benchmark nacional: promedio={kpis.get('promedio_nacional','?'):.1f} pts
Ranking nacional: #{ranking} de {total_d} departamentos

Tendencia histórica (depto vs nacional):
{tendencia_vs}

Cluster K-Means: "{cluster.get('cluster_label','?')}" — promedio={cluster.get('promedio_reciente','?'):.1f} pts, tendencia={cluster.get('tendencia_pendiente','?'):+.3f} pts/año
Departamentos en el mismo cluster: {pares_str or 'Ninguno'}

Predicciones 2025 para colegios de {departamento.title()} (GBM R²=0.875):
  Distribución local: {dist_str}
  Top mejora:
{pred_mejora_str or '  (sin datos)'}
  Top riesgo:
{pred_riesgo_str or '  (sin datos)'}

---
Genera análisis ejecutivo en español para la Secretaría de Educación de {departamento.title()}.
Usa este formato EXACTO:

###SITUACION###
[2-3 párrafos: estado actual en {departamento.title()} en {ano}, comparación vs promedio nacional, posición relativa entre departamentos]

###GEOGRAFIA###
[2 párrafos: perfil del cluster al que pertenece {departamento.title()}, comparación con departamentos del mismo grupo, fortalezas y debilidades locales]

###PREDICCION###
[2 párrafos: qué predice el modelo para {ano+1} en los colegios de {departamento.title()}, cuáles tienen mayor oportunidad y cuáles mayor riesgo]

###BRECHA###
[2 párrafos: brechas internas del departamento si las hay, contexto regional; indica que los datos son correlacionales, no causales]

###RECOMENDACION###
[3 recomendaciones concretas para la Secretaría de Educación de {departamento.title()}, basadas solo en los datos anteriores]

Tono: técnico pero accesible. Usa cifras exactas. Dirige el texto a funcionarios de la secretaría."""


# ---------------------------------------------------------------------------
# 3. Parsear secciones
# ---------------------------------------------------------------------------

def _parse_sections(text: str) -> dict:
    sections = {}
    markers  = ['SITUACION', 'GEOGRAFIA', 'PREDICCION', 'BRECHA', 'RECOMENDACION']
    pattern  = r'###(' + '|'.join(markers) + r')###\s*(.*?)(?=###(?:' + '|'.join(markers) + r')###|$)'
    for m in re.finditer(pattern, text, re.DOTALL):
        sections[m.group(1).lower()] = m.group(2).strip()
    return sections


# ---------------------------------------------------------------------------
# 4. Guardar en PostgreSQL
# ---------------------------------------------------------------------------

def _guardar(tipo: str, parametro: str, ano: int,
             analisis_md: str, sections: dict,
             tokens_input: int, tokens_output: int):
    from icfes_dashboard.models import InglesAnalisisIA

    # Archivar activos anteriores
    InglesAnalisisIA.objects.filter(
        tipo=tipo, parametro=parametro,
        ano_referencia=ano, estado=InglesAnalisisIA.ESTADO_ACTIVO,
    ).update(estado=InglesAnalisisIA.ESTADO_ARCHIVADO)

    return InglesAnalisisIA.objects.create(
        tipo=tipo, parametro=parametro, ano_referencia=ano,
        estado=InglesAnalisisIA.ESTADO_ACTIVO,
        analisis_md=analisis_md,
        situacion=sections.get('situacion', ''),
        geografia=sections.get('geografia', ''),
        prediccion=sections.get('prediccion', ''),
        brecha=sections.get('brecha', ''),
        recomendacion=sections.get('recomendacion', ''),
        modelo_ia=MODEL_IA,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )


# ---------------------------------------------------------------------------
# 5. Management Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Genera análisis IA de inglés (nacional o por departamento) y persiste en PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument('--ano', type=int, default=ANO_DEFAULT)
        parser.add_argument(
            '--departamento', type=str, default='',
            help='Departamento en mayúsculas, o "ALL" para generar los 33',
        )
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--forzar', action='store_true',
                            help='Regenera aunque ya exista análisis activo')

    def handle(self, *args, **options):
        ano        = options['ano']
        depto_arg  = options['departamento'].strip().upper()
        dry_run    = options['dry_run']
        forzar     = options['forzar']

        from icfes_dashboard.db_utils import execute_query

        if depto_arg == 'ALL':
            # Obtener lista de los 33 departamentos desde la tabla de clusters
            df_deptos = execute_query(
                "SELECT DISTINCT departamento FROM gold.fct_clusters_depto_ingles ORDER BY departamento"
            )
            departamentos = df_deptos['departamento'].tolist()
            self.stdout.write(f"\nGenerando análisis para {len(departamentos)} departamentos (año {ano})...\n")
            for i, depto in enumerate(departamentos, 1):
                self.stdout.write(f"  [{i:02d}/{len(departamentos)}] {depto}...")
                self._generar(ano, depto, dry_run, forzar)
                if not dry_run and i < len(departamentos):
                    time.sleep(1)  # evitar rate-limit de la API
            self.stdout.write(self.style.SUCCESS(f"\nOK: {len(departamentos)} análisis departamentales generados."))

        elif depto_arg:
            # Un solo departamento
            self._generar(ano, depto_arg, dry_run, forzar)

        else:
            # Nacional
            self._generar_nacional(ano, dry_run, forzar)

    def _get_client(self):
        if not getattr(settings, 'ANTHROPIC_API_KEY', None):
            raise CommandError("ANTHROPIC_API_KEY no configurada en settings.")
        import anthropic
        return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _llamar_api(self, client, prompt: str):
        msg = client.messages.create(
            model=MODEL_IA, max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text, msg.usage.input_tokens, msg.usage.output_tokens

    def _generar_nacional(self, ano: int, dry_run: bool, forzar: bool):
        from icfes_dashboard.models import InglesAnalisisIA

        self.stdout.write(f"\nAnálisis NACIONAL — año {ano}")

        existe = InglesAnalisisIA.objects.filter(
            tipo=InglesAnalisisIA.TIPO_NACIONAL, parametro='',
            ano_referencia=ano, estado=InglesAnalisisIA.ESTADO_ACTIVO,
        ).exists()
        if existe and not forzar:
            self.stdout.write(self.style.WARNING("  Ya existe. Usa --forzar para regenerar."))
            return

        data   = _get_duckdb_data_nacional(ano)
        prompt = _build_prompt_nacional(data, ano)

        if dry_run:
            self.stdout.write(prompt[:1500] + "\n[...DRY RUN - no se llamó API]")
            return

        client = self._get_client()
        texto, t_in, t_out = self._llamar_api(client, prompt)
        sections = _parse_sections(texto)
        _guardar(InglesAnalisisIA.TIPO_NACIONAL, '', ano, texto, sections, t_in, t_out)
        self.stdout.write(self.style.SUCCESS(f"  OK — {t_in}in/{t_out}out tokens"))

    def _generar(self, ano: int, departamento: str, dry_run: bool, forzar: bool):
        from icfes_dashboard.models import InglesAnalisisIA

        existe = InglesAnalisisIA.objects.filter(
            tipo=InglesAnalisisIA.TIPO_DEPARTAMENTO, parametro=departamento,
            ano_referencia=ano, estado=InglesAnalisisIA.ESTADO_ACTIVO,
        ).exists()
        if existe and not forzar:
            self.stdout.write(self.style.WARNING(f"  {departamento}: ya existe. Omitiendo."))
            return

        try:
            data   = _get_duckdb_data_depto(ano, departamento)
            prompt = _build_prompt_depto(data, ano, departamento)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  {departamento}: error obteniendo datos — {e}"))
            return

        if dry_run:
            self.stdout.write(f"  {departamento}: prompt OK ({len(prompt)} chars) [DRY RUN]")
            return

        try:
            client = self._get_client()
            texto, t_in, t_out = self._llamar_api(client, prompt)
            sections = _parse_sections(texto)
            _guardar(InglesAnalisisIA.TIPO_DEPARTAMENTO, departamento, ano,
                     texto, sections, t_in, t_out)
            self.stdout.write(f"  {departamento}: OK — {t_in}in/{t_out}out tokens")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  {departamento}: error API — {e}"))
