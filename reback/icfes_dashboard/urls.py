"""
URLs para el dashboard ICFES.
"""
from django.urls import path
from . import (
    api_views,
    export_views,
    geo_landing_views,
    ingles_landing_views,
    invitacion_views,
    landing_views_simple as landing_views,
    longtail_landing_views,
    views,
    views_ingles,
    views_mi_colegio,
    views_school_endpoints,
)

app_name = 'icfes_dashboard'

urlpatterns = [
    # Vista principal
    path('', views.icfes_dashboard, name='dashboard'),
    path('charts/', views.dashboard_charts, name='dashboard_charts'),
    path('brecha/', views.brecha_educativa_dashboard, name='brecha_educativa'),
    path('ejecutivo/', views.resumen_ejecutivo_dashboard, name='resumen_ejecutivo'),
    path('ingles/', views.ingles_dashboard, name='ingles_dashboard'),
    path('ingles-seo/', ingles_landing_views.ingles_hub_page, name='ingles_seo_hub'),
    path('ingles-seo/departamento/<slug:departamento_slug>/',
         ingles_landing_views.ingles_department_page, name='ingles_department_landing'),
    path('historia/', views.historia_educacion_dashboard, name='historia_educacion'),
    path('inteligencia/', views.inteligencia_educativa_dashboard, name='inteligencia_educativa'),
    path('colegio/', views.colegio_detalle_page, name='colegio_detalle_page'),

    # Mi Colegio — diagnóstico personalizado
    path('mi-colegio/', views_mi_colegio.mi_colegio_page, name='mi_colegio'),
    path('mi-colegio/seleccionar/', views_mi_colegio.mi_colegio_seleccionar, name='mi_colegio_seleccionar'),
    path('mi-colegio/limpiar/', views_mi_colegio.mi_colegio_limpiar, name='mi_colegio_limpiar'),
    path('api/colegio/buscar/', views_mi_colegio.api_colegio_buscar, name='api_colegio_buscar'),
    path('api/colegio/<str:colegio_sk>/ml-diagnostico/', views_mi_colegio.api_colegio_ml_diagnostico, name='api_colegio_ml_diagnostico'),
    path('api/colegio/<str:colegio_sk>/recomendaciones/', views_mi_colegio.api_colegio_recomendaciones, name='api_colegio_recomendaciones'),

    # Dynamic school landing pages (SEO)
    path('colegio/<slug:slug>/',
         landing_views.school_landing_page, name='school_landing'),
    path('departamentos/',
         geo_landing_views.departments_index_page, name='departments_index'),
    path('departamento/<slug:departamento_slug>/',
         geo_landing_views.department_landing_page, name='department_landing'),
    path('departamento/<slug:departamento_slug>/municipio/<slug:municipio_slug>/',
         geo_landing_views.municipality_landing_page, name='municipality_landing'),
    path('ranking/colegios/<int:ano>/',
         longtail_landing_views.ranking_colegios_year_page, name='ranking_colegios_year'),
    path('ranking/matematicas/<int:ano>/',
         longtail_landing_views.ranking_matematicas_year_page, name='ranking_matematicas_year'),
    path('historico/puntaje-global/',
         longtail_landing_views.historico_nacional_page, name='historico_puntaje_global'),

    # Endpoints de datos generales
    path('api/estadisticas/', views.icfes_estadisticas_generales,
         name='estadisticas_generales'),
    path('api/anos/', views.icfes_anos_disponibles, name='anos_disponibles'),

    # Endpoints de tendencias
    path('api/tendencias/', views.tendencias_regionales,
         name='tendencias_regionales'),

    # Endpoints de colegios
    path('api/colegios/', views.colegios_agregados, name='colegios_agregados'),
    path('api/colegios/destacados/', views.colegios_destacados,
         name='colegios_destacados'),
    path('api/colegios/<int:colegio_sk>/',
         views.colegio_detalle, name='colegio_detalle'),

    # Endpoints de análisis
    path('api/brechas/', views.brechas_educativas, name='brechas_educativas'),
    path('api/comparacion-sectores/', views.comparacion_sectores,
         name='comparacion_sectores'),
    path('api/ranking-departamental/', views.ranking_departamental,
         name='ranking_departamental'),

    # Endpoints legacy (compatibilidad)
    path('data/', views.icfes_data, name='icfes_data'),
    path('resumen/', views.icfes_resumen, name='icfes_resumen'),

    # Endpoints para gráficos
    path('api/charts/tendencias/', views.api_tendencias_nacionales,
         name='api_tendencias_nacionales'),
    path('api/charts/sectores/', views.api_comparacion_sectores_chart,
         name='api_comparacion_sectores_chart'),
    path('api/charts/departamentos/', views.api_ranking_departamentos,
         name='api_ranking_departamentos'),
    path('api/charts/regional/', views.api_distribucion_regional,
         name='api_distribucion_regional'),
    path('api/promedios-ubicacion/', views.api_promedios_ubicacion,
         name='api_promedios_ubicacion'),

    # Endpoints para explorador jerárquico
    path('api/hierarchy/regions/', views.hierarchy_regions,
         name='hierarchy_regions'),
    path('api/hierarchy/departments/', views.hierarchy_departments,
         name='hierarchy_departments'),
    path('api/hierarchy/municipalities/', views.hierarchy_municipalities,
         name='hierarchy_municipalities'),
    path('api/hierarchy/schools/', views.hierarchy_schools,
         name='hierarchy_schools'),
    path('api/hierarchy/history/', views.hierarchy_history,
         name='hierarchy_history'),

    # Endpoints para Vista Individual de Colegio
    path('api/search/colegios/', views.api_search_colegios,
         name='api_search_colegios'),
    path('api/colegio/<str:colegio_sk>/historico/',
         views.api_colegio_historico, name='api_colegio_historico'),
    path('api/colegio/<str:colegio_sk>/similares/',
         views_school_endpoints.api_colegios_similares, name='api_colegios_similares'),
    path('api/colegio/<str:colegio_sk>/fortalezas-debilidades/',
         views_school_endpoints.api_colegio_fortalezas, name='api_colegio_fortalezas_debilidades'),
    path('api/colegio/<str:colegio_sk>/ingles/',
         views_school_endpoints.api_colegio_ingles, name='api_colegio_ingles'),
    path('api/colegio/<str:colegio_sk>/niveles-historico/',
         views_school_endpoints.api_colegio_niveles_historico, name='api_colegio_niveles_historico'),
    path('api/colegio/<str:colegio_sk>/comparacion/',
         views.api_colegio_comparacion, name='api_colegio_comparacion'),
    path('api/colegio/<str:colegio_sk>/resumen/',
         views.api_colegio_resumen, name='api_colegio_resumen'),
    path('api/colegio/<str:colegio_sk>/ai-recommendations/',
         views.api_colegio_ai_recommendations, name='api_colegio_ai_recommendations'),

    # Endpoints de Comparación con Contexto (NUEVO - usando modelo gold)
    path('api/colegio/<str:colegio_sk>/comparacion-contexto/',
         views.api_colegio_comparacion_contexto, name='api_colegio_comparacion_contexto'),
    path('api/colegio/<str:colegio_sk>/comparacion-chart-data/',
         views.api_colegio_comparacion_chart_data, name='api_colegio_comparacion_chart_data'),

    # Endpoint de Colegios Similares (Clustering)
    path('api/colegio/<str:colegio_sk>/similares/',
         views.api_colegios_similares, name='api_colegios_similares'),

    # Endpoint de Indicadores de Excelencia (NUEVO - usando fct_indicadores_desempeno)
    path('api/colegio/<str:colegio_sk>/indicadores-excelencia/',
         views.api_colegio_indicadores_excelencia, name='api_colegio_indicadores_excelencia'),

    # Endpoint de Indicadores de Inglés MCER por colegio
    path('api/colegio/<str:colegio_sk>/indicadores-ingles/',
         views.api_colegio_indicadores_ingles, name='api_colegio_indicadores_ingles'),

    # Endpoint de Distribución de Niveles de Desempeño (NUEVO - gráficas donut estilo ICFES)
    path('api/colegio/<str:colegio_sk>/distribucion-niveles/',
         views.api_colegio_distribucion_niveles, name='api_colegio_distribucion_niveles'),

    # Endpoints de Mapa Geográfico
    path('api/mapa-colegios/', views.api_mapa_colegios, name='api_mapa_colegios'),
    path('api/mapa-estudiantes-heatmap/', views.api_mapa_estudiantes_heatmap,
         name='api_mapa_estudiantes_heatmap'),
    path('api/mapa-departamentos/', views.api_mapa_departamentos,
         name='api_mapa_departamentos'),
    path('api/mapa-municipios/', views.api_mapa_municipios,
         name='api_mapa_municipios'),

    # Endpoint de Comparación de Colegios (NUEVO - requiere autenticación)
    path('api/comparar-colegios/', views.api_comparar_colegios,
         name='api_comparar_colegios'),

    # Endpoints de Riesgo de Declive (Data Science P2)
    path('api/colegio/<str:colegio_sk>/riesgo/',
         views.api_colegio_riesgo, name='api_colegio_riesgo'),
    path('api/panorama-riesgo/',
         views.api_panorama_riesgo, name='api_panorama_riesgo'),

    # Storytelling ejecutivo (Gold Layer)
    path('api/story/resumen/', views.api_story_resumen_ejecutivo, name='api_story_resumen'),
    path('api/story/serie-anual/', views.api_story_serie_anual, name='api_story_serie_anual'),
    path('api/story/brechas/', views.api_story_brechas_clave, name='api_story_brechas'),
    path('api/story/priorizacion/', views.api_story_priorizacion, name='api_story_priorizacion'),

    # Historia de la Educación Colombiana - Story API
    path('api/historia/tendencia-nacional/', api_views.historia_tendencia_nacional, name='historia_tendencia_nacional'),
    path('api/historia/regiones/', api_views.historia_regiones, name='historia_regiones'),
    path('api/historia/brechas/', api_views.historia_brechas, name='historia_brechas'),
    path('api/historia/convergencia/', api_views.historia_convergencia, name='historia_convergencia'),
    path('api/historia/riesgo/', api_views.historia_riesgo, name='historia_riesgo'),
    path('api/historia/riesgo/colegios/', api_views.historia_riesgo_colegios, name='historia_riesgo_colegios'),
    path('api/historia/ingles/', api_views.historia_ingles, name='historia_ingles'),

    # Inteligencia Educativa - ML-driven narratives
    path('api/inteligencia/trayectorias/', api_views.inteligencia_trayectorias, name='inteligencia_trayectorias'),
    path('api/inteligencia/resilientes/', api_views.inteligencia_resilientes, name='inteligencia_resilientes'),
    path('api/inteligencia/movilidad/', api_views.inteligencia_movilidad, name='inteligencia_movilidad'),
    path('api/inteligencia/promesa-ingles/', api_views.inteligencia_promesa_ingles, name='inteligencia_promesa_ingles'),
    path('api/inteligencia/potencial/', api_views.inteligencia_potencial, name='inteligencia_potencial'),
    path('api/inteligencia/potencial/scatter/', api_views.inteligencia_potencial_scatter, name='inteligencia_potencial_scatter'),

    # English Dashboard Endpoints
    path('api/ingles/kpis/', views_ingles.api_ingles_kpis, name='api_ingles_kpis'),
    path('api/ingles/tendencia/', views_ingles.api_ingles_tendencia, name='api_ingles_tendencia'),
    path('api/ingles/distribucion/', views_ingles.api_ingles_distribucion, name='api_ingles_distribucion'),
    path('api/ingles/colegios-top/', views_ingles.api_ingles_colegios_top, name='api_ingles_colegios_top'),
    path('api/ingles/mcer-historico/', views_ingles.api_ingles_mcer_historico, name='api_ingles_mcer_historico'),
    path('api/ingles/brechas/', views_ingles.api_ingles_brechas, name='api_ingles_brechas'),
    path('api/ingles/potencial/', views_ingles.api_ingles_potencial, name='api_ingles_potencial'),
    path('api/ingles/mapa-depto/', views_ingles.api_ingles_mapa_depto, name='api_ingles_mapa_depto'),
    path('api/ingles/estado-animo/', views_ingles.api_ingles_estado_animo, name='api_ingles_estado_animo'),
    path('api/ingles/alertas-declive/', views_ingles.api_ingles_alertas_declive, name='api_ingles_alertas_declive'),
    path('api/ingles/colegio-serie/', views_ingles.api_ingles_colegio_serie, name='api_ingles_colegio_serie'),
    path('api/ingles/story/', views_ingles.api_ingles_story, name='api_ingles_story'),
    path('api/ingles/prioridad/', views_ingles.api_ingles_prioridad, name='api_ingles_prioridad'),
    path('api/ingles/clusters-depto/', views_ingles.api_ingles_clusters_depto, name='api_ingles_clusters_depto'),
    path('api/ingles/prediccion/', views_ingles.api_ingles_prediccion, name='api_ingles_prediccion'),
    path('api/ingles/ai-analisis/', views_ingles.api_ingles_ai_analisis, name='api_ingles_ai_analisis'),
    path('api/ingles/correlaciones/', views_ingles.api_ingles_correlaciones, name='api_ingles_correlaciones'),
    path('api/ingles/tendencias-regionales/', views_ingles.api_ingles_tendencias_regionales, name='api_ingles_tendencias_regionales'),

    # API endpoints for enhanced user profile
    path('api/schools/search/', api_views.search_schools, name='search_schools'),
    path('api/departments/', api_views.get_departments, name='get_departments'),
    path('api/municipalities/', api_views.get_municipalities, name='get_municipalities'),

    # Brecha Educativa API endpoints
    path('api/brecha/kpis/', api_views.brecha_kpis, name='brecha_kpis'),
    path('api/brecha/por-materia/', api_views.brecha_por_materia, name='brecha_por_materia'),
    path('api/brecha/tendencia-historica/', api_views.brecha_tendencia_historica, name='brecha_tendencia_historica'),
    path('api/brecha/niveles-desempeno/', api_views.brecha_niveles_desempeno, name='brecha_niveles_desempeno'),
    path('api/brecha/departamental/', api_views.brecha_departamental, name='brecha_departamental'),
    path('api/brecha/niveles-por-materia/', api_views.brecha_niveles_por_materia, name='brecha_niveles_por_materia'),
    path('api/brecha/convergencia-regional/', api_views.brecha_convergencia_regional, name='brecha_convergencia_regional'),
    path('api/brecha/tendencia-brecha/', api_views.brecha_tendencia_brecha_sector, name='brecha_tendencia_brecha'),
    path('api/brecha/area-fortalezas/', api_views.brecha_area_fortalezas, name='brecha_area_fortalezas'),
    path('api/brecha/zscore-distribucion/', api_views.brecha_zscore_distribucion, name='brecha_zscore_distribucion'),
    
    # Módulo de invitaciones (solo superadmin)
    path('invitar/', invitacion_views.invitar, name='invitar'),

    # Export Endpoints
    # CSV Exports (Basic Plan)
    path('export/schools/csv/', export_views.export_school_search_csv,
         name='export_schools_csv'),
    path('export/ranking/csv/', export_views.export_ranking_csv,
         name='export_ranking_csv'),
    
    # PDF Exports (Premium Plan)
    path('export/school/<str:colegio_sk>/pdf/', 
         export_views.export_school_report_pdf,
         name='export_school_pdf'),
    path('export/comparison/pdf/', export_views.export_comparison_pdf,
         name='export_comparison_pdf'),
]


print("BOOT icfes_dashboard.urls loaded with slug route")
