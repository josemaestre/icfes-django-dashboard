"""
Dashboard "Mi Colegio" — Diagnóstico Personalizado por Colegio
==============================================================
Permite a un estudiante seleccionar su colegio (guardado en session) y ver
un diagnóstico completo: vs nacional, vs departamento, fortalezas/brechas,
trayectoria, potencial inglés ML y recomendaciones basadas en factores asociados.

Endpoints:
    GET  /dashboard-icfes/mi-colegio/                     → página principal
    POST /dashboard-icfes/mi-colegio/seleccionar/         → guarda colegio en session
    GET  /dashboard-icfes/mi-colegio/limpiar/             → limpia session → redirect
    GET  /dashboard-icfes/api/colegio/buscar/             → autocomplete por nombre
    GET  /dashboard-icfes/api/colegio/<sk>/ml-diagnostico/ → ML data (potencial+cluster)
    GET  /dashboard-icfes/api/colegio/<sk>/recomendaciones/ → factores asociados
"""

import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .db_utils import execute_query

SESSION_KEY = "mi_colegio"


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------

def mi_colegio_page(request):
    """Vista principal: buscador si no hay colegio en session, dashboard si hay."""
    mi_colegio = request.session.get(SESSION_KEY)
    return render(request, "icfes_dashboard/pages/mi-colegio.html",
                  {"mi_colegio": mi_colegio})


# ---------------------------------------------------------------------------
# Gestión de session
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def mi_colegio_seleccionar(request):
    """Guarda el colegio seleccionado en session y redirige al dashboard."""
    try:
        data = json.loads(request.body)
        colegio_sk  = str(data.get("colegio_sk", "")).strip()
        colegio_bk  = str(data.get("colegio_bk", "")).strip()
        nombre      = str(data.get("nombre_colegio", "")).strip()
        departamento = str(data.get("departamento", "")).strip()
        municipio   = str(data.get("municipio", "")).strip()
        sector      = str(data.get("sector", "")).strip()

        if not colegio_sk or not colegio_bk or not nombre:
            return JsonResponse({"error": "Datos incompletos"}, status=400)

        request.session[SESSION_KEY] = {
            "colegio_sk":   colegio_sk,
            "colegio_bk":   colegio_bk,
            "nombre_colegio": nombre,
            "departamento": departamento,
            "municipio":    municipio,
            "sector":       sector,
        }
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def mi_colegio_limpiar(request):
    """Elimina el colegio de session y vuelve al buscador."""
    request.session.pop(SESSION_KEY, None)
    return redirect("icfes_dashboard:mi_colegio")


# ---------------------------------------------------------------------------
# API: autocomplete de búsqueda
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def api_colegio_buscar(request):
    """Autocomplete: devuelve hasta 10 colegios que coincidan con ?q=<texto>."""
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse([], safe=False)

    query = """
        SELECT s.codigo      AS colegio_bk,
               s.nombre_colegio,
               s.departamento,
               s.municipio,
               s.sector,
               s.slug,
               c.colegio_sk
        FROM gold.dim_colegios_slugs s
        JOIN gold.dim_colegios c ON c.colegio_bk = s.codigo
        WHERE LOWER(s.nombre_colegio) LIKE LOWER(? || '%')
           OR LOWER(s.nombre_colegio) LIKE LOWER('%' || ? || '%')
        ORDER BY
            CASE WHEN LOWER(s.nombre_colegio) LIKE LOWER(? || '%') THEN 0 ELSE 1 END,
            s.nombre_colegio
        LIMIT 10
    """
    df = execute_query(query, params=[q, q, q])
    return JsonResponse(df.to_dict(orient="records"), safe=False)


