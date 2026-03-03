"""
Vistas para el Dashboard de IA & Modelos ML.

Endpoints:
  GET /icfes/ml/                        → página principal
  GET /icfes/api/ml/shap/               → SHAP importances + partial dependence estrato
  GET /icfes/api/ml/social-clusters/    → arquetipos sociales (clusters + scatter PCA)
  GET /icfes/api/ml/riesgo/             → colegios en riesgo de declive
  GET /icfes/api/ml/b1-overperformers/  → colegios que superan predicción B1
"""
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .db_utils import get_duckdb_connection, resolve_schema

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60  # 1 hora


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------

@login_required
def ml_dashboard(request):
    return render(request, 'icfes_dashboard/pages/dashboard-ml.html', {})


# ---------------------------------------------------------------------------
# API — SHAP importances + partial dependence estrato
# ---------------------------------------------------------------------------

@login_required
@require_GET
def api_ml_shap(request):
    try:
        q_imp = resolve_schema("""
            SELECT feature, label, icono, shap_pts, rank, model_mae, model_r2
            FROM gold.fct_ml_shap_importances
            ORDER BY rank
        """)
        q_partial = resolve_schema("""
            SELECT estrato, orden, puntaje_predicho
            FROM gold.fct_ml_shap_partial_estrato
            ORDER BY orden
        """)
        with get_duckdb_connection() as con:
            rows_imp = con.execute(q_imp).fetchall()
            rows_par = con.execute(q_partial).fetchall()

        importances = [
            {
                'feature': r[0], 'label': r[1], 'icono': r[2],
                'shap_pts': round(float(r[3]), 2), 'rank': int(r[4]),
                'model_mae': round(float(r[5]), 2), 'model_r2': round(float(r[6]), 3),
            }
            for r in rows_imp
        ]
        partial = [
            {'estrato': r[0], 'orden': int(r[1]), 'puntaje_predicho': round(float(r[2]), 1)}
            for r in rows_par
        ]
        return JsonResponse({'importances': importances, 'partial_estrato': partial})

    except Exception as e:
        logger.warning("api_ml_shap: tablas aún no generadas — %s", e)
        return JsonResponse({'importances': [], 'partial_estrato': [], 'pending': True})


# ---------------------------------------------------------------------------
# API — Social clusters (arquetipos por contexto socioeconómico)
# ---------------------------------------------------------------------------

@login_required
@require_GET
def api_ml_social_clusters(request):
    try:
        q_profiles = resolve_schema("""
            SELECT
                cluster_id,
                cluster_name,
                cluster_color,
                cluster_descripcion,
                COUNT(*)                          AS n_colegios,
                ROUND(AVG(avg_global), 1)         AS avg_global,
                ROUND(AVG(avg_ingles), 1)         AS avg_ingles,
                ROUND(AVG(pct_nbi), 1)            AS pct_nbi,
                ROUND(AVG(avg_estrato), 2)        AS avg_estrato,
                ROUND(AVG(pct_internet), 1)       AS pct_internet,
                ROUND(MIN(silhouette_score), 3)   AS silhouette_score,
                ROUND(MIN(pca_var_pc1), 1)        AS pca_var_pc1,
                ROUND(MIN(pca_var_pc2), 1)        AS pca_var_pc2
            FROM gold.fct_ml_social_clusters
            GROUP BY cluster_id, cluster_name, cluster_color, cluster_descripcion
            ORDER BY avg_global DESC
        """)
        q_scatter = resolve_schema("""
            SELECT
                colegio_bk, nombre_colegio, departamento,
                ROUND(pc1, 3) AS pc1, ROUND(pc2, 3) AS pc2,
                cluster_id, cluster_name, cluster_color,
                ROUND(avg_global, 1) AS avg_global,
                ROUND(pct_nbi, 1) AS pct_nbi
            FROM gold.fct_ml_social_clusters
            ORDER BY RANDOM()
            LIMIT 3000
        """)
        with get_duckdb_connection() as con:
            rows_p = con.execute(q_profiles).fetchall()
            rows_s = con.execute(q_scatter).fetchall()

        profiles = [
            {
                'cluster_id': int(r[0]), 'cluster_name': r[1],
                'cluster_color': r[2], 'cluster_descripcion': r[3],
                'n_colegios': int(r[4]), 'avg_global': float(r[5]),
                'avg_ingles': float(r[6]), 'pct_nbi': float(r[7]),
                'avg_estrato': float(r[8]), 'pct_internet': float(r[9]),
                'silhouette_score': float(r[10]),
                'pca_var_pc1': float(r[11]), 'pca_var_pc2': float(r[12]),
            }
            for r in rows_p
        ]
        scatter = [
            {
                'colegio_bk': r[0], 'nombre': r[1], 'departamento': r[2],
                'pc1': float(r[3]), 'pc2': float(r[4]),
                'cluster_id': int(r[5]), 'cluster_name': r[6], 'color': r[7],
                'avg_global': float(r[8]), 'pct_nbi': float(r[9]),
            }
            for r in rows_s
        ]
        return JsonResponse({'profiles': profiles, 'scatter': scatter})

    except Exception as e:
        logger.warning("api_ml_social_clusters: tablas aún no generadas — %s", e)
        return JsonResponse({'profiles': [], 'scatter': [], 'pending': True})


