"""
Management command: generate_ml_ia_analisis

Lee los resultados de los modelos ML desde DuckDB y genera un análisis
narrativo con Claude sonnet-4-6. Guarda en PostgreSQL (MlAnalisisIA).

Uso:
    python manage.py generate_ml_ia_analisis
    python manage.py generate_ml_ia_analisis --ano 2024
    python manage.py generate_ml_ia_analisis --forzar
"""
import re
import logging

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_IA   = 'claude-sonnet-4-6'
MAX_TOKENS = 4096
DEFAULT_ANO = 2024


# ---------------------------------------------------------------------------
# 1. Extracción de datos desde DuckDB
# ---------------------------------------------------------------------------

def _get_ml_data(ano: int) -> dict:
    """Extrae todos los datos necesarios para el prompt desde DuckDB."""
    from icfes_dashboard.db_utils import execute_query

    data = {}

    # SHAP importances
    data['shap'] = execute_query("""
        SELECT label, icono, shap_pts, rank, model_mae, model_r2
        FROM gold.fct_ml_shap_importances
        ORDER BY rank
        LIMIT 10
    """)

    # Partial dependence estrato
    data['partial'] = execute_query("""
        SELECT estrato, puntaje_predicho, orden
        FROM gold.fct_ml_shap_partial_estrato
        ORDER BY orden
    """)

    # Perfiles de clusters
    data['clusters'] = execute_query("""
        SELECT
            cluster_id, cluster_name, cluster_descripcion, cluster_color,
            COUNT(*) AS n_colegios,
            ROUND(AVG(avg_global), 1) AS avg_global,
            ROUND(AVG(pct_nbi), 1) AS pct_nbi,
            ROUND(AVG(pct_internet), 1) AS pct_internet,
            ROUND(AVG(avg_estrato), 2) AS avg_estrato
        FROM gold.fct_ml_social_clusters
        GROUP BY cluster_id, cluster_name, cluster_descripcion, cluster_color
        ORDER BY avg_global DESC
    """)

    # Stats de riesgo
    data['riesgo_stats'] = execute_query("""
        SELECT nivel_riesgo, COUNT(*) AS n
        FROM gold.fct_riesgo_colegios
        GROUP BY nivel_riesgo
        ORDER BY n DESC
    """)

    # Top 5 escuelas en riesgo alto
    data['riesgo_top'] = execute_query("""
        SELECT nombre_colegio, departamento, sector,
               ROUND(prob_declive * 100, 1) AS prob_pct,
               factores_principales
        FROM gold.fct_riesgo_colegios
        WHERE nivel_riesgo = 'Alto'
        ORDER BY prob_declive DESC
        LIMIT 5
    """)

    # Top B1 overperformers
    data['b1_top'] = execute_query("""
        SELECT nombre_colegio, departamento, sector,
               ROUND(ing_pct_b1, 1) AS pct_b1_real,
               ROUND(exceso_b1, 1) AS exceso_b1
        FROM gold.fct_ml_predictor_b1
        WHERE clasificacion_b1 IN ('Excepcional B1+', 'Notable B1+')
        ORDER BY exceso_b1 DESC
        LIMIT 5
    """)

    return data


# ---------------------------------------------------------------------------
# 2. Construcción del prompt
# ---------------------------------------------------------------------------