# ---------------------------------------------------------------------------
# API: ML Diagnóstico (potencial inglés + B1+ + cluster transformador)
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def api_colegio_ml_diagnostico(request, colegio_sk):
    """
    Combina ML-2 (potencial inglés), ML-1 (predictor B1+) y ML-3 (cluster
    transformador) para el colegio dado.
    """
    if not colegio_sk or not str(colegio_sk).replace("-", "").replace("_", "").isalnum():
        return JsonResponse({"error": "colegio_sk inválido"}, status=400)

    colegio_sk_str = str(colegio_sk)

    # ML-2: potencial inglés (disponible en dev y prod)
    query_potencial = """
        SELECT colegio_bk, avg_ingles, score_ingles_esperado, exceso_ingles,
               percentil_exceso_ingles, ranking_exceso_nacional,
               ranking_exceso_depto, clasificacion_ingles
        FROM gold.fct_potencial_ingles
        WHERE colegio_bk = (
            SELECT colegio_bk FROM gold.dim_colegios
            WHERE colegio_sk = ? LIMIT 1
        )
    """
    df_potencial = execute_query(query_potencial, params=[colegio_sk_str])
    potencial = df_potencial.to_dict(orient="records")[0] if not df_potencial.empty else None

    # ML-1: predictor B1+ (solo en prod; graceful si no existe en dev)
    try:
        query_b1 = """
            SELECT ing_pct_b1, pct_b1_esperado, exceso_b1,
                   percentil_exceso_b1, clasificacion_b1
            FROM gold.fct_ml_predictor_b1
            WHERE colegio_bk = (
                SELECT colegio_bk FROM gold.dim_colegios
                WHERE colegio_sk = ? LIMIT 1
            )
        """
        df_b1 = execute_query(query_b1, params=[colegio_sk_str])
        if potencial and not df_b1.empty:
            potencial.update(df_b1.to_dict(orient="records")[0])
    except Exception:
        pass

    # ML-3: cluster transformador (solo en prod; graceful si no existe en dev)
    try:
        query_cluster = """
            SELECT cluster_label, cluster_id,
                   nivel_actual, nivel_base, tendencia, mejora_3y, volatilidad,
                   anos_con_dato
            FROM gold.fct_ml_clusters_transformadores
            WHERE colegio_sk = ?
            LIMIT 1
        """
        df_cluster = execute_query(query_cluster, params=[colegio_sk_str])
        cluster = df_cluster.to_dict(orient="records")[0] if not df_cluster.empty else None
    except Exception:
        cluster = None

    result = {
        "potencial_ingles": potencial,
        "cluster_transformador": cluster,
    }
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# API: Recomendaciones (materia débil + factores asociados de impacto)
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def api_colegio_recomendaciones(request, colegio_sk):
    """
    Devuelve la recomendación principal del colegio (fortalezas_debilidades)
    y los top factores asociados con mayor brecha vs promedio nacional.
    """
    if not colegio_sk or not str(colegio_sk).replace("-", "").replace("_", "").isalnum():
        return JsonResponse({"error": "colegio_sk inválido"}, status=400)

    colegio_sk_str = str(colegio_sk)

    # Recomendación del colegio
    query_rec = """
        SELECT materia_mas_debil, materia_mas_fuerte,
               recomendacion_principal, urgencia_mejora,
               clasificacion_general, perfil_rendimiento
        FROM gold.fct_colegio_fortalezas_debilidades
        WHERE colegio_sk = ?
        ORDER BY ano DESC
        LIMIT 1
    """
    df_rec = execute_query(query_rec, params=[colegio_sk_str])

    # Top factores con mayor impacto positivo (año 2024) — solo en prod
    try:
        query_factores = """
            SELECT factor, valor_factor, avg_ingles, brecha_vs_factor, n_estudiantes
            FROM gold.fct_factores_asociados
            WHERE ano = '2024'
              AND brecha_vs_factor > 5
            ORDER BY brecha_vs_factor DESC
            LIMIT 6
        """
        df_factores = execute_query(query_factores)
        factores_impacto = df_factores.to_dict(orient="records")
    except Exception:
        factores_impacto = []

    result = {
        "recomendacion": df_rec.to_dict(orient="records")[0] if not df_rec.empty else None,
        "factores_impacto": factores_impacto,
    }
    return JsonResponse(result)
