"""
Management command para entrenar los modelos ICFES ML:
  - Modelo 1: XGBoost predictor de punt_global + SHAP via pred_contribs
  - Modelo 3: K-Means clustering de colegios + PCA 2D

Uso:
  python manage.py train_icfes_models
  python manage.py train_icfes_models --only predictor
  python manage.py train_icfes_models --only clustering
"""
import logging
import time

from django.core.management.base import BaseCommand

from icfes_dashboard.db_utils import execute_query
from icfes_dashboard.ml.train_models import (
    save_metadata,
    train_clustering,
    train_predictor,
)

logger = logging.getLogger(__name__)

SQL_PREDICTOR = """
SELECT
    f.punt_global,
    f.fami_estratovivienda,
    f.fami_educacionmadre,
    f.fami_educacionpadre,
    f.fami_tieneinternet,
    f.fami_tienecomputador,
    f.fami_numlibros,
    f.fami_personashogar,
    f.fami_situacioneconomica,
    f.cole_naturaleza,
    f.cole_area_ubicacion,
    f.estu_genero,
    f.estu_horassemanatrabaja,
    f.estu_dedicacionlecturadiaria,
    CAST(f.ano AS INTEGER) AS ano,
    n.pct_nbi_total
FROM icfes_silver.icfes f
LEFT JOIN gold.dim_municipio_nbi n
    ON CAST(n.codigo_municipio AS VARCHAR) = SUBSTRING(f.cole_cod_dane_establecimiento, 1, 5)
WHERE CAST(f.ano AS INTEGER) >= 2014
  AND f.punt_global IS NOT NULL
  AND f.punt_global > 0
"""

SQL_CLUSTERING = """
SELECT
    f.colegio_bk,
    MIN(f.nombre_colegio)                       AS nombre,
    MIN(f.departamento)                         AS dpto,
    MIN(f.sector)                               AS sector,
    ROUND(AVG(f.avg_punt_global), 1)            AS avg_global,
    ROUND(AVG(f.avg_punt_ingles), 1)            AS avg_ingles,
    MAX(f.total_estudiantes)                    AS n_estudiantes,
    ROUND(AVG(n.pct_nbi_total), 1)             AS pct_nbi,
    ROUND(COALESCE(est.avg_estrato, 2.5), 2)   AS avg_estrato
FROM gold.fct_agg_colegios_ano f
LEFT JOIN gold.dim_municipio_nbi n
    ON CAST(n.codigo_municipio AS VARCHAR) = SUBSTRING(f.colegio_bk, 2, 5)
LEFT JOIN (
    SELECT
        cole_cod_dane_establecimiento,
        AVG(CASE fami_estratovivienda
            WHEN 'Estrato 1' THEN 1.0
            WHEN 'Estrato 2' THEN 2.0
            WHEN 'Estrato 3' THEN 3.0
            WHEN 'Estrato 4' THEN 4.0
            WHEN 'Estrato 5' THEN 5.0
            WHEN 'Estrato 6' THEN 6.0
            ELSE 0.0 END) AS avg_estrato
    FROM icfes_silver.icfes
    WHERE ano = '2024'
      AND fami_estratovivienda IS NOT NULL
      AND fami_estratovivienda != 'None'
    GROUP BY cole_cod_dane_establecimiento
) est ON 'c' || est.cole_cod_dane_establecimiento = f.colegio_bk
WHERE f.ano = '2024'
GROUP BY f.colegio_bk
HAVING AVG(f.avg_punt_global) > 0
   AND MAX(f.total_estudiantes) > 0
"""


class Command(BaseCommand):
    help = 'Entrena modelos XGBoost (predictor) y K-Means (clustering) con datos ICFES 2014-2024'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only',
            choices=['predictor', 'clustering'],
            help='Entrenar solo uno de los modelos (por defecto entrena ambos)',
        )

    def handle(self, *args, **options):
        only = options.get('only')
        t0 = time.time()

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  ICFES ML Training Pipeline'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        predictor_result  = None
        clustering_result = None

        # ── MODELO 1: XGBoost Predictor ───────────────────────────────────────
        if only in (None, 'predictor'):
            self.stdout.write('\n📥 Cargando datos para el predictor (2014-2024)...')
            t1 = time.time()
            df_pred = execute_query(SQL_PREDICTOR)
            self.stdout.write(f'   → {len(df_pred):,} filas cargadas en {time.time()-t1:.1f}s')

            self.stdout.write('\n🤖 Entrenando XGBoost + SHAP...')
            t1 = time.time()
            predictor_result = train_predictor(df_pred)
            elapsed = time.time() - t1
            self.stdout.write(
                self.style.SUCCESS(
                    f'   ✅ MAE={predictor_result["mae"]} pts  |  '
                    f'R²={predictor_result["r2"]}  |  '
                    f'{elapsed:.0f}s'
                )
            )

        # ── MODELO 3: K-Means Clustering ──────────────────────────────────────
        if only in (None, 'clustering'):
            self.stdout.write('\n📥 Cargando datos para clustering de colegios (2024)...')
            t1 = time.time()
            df_colegios = execute_query(SQL_CLUSTERING)
            self.stdout.write(f'   → {len(df_colegios):,} colegios cargados en {time.time()-t1:.1f}s')

            self.stdout.write('\n🔵 Entrenando K-Means + PCA...')
            t1 = time.time()
            clustering_result = train_clustering(df_colegios)
            elapsed = time.time() - t1
            self.stdout.write(
                self.style.SUCCESS(
                    f'   ✅ Silhouette={clustering_result["silhouette"]}  |  '
                    f'{clustering_result["n_colegios"]:,} colegios  |  '
                    f'{elapsed:.1f}s'
                )
            )

        # ── Metadata ──────────────────────────────────────────────────────────
        if predictor_result and clustering_result:
            save_metadata(predictor_result, clustering_result)

        total = time.time() - t0
        self.stdout.write(
            self.style.SUCCESS(f'\n🏁 Entrenamiento completo en {total/60:.1f} minutos.')
        )
        self.stdout.write('   Artefactos guardados en: icfes_dashboard/ml/artifacts/')