def _build_prompt(data: dict, ano: int) -> str:
    shap_df    = data['shap']
    partial_df = data['partial']
    clust_df   = data['clusters']
    riesgo_df  = data['riesgo_stats']
    riesgo_top = data['riesgo_top']
    b1_top     = data['b1_top']

    # Formatear SHAP
    shap_lines = '\n'.join(
        f"  {int(r['rank'])}. {r['label']}: {r['shap_pts']:.1f} pts SHAP"
        for _, r in shap_df.iterrows()
    )
    model_r2  = float(shap_df.iloc[0]['model_r2']) if not shap_df.empty else 0
    model_mae = float(shap_df.iloc[0]['model_mae']) if not shap_df.empty else 0

    # Brecha E1→E6
    brecha_estrato = ''
    if not partial_df.empty and len(partial_df) >= 2:
        e1 = float(partial_df[partial_df['estrato'] == 'Estrato 1']['puntaje_predicho'].iloc[0]) if 'Estrato 1' in partial_df['estrato'].values else 0
        e6 = float(partial_df[partial_df['estrato'] == 'Estrato 6']['puntaje_predicho'].iloc[0]) if 'Estrato 6' in partial_df['estrato'].values else 0
        brecha_estrato = f"{e6 - e1:+.1f} pts (E1={e1:.0f} → E6={e6:.0f})"

    # Formatear clusters
    cluster_lines = '\n'.join(
        f"  - {r['cluster_name']} ({int(r['n_colegios'])} colegios): "
        f"puntaje={r['avg_global']}, NBI={r['pct_nbi']}%, internet={r['pct_internet']}%, "
        f"estrato_prom={r['avg_estrato']:.1f}. Descripción: {r['cluster_descripcion']}"
        for _, r in clust_df.iterrows()
    )

    # Riesgo
    riesgo_stats_lines = '\n'.join(
        f"  - {r['nivel_riesgo']}: {int(r['n'])} colegios"
        for _, r in riesgo_df.iterrows()
    )
    riesgo_top_lines = '\n'.join(
        f"  {i+1}. {r['nombre_colegio']} ({r['departamento']}, {r['sector']}): "
        f"prob={r['prob_pct']}%"
        for i, (_, r) in enumerate(riesgo_top.iterrows())
    )

    # B1
    b1_lines = '\n'.join(
        f"  {i+1}. {r['nombre_colegio']} ({r['departamento']}, {r['sector']}): "
        f"B1={r['pct_b1_real']}%, exceso=+{r['exceso_b1']} pp sobre lo esperado"
        for i, (_, r) in enumerate(b1_top.iterrows())
    )

    prompt = f"""Eres un analista experto en educación colombiana con profundo conocimiento en ciencia de datos,
política pública educativa y contexto socioeconómico de Colombia.

Se te presentan los resultados de modelos de Machine Learning entrenados sobre 7.3 millones de registros
del examen ICFES (Saber 11) de Colombia, años 2014-2024. Genera un análisis narrativo profundo,
en español, que transforme estos números en historias poderosas sobre equidad educativa.

---
## DATOS DEL MODELO (año de referencia: {ano})

### Modelo XGBoost + SHAP (predictor de puntaje global)
- R² del modelo: {model_r2:.3f} (explica el {model_r2*100:.1f}% de la varianza)
- MAE: {model_mae:.1f} puntos
- Factores que más determinan el puntaje (importancia SHAP media):
{shap_lines}
- Brecha predicha por estrato (partial dependence): {brecha_estrato}

### K-Means Clustering — 5 arquetipos de colegios
{cluster_lines}

### Alertas de Riesgo de Declive (XGBoost clasificador)
{riesgo_stats_lines}
Top 5 colegios en mayor riesgo:
{riesgo_top_lines}

### Colegios que Superan su Predicción B1 Inglés
Top 5 'overperformers':
{b1_lines}

---
## INSTRUCCIONES DE FORMATO

Genera 4 secciones con estos marcadores exactos. Cada sección: 3-4 párrafos fluidos,
tono analítico pero accesible, usa los datos concretos para ilustrar los puntos.
NO uses bullets ni listas — solo prosa narrativa de alta calidad.

###SHAP###
[Narrativa sobre qué factores socioeconómicos determinan el puntaje ICFES.
Cuenta la historia de qué revela el modelo XGBoost: qué pesa más, qué sorprende,
qué implica para política pública. El R²={model_r2:.2f} tiene una implicación
poderosa — ¿qué explica el otro {(1-model_r2)*100:.0f}%?
Menciona la brecha de estrato de forma evocadora.]

###CLUSTERS###
[Narrativa sobre los 5 arquetipos de colegios colombianos.
Dale vida a cada cluster: quiénes son los "Héroes Silenciosos", qué define a los
"Rurales en Riesgo", qué separa a los colegios de élite del resto.
Usa los datos de NBI, internet y puntaje para pintar un cuadro sociológico.
Termina con la pregunta: ¿qué separa a un colegio de uno y otro lado?]

###RIESGO###
[Narrativa sobre el sistema de alerta temprana de riesgo de declive.
Interpreta qué significa que X colegios estén en riesgo alto.
¿Qué patrones comparten? ¿Qué intervenciones sugiere el modelo?
Usa los colegios del top 5 para ilustrar (sin estigmatizar).
Convierte el análisis probabilístico en una narrativa de urgencia y oportunidad.]

###OPORTUNIDAD###
[Narrativa sobre los colegios que superan su predicción de inglés B1.
Estos son los "casos imposibles según el modelo" — contexto difícil pero
resultados excepcionales. ¿Qué hace especiales a estos colegios?
¿Qué lecciones replicables hay aquí para la política educativa colombiana?
Termina con un mensaje esperanzador sobre lo que es posible.]
"""
    return prompt


# ---------------------------------------------------------------------------
# 3. Llamada a Claude API
# ---------------------------------------------------------------------------

