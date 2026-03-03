"""
Pipeline de entrenamiento para los dos modelos ICFES ML:
  1. XGBoost predictor de puntaje global + SHAP nativo (pred_contribs)
  2. K-Means clustering de colegios + PCA 2D para visualización

Los artefactos se guardan como JSON en icfes_dashboard/ml/artifacts/.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import mean_absolute_error, r2_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .feature_engineering import (
    FEATURE_COLS,
    FEATURE_ICONS,
    FEATURE_LABELS,
    encode_features,
)

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).parent / 'artifacts'
ARTIFACTS_DIR.mkdir(exist_ok=True)

# ── Cluster names asignados post-hoc por centroides ──────────────────────────
# El script detecta automáticamente cuál cluster es cuál basándose en avg_global
# Estos nombres se asignan por orden de puntaje promedio (desc)
CLUSTER_NAMES_BY_RANK = [
    {'nombre': 'Élite Privados',      'icono': '🏆', 'color': '#1abc9c',
     'descripcion': 'Colegios privados de alto estrato con puntajes sobresalientes'},
    {'nombre': 'Buenos Públicos',     'icono': '⭐', 'color': '#4fc6e1',
     'descripcion': 'Colegios oficiales urbanos con rendimiento sólido'},
    {'nombre': 'Héroes Silenciosos',  'icono': '💪', 'color': '#f7b731',
     'descripcion': 'Colegios que superan lo esperado dado su contexto socioeconómico'},
    {'nombre': 'Públicos Urbanos',    'icono': '🏫', 'color': '#6c757d',
     'descripcion': 'Colegios oficiales urbanos de rendimiento promedio'},
    {'nombre': 'Rurales en Riesgo',   'icono': '⚠️',  'color': '#f1556c',
     'descripcion': 'Colegios rurales con alta pobreza y puntajes bajos'},
]

N_CLUSTERS = 5


# ══════════════════════════════════════════════════════════════════════════════
# MODELO 1: XGBoost Predictor + SHAP nativo
# ══════════════════════════════════════════════════════════════════════════════

def train_predictor(df: pd.DataFrame) -> dict:
    """
    Entrena XGBoost sobre df, calcula SHAP vía pred_contribs nativo,
    y guarda:
      - artifacts/shap_importances.json
      - artifacts/shap_partial_estrato.json
    Devuelve: {'mae': float, 'r2': float, 'n_rows': int}
    """
    logger.info(f'[Predictor] Preparando features sobre {len(df):,} filas...')
    X = encode_features(df)
    y = df['punt_global'].astype(float)

    # Eliminar filas con target nulo
    mask = y.notna() & (y > 0)
    X, y = X[mask], y[mask]
    logger.info(f'[Predictor] {len(X):,} filas válidas tras filtrar nulos.')

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42
    )

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_COLS)
    dtest  = xgb.DMatrix(X_test,  label=y_test,  feature_names=FEATURE_COLS)

    params = {
        'objective':        'reg:squarederror',
        'n_estimators':     300,
        'max_depth':        6,
        'learning_rate':    0.1,
        'subsample':        0.8,
        'colsample_bytree': 0.8,
        'seed':             42,
        'nthread':          -1,
        'verbosity':        0,
    }
    logger.info('[Predictor] Entrenando XGBoost...')
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=300,
        evals=[(dtest, 'test')],
        verbose_eval=50,
    )

    # ── Métricas ──────────────────────────────────────────────────────────────
    y_pred = model.predict(dtest)
    mae    = round(float(mean_absolute_error(y_test, y_pred)), 2)
    r2     = round(float(r2_score(y_test, y_pred)), 4)
    logger.info(f'[Predictor] MAE={mae} | R²={r2}')

    # ── SHAP via pred_contribs (TreeSHAP nativo en XGBoost) ──────────────────
    logger.info('[Predictor] Calculando SHAP sobre muestra de 50K filas...')
    sample_size = min(50_000, len(X_train))
    X_sample    = X_train.sample(sample_size, random_state=42)
    d_sample    = xgb.DMatrix(X_sample, feature_names=FEATURE_COLS)

    # pred_contribs devuelve (n_samples, n_features + 1): última col = bias
    shap_matrix = model.predict(d_sample, pred_contribs=True)
    shap_values = shap_matrix[:, :-1]  # quitar bias

    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    importances = []
    for i, col in enumerate(FEATURE_COLS):
        importances.append({
            'feature': col,
            'label':   FEATURE_LABELS[col],
            'icono':   FEATURE_ICONS[col],
            'shap_pts': round(float(mean_abs_shap[i]), 3),
        })
    importances.sort(key=lambda x: x['shap_pts'], reverse=True)

    _save_json('shap_importances.json', importances)
    logger.info(f'[Predictor] Top feature: {importances[0]["label"]} = {importances[0]["shap_pts"]} pts')

    # ── Partial dependence: estrato E0 → E6 ──────────────────────────────────
    logger.info('[Predictor] Calculando partial dependence para estrato...')
    medians      = X_sample.median()
    partial_rows = []
    for estrato_val in range(7):  # 0=Sin, 1=E1...6=E6
        row = medians.copy()
        row['fami_estratovivienda'] = estrato_val
        partial_rows.append(row)

    d_partial  = xgb.DMatrix(pd.DataFrame(partial_rows), feature_names=FEATURE_COLS)
    pred_vals  = model.predict(d_partial)
    estrato_labels = ['Sin Estrato', 'Estrato 1', 'Estrato 2', 'Estrato 3',
                      'Estrato 4', 'Estrato 5', 'Estrato 6']
    partial_data = [
        {'estrato': estrato_labels[i], 'orden': i, 'puntaje_predicho': round(float(pred_vals[i]), 1)}
        for i in range(7)
    ]
    _save_json('shap_partial_estrato.json', partial_data)

    return {'mae': mae, 'r2': r2, 'n_rows': len(X)}


# ══════════════════════════════════════════════════════════════════════════════
# MODELO 3: K-Means Clustering de Colegios + PCA 2D
# ══════════════════════════════════════════════════════════════════════════════

CLUSTER_FEATURES = [
    'avg_global', 'avg_ingles', 'avg_estrato', 'pct_nbi',
    'es_privado', 'n_estudiantes_log',
]


def train_clustering(df_colegios: pd.DataFrame) -> dict:
    """
    Agrupa colegios en N_CLUSTERS arquetipos usando K-Means sobre
    métricas normalizadas. PCA 2D para scatter de visualización.
    Guarda:
      - artifacts/cluster_profiles.json
      - artifacts/cluster_schools.json
    Devuelve: {'silhouette': float, 'n_colegios': int}
    """
    logger.info(f'[Clustering] {len(df_colegios):,} colegios recibidos.')

    df = df_colegios.copy()
    df = df.dropna(subset=['avg_global'])
    df['es_privado']       = (df['sector'].str.upper().str.contains('NO OFICIAL', na=False)).astype(float)
    df['n_estudiantes_log'] = np.log1p(df['n_estudiantes'].fillna(1))
    df['avg_estrato']       = df['avg_estrato'].fillna(df['avg_estrato'].median())
    df['pct_nbi']           = df['pct_nbi'].fillna(df['pct_nbi'].median())
    df['avg_ingles']        = df['avg_ingles'].fillna(df['avg_ingles'].median())

    X_raw = df[CLUSTER_FEATURES].astype(float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    # ── K-Means ───────────────────────────────────────────────────────────────
    logger.info(f'[Clustering] Ajustando K-Means con K={N_CLUSTERS}...')
    km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=20)
    df['cluster_id'] = km.fit_predict(X_scaled)

    sil = round(float(silhouette_score(X_scaled, df['cluster_id'])), 3)
    logger.info(f'[Clustering] Silhouette score: {sil}')

    # ── PCA 2D ────────────────────────────────────────────────────────────────
    pca = PCA(n_components=2, random_state=42)
    pcs = pca.fit_transform(X_scaled)
    df['pc1'] = np.round(pcs[:, 0], 3)
    df['pc2'] = np.round(pcs[:, 1], 3)
    var_exp = np.round(pca.explained_variance_ratio_ * 100, 1)
    logger.info(f'[Clustering] PCA varianza explicada: PC1={var_exp[0]}%, PC2={var_exp[1]}%')

    # ── Asignar nombres a clusters por puntaje promedio desc ─────────────────
    cluster_avgs = df.groupby('cluster_id')['avg_global'].mean().sort_values(ascending=False)
    rank_to_name = {}
    for rank, cid in enumerate(cluster_avgs.index):
        rank_to_name[cid] = CLUSTER_NAMES_BY_RANK[rank]

    # ── Perfiles de cluster ───────────────────────────────────────────────────
    profiles = []
    for cid in range(N_CLUSTERS):
        sub = df[df['cluster_id'] == cid]
        info = rank_to_name[cid]
        profiles.append({
            'cluster_id':   int(cid),
            'nombre':       info['nombre'],
            'icono':        info['icono'],
            'color':        info['color'],
            'descripcion':  info['descripcion'],
            'n_colegios':   int(len(sub)),
            'avg_global':   round(float(sub['avg_global'].mean()), 1),
            'avg_ingles':   round(float(sub['avg_ingles'].mean()), 1),
            'avg_estrato':  round(float(sub['avg_estrato'].mean()), 2),
            'pct_nbi':      round(float(sub['pct_nbi'].mean()), 1),
            'pct_privados': round(float(sub['es_privado'].mean() * 100), 1),
            'mediana_est':  int(sub['n_estudiantes'].median()),
        })
    profiles.sort(key=lambda x: x['avg_global'], reverse=True)
    _save_json('cluster_profiles.json', {
        'profiles': profiles,
        'silhouette': sil,
        'pca_var_exp': [float(var_exp[0]), float(var_exp[1])],
    })

    # ── Scatter data (por colegio) ────────────────────────────────────────────
    scatter = []
    for _, row in df.iterrows():
        info = rank_to_name[int(row['cluster_id'])]
        scatter.append({
            'pc1':        float(row['pc1']),
            'pc2':        float(row['pc2']),
            'cluster_id': int(row['cluster_id']),
            'cluster_nombre': info['nombre'],
            'color':      info['color'],
            'nombre':     str(row.get('nombre', '')),
            'dpto':       str(row.get('dpto', '')),
            'avg_global': float(row['avg_global']),
            'avg_ingles': float(row.get('avg_ingles', 0)),
            'pct_nbi':    float(row['pct_nbi']),
            'avg_estrato': float(row['avg_estrato']),
        })
    _save_json('cluster_schools.json', scatter)
    logger.info(f'[Clustering] {len(scatter)} colegios guardados en scatter.')

    return {'silhouette': sil, 'n_colegios': len(df)}


# ── Helper ────────────────────────────────────────────────────────────────────

def _save_json(filename: str, data) -> None:
    path = ARTIFACTS_DIR / filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f'[Artifacts] Guardado: {path}')


def save_metadata(predictor_result: dict, clustering_result: dict) -> None:
    meta = {
        'fecha_entrenamiento': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'modelo_predictor': {
            'tipo': 'XGBoost (TreeSHAP nativo)',
            'mae':   predictor_result['mae'],
            'r2':    predictor_result['r2'],
            'n_rows_entrenamiento': predictor_result['n_rows'],
            'periodo': '2014-2024',
        },
        'modelo_clustering': {
            'tipo': f'K-Means (K={N_CLUSTERS}) + PCA 2D',
            'silhouette': clustering_result['silhouette'],
            'n_colegios': clustering_result['n_colegios'],
            'ano': '2024',
        },
    }
    _save_json('model_metadata.json', meta)
    logger.info('[Metadata] model_metadata.json guardado.')
