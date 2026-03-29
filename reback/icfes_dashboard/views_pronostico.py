"""
Vistas y API para el módulo de Pronóstico a 5 Años.
===================================================
Proporciona la página principal del pronóstico y la API que combina
el histórico real con la proyección del modelo (fct_pronostico_colegio).
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from reback.users.decorators import subscription_required
from .db_utils import execute_query

from reback.users.subscription_models import UserSubscription

@login_required
def pronostico_page(request):
    """Renderiza la página principal del pronóstico interactivo."""
    # Obtenemos el tier de la suscripción directamente de la base de datos
    # ya que el middleware sólo aplica a endpoints de API de ICFES.
    tier = 'free'
    if request.user.is_superuser:
        tier = 'institucional'
    else:
        try:
            sub = UserSubscription.objects.select_related('plan').get(user=request.user, is_active=True)
            tier = sub.plan.tier
        except UserSubscription.DoesNotExist:
            pass
            
    context = {
        "is_pro": tier in ['pro', 'institucional', 'basic', 'premium', 'enterprise'],
        "tier": tier,
    }
    return render(request, "icfes_dashboard/pages/pronostico-colegio.html", context)


@login_required
@subscription_required(tier='pro')
@require_http_methods(["GET"])
def api_colegio_pronostico(request, colegio_sk):
    """
    Retorna la serie de tiempo (histórico + pronóstico) combinada
    para un colegio específico.
    """
    if not colegio_sk or not str(colegio_sk).replace("-", "").replace("_", "").isalnum():
        return JsonResponse({"error": "colegio_sk inválido"}, status=400)

    colegio_sk_str = str(colegio_sk)

    # 1. Traer datos históricos (2015-2024)
    query_hist = """
        SELECT
            CAST(ano AS INTEGER) as ano,
            ROUND(avg_punt_global, 1) as global,
            ROUND(avg_punt_matematicas, 1) as matematicas,
            ROUND(avg_punt_lectura_critica, 1) as lectura_critica,
            ROUND(avg_punt_c_naturales, 1) as c_naturales,
            ROUND(avg_punt_sociales_ciudadanas, 1) as sociales_ciudadanas,
            ROUND(avg_punt_ingles, 1) as ingles
        FROM gold.fct_colegio_historico
        WHERE colegio_sk = ?
          AND CAST(ano AS INTEGER) >= 2015
        ORDER BY ano
    """
    try:
        df_hist = execute_query(query_hist, params=[colegio_sk_str])
        historico = df_hist.to_dict(orient="records") if not df_hist.empty else []
    except Exception as e:
        return JsonResponse({"error": f"Error obteniendo histórico: {str(e)}"}, status=500)

    if not historico:
        return JsonResponse({
            "colegio": {}, "historico": [], "pronosticos": {}, "info_modelo": {},
            "sin_datos": True
        }, status=200)

    # 2. Traer pronósticos (2025-2029) e información del modelo
    query_pronostico = """
        SELECT
            materia,
            ano,
            ROUND(puntaje_proyectado, 1) as proyectado,
            ROUND(puntaje_lb, 1) as lb,
            ROUND(puntaje_ub, 1) as ub,
            tendencia_proyectada,
            ROUND(confianza_modelo, 2) as confianza,
            ROUND(cambio_proyectado_5y, 1) as cambio_5y,
            anos_datos_usados
        FROM gold.fct_pronostico_colegio
        WHERE colegio_sk = ?
        ORDER BY materia, ano
    """
    try:
        df_pronostico = execute_query(query_pronostico, params=[colegio_sk_str])
        
        # Agrupar pronósticos por materia estructuradamente
        pronosticos = {}
        info_modelo = {}
        
        if not df_pronostico.empty:
            for materia, group in df_pronostico.groupby("materia"):
                pronosticos[materia] = group[["ano", "proyectado", "lb", "ub"]].to_dict(orient="records")
                
                # Info a nivel de materia (tomando la fila del 2029 que tiene el resumen)
                fila_resumen = group.iloc[0] 
                info_modelo[materia] = {
                    "tendencia": str(fila_resumen["tendencia_proyectada"]),
                    "confianza": float(fila_resumen["confianza"]),
                    "cambio_5y": float(fila_resumen["cambio_5y"]),
                    "anos_datos_usados": int(fila_resumen["anos_datos_usados"])
                }
    except Exception as e:
        return JsonResponse({"error": f"Error obteniendo pronósticos: {str(e)}"}, status=500)

    # Buscar contexto municipal/ubicación para la tarjeta informativa
    query_info = """
        SELECT nombre_colegio, municipio, departamento, sector
        FROM gold.dim_colegios
        WHERE colegio_sk = ? LIMIT 1
    """
    try:
        df_info = execute_query(query_info, params=[colegio_sk_str])
        colegio_info = df_info.to_dict(orient="records")[0] if not df_info.empty else {}
    except Exception:
        colegio_info = {}

    # Construir JSON de salida
    resultado = {
        "colegio": colegio_info,
        "historico": historico,
        "pronosticos": pronosticos,
        "info_modelo": info_modelo
    }

    return JsonResponse(resultado)