# ---------------------------------------------------------------------------
# API — Colegios en riesgo de declive
# ---------------------------------------------------------------------------

@login_required
@require_GET
def api_ml_riesgo(request):
    try:
        q = resolve_schema("""
            SELECT
                nombre_colegio, sector, departamento,
                ROUND(avg_punt_global_actual, 1) AS puntaje,
                ROUND(prob_declive * 100, 1)     AS prob_declive_pct,
                nivel_riesgo, factores_principales
            FROM gold.fct_riesgo_colegios
            WHERE nivel_riesgo IN ('Alto', 'Medio')
            ORDER BY prob_declive DESC
            LIMIT 100
        """)
        q_stats = resolve_schema("""
            SELECT
                nivel_riesgo,
                COUNT(*) AS n
            FROM gold.fct_riesgo_colegios
            GROUP BY nivel_riesgo
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(q).fetchall()
            stats_rows = con.execute(q_stats).fetchall()

        colegios = [
            {
                'nombre': r[0], 'sector': r[1], 'departamento': r[2],
                'puntaje': float(r[3]), 'prob_declive_pct': float(r[4]),
                'nivel_riesgo': r[5], 'factores': r[6],
            }
            for r in rows
        ]
        stats = {r[0]: int(r[1]) for r in stats_rows}
        return JsonResponse({'colegios': colegios, 'stats': stats})

    except Exception as e:
        logger.error("api_ml_riesgo error: %s", e)
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# API — Colegios que superan predicción B1 inglés
# ---------------------------------------------------------------------------

@login_required
@require_GET
def api_ml_b1(request):
    try:
        sector = request.GET.get('sector', 'OFICIAL')
        q = resolve_schema(f"""
            SELECT
                nombre_colegio, sector, departamento,
                ROUND(ing_pct_b1, 1)        AS pct_b1_real,
                ROUND(pct_b1_esperado, 1)   AS pct_b1_esperado,
                ROUND(exceso_b1, 1)         AS exceso_b1,
                clasificacion_b1,
                total_estudiantes,
                ROUND(model_r2, 3)          AS model_r2,
                ROUND(model_mae, 2)         AS model_mae
            FROM gold.fct_ml_predictor_b1
            WHERE sector ILIKE '%{sector}%'
              AND clasificacion_b1 IN ('Excepcional B1+', 'Notable B1+')
            ORDER BY exceso_b1 DESC
            LIMIT 80
        """)
        q_dist = resolve_schema("""
            SELECT clasificacion_b1, COUNT(*) AS n
            FROM gold.fct_ml_predictor_b1
            GROUP BY clasificacion_b1
            ORDER BY n DESC
        """)
        with get_duckdb_connection() as con:
            rows = con.execute(q).fetchall()
            dist_rows = con.execute(q_dist).fetchall()

        colegios = [
            {
                'nombre': r[0], 'sector': r[1], 'departamento': r[2],
                'pct_b1_real': float(r[3]), 'pct_b1_esperado': float(r[4]),
                'exceso_b1': float(r[5]), 'clasificacion': r[6],
                'n_estudiantes': int(r[7]),
                'model_r2': float(r[8]), 'model_mae': float(r[9]),
            }
            for r in rows
        ]
        distribucion = [{'clasificacion': r[0], 'n': int(r[1])} for r in dist_rows]
        return JsonResponse({'colegios': colegios, 'distribucion': distribucion})

    except Exception as e:
        logger.error("api_ml_b1 error: %s", e)
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# API — Análisis narrativo IA de modelos ML
# ---------------------------------------------------------------------------

@login_required
@require_GET
def api_ml_ia_analisis(request):
    """Devuelve el análisis narrativo IA pre-generado (MlAnalisisIA)."""
    from .models import MlAnalisisIA
    ano = int(request.GET.get('ano', 2024))
    try:
        obj = MlAnalisisIA.objects.filter(
            ano_referencia=ano, estado=MlAnalisisIA.ESTADO_ACTIVO
        ).latest('fecha_generacion')
        return JsonResponse({
            'disponible': True,
            'ano_referencia': obj.ano_referencia,
            'shap_narrative': obj.shap_narrative,
            'clusters_narrative': obj.clusters_narrative,
            'riesgo_narrative': obj.riesgo_narrative,
            'oportunidad_narrative': obj.oportunidad_narrative,
            'analisis_md': obj.analisis_md,
            'modelo_ia': obj.modelo_ia,
            'fecha_generacion': obj.fecha_generacion.isoformat(),
            'tokens_output': obj.tokens_output,
        })
    except MlAnalisisIA.DoesNotExist:
        return JsonResponse({'disponible': False})
    except Exception as e:
        logger.warning("api_ml_ia_analisis: %s", e)
        return JsonResponse({'disponible': False})


# ---------------------------------------------------------------------------
# API — Generar análisis IA bajo demanda (staff only)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def api_ml_generate_ia(request):
    """Dispara la generación del análisis narrativo IA (solo staff)."""
    if not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Permiso denegado'}, status=403)

    from django.conf import settings
    if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
        return JsonResponse({'ok': False, 'error': 'ANTHROPIC_API_KEY no configurada'}, status=400)

    from .management.commands.generate_ml_ia_analisis import (
        _get_ml_data, _build_prompt, _llamar_api, _parse_sections, _guardar,
    )
    from .models import MlAnalisisIA

    ano    = int(request.POST.get('ano', 2024))
    forzar = request.POST.get('forzar', '') in ('1', 'true', 'yes')

    if not forzar:
        exists = MlAnalisisIA.objects.filter(
            ano_referencia=ano, estado=MlAnalisisIA.ESTADO_ACTIVO
        ).exists()
        if exists:
            return JsonResponse({
                'ok': False,
                'error': 'Ya existe análisis activo. Envía forzar=1 para regenerar.',
            })

    try:
        data        = _get_ml_data(ano)
        prompt      = _build_prompt(data, ano)
        analisis_md, tokens_in, tokens_out = _llamar_api(prompt)
        sections    = _parse_sections(analisis_md)
        obj         = _guardar(ano, analisis_md, sections, tokens_in, tokens_out)
        logger.info("api_ml_generate_ia: ok id=%s tokens_out=%s", obj.pk, tokens_out)
        return JsonResponse({'ok': True, 'id': obj.pk, 'tokens': tokens_out})
    except Exception as e:
        logger.error("api_ml_generate_ia error: %s", e)
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