def _get_client():
    import anthropic
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _llamar_api(prompt: str):
    client = _get_client()
    message = client.messages.create(
        model=MODEL_IA,
        max_tokens=MAX_TOKENS,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return (
        message.content[0].text,
        message.usage.input_tokens,
        message.usage.output_tokens,
    )


# ---------------------------------------------------------------------------
# 4. Parseo de secciones
# ---------------------------------------------------------------------------

def _parse_sections(text: str) -> dict:
    markers = ['SHAP', 'CLUSTERS', 'RIESGO', 'OPORTUNIDAD']
    sections = {}
    for i, marker in enumerate(markers):
        next_marker = markers[i + 1] if i + 1 < len(markers) else None
        pattern = (
            rf'###{marker}###\s*(.*?)(?=###{next_marker}###|$)'
            if next_marker
            else rf'###{marker}###\s*(.*?)$'
        )
        m = re.search(pattern, text, re.DOTALL)
        sections[marker.lower()] = m.group(1).strip() if m else ''
    return sections


# ---------------------------------------------------------------------------
# 5. Guardado en PostgreSQL
# ---------------------------------------------------------------------------

def _guardar(ano: int, analisis_md: str, sections: dict,
             tokens_in: int, tokens_out: int):
    from icfes_dashboard.models import MlAnalisisIA

    # Archivar análisis activos anteriores
    MlAnalisisIA.objects.filter(
        ano_referencia=ano, estado=MlAnalisisIA.ESTADO_ACTIVO
    ).update(estado=MlAnalisisIA.ESTADO_ARCHIVADO)

    return MlAnalisisIA.objects.create(
        ano_referencia=ano,
        estado=MlAnalisisIA.ESTADO_ACTIVO,
        analisis_md=analisis_md,
        shap_narrative=sections.get('shap', ''),
        clusters_narrative=sections.get('clusters', ''),
        riesgo_narrative=sections.get('riesgo', ''),
        oportunidad_narrative=sections.get('oportunidad', ''),
        modelo_ia=MODEL_IA,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Genera análisis narrativo IA de los modelos ML y lo guarda en PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument('--ano', type=int, default=DEFAULT_ANO)
        parser.add_argument('--forzar', action='store_true',
                            help='Regenerar aunque ya exista análisis activo')

    def handle(self, *args, **options):
        from icfes_dashboard.models import MlAnalisisIA

        ano    = options['ano']
        forzar = options['forzar']

        self.stdout.write(f'\nGenerando análisis IA — Modelos ML (año {ano})\n')

        # Verificar si ya existe
        if not forzar:
            exists = MlAnalisisIA.objects.filter(
                ano_referencia=ano, estado=MlAnalisisIA.ESTADO_ACTIVO
            ).exists()
            if exists:
                self.stdout.write(self.style.WARNING(
                    '  Ya existe análisis activo. Usa --forzar para regenerar.'
                ))
                return

        # Verificar API key
        if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
            self.stdout.write(self.style.ERROR(
                '  ERROR: ANTHROPIC_API_KEY no configurada.'
            ))
            return

        # 1. Extraer datos
        self.stdout.write('  1/4 Extrayendo datos de DuckDB...')
        try:
            data = _get_ml_data(ano)
            self.stdout.write(
                f"       SHAP: {len(data['shap'])} features | "
                f"Clusters: {len(data['clusters'])} | "
                f"Riesgo top: {len(data['riesgo_top'])}"
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ERROR extrayendo datos: {e}'))
            return

        # 2. Construir prompt
        self.stdout.write('  2/4 Construyendo prompt...')
        prompt = _build_prompt(data, ano)

        # 3. Llamar API
        self.stdout.write(f'  3/4 Llamando a {MODEL_IA}...')
        try:
            analisis_md, tokens_in, tokens_out = _llamar_api(prompt)
            self.stdout.write(
                f'       Tokens: {tokens_in} entrada / {tokens_out} salida'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ERROR en API: {e}'))
            return

        # 4. Parsear y guardar
        self.stdout.write('  4/4 Parseando secciones y guardando...')
        sections = _parse_sections(analisis_md)
        obj = _guardar(ano, analisis_md, sections, tokens_in, tokens_out)

        self.stdout.write(self.style.SUCCESS(
            f'\n  OK: MlAnalisisIA id={obj.pk} guardado '
            f'({tokens_out} tokens, {len(analisis_md)} chars)\n'
        ))
        for key in ['shap', 'clusters', 'riesgo', 'oportunidad']:
            n = len(sections.get(key, ''))
            self.stdout.write(f'     {key}: {n} chars')
