# Inventario de Endpoints y Controles

Generado: 2026-03-13 03:48:38 UTC

## Alcance

- Incluye rutas tipo endpoint definidas en `icfes_dashboard/urls.py`: `api/`, `export/`, `data/`, `resumen/`, `email-graphs/`, `social-card/`, `og/`.
- Prefijo base en producción: `/icfes/` (ver `config/urls.py`).
- Total endpoints inventariados: 121.

## Endpoints

| Endpoint | View | Source | Methods | Auth | Cache | Rate limit | CSRF | Path params | Observaciones |
|---|---|---|---|---|---|---|---|---|---|
| /icfes/api/anos/ | `views.icfes_anos_disponibles` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60 * 24)  # 24 horas - lista de años cambia raramente | No | Protegido por defecto | - | Acepta query param limit; limit max 500 |
| /icfes/api/brecha/area-fortalezas/ | `api_views.brecha_area_fortalezas` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/convergencia-regional/ | `api_views.brecha_convergencia_regional` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/departamental/ | `api_views.brecha_departamental` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/kpis/ | `api_views.brecha_kpis` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/niveles-desempeno/ | `api_views.brecha_niveles_desempeno` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/niveles-por-materia/ | `api_views.brecha_niveles_por_materia` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/por-materia/ | `api_views.brecha_por_materia` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/tendencia-brecha/ | `api_views.brecha_tendencia_brecha_sector` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/tendencia-historica/ | `api_views.brecha_tendencia_historica` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brecha/zscore-distribucion/ | `api_views.brecha_zscore_distribucion` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/brechas/ | `views.brechas_educativas` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60)  # 1 hora - brechas educativas | No | Protegido por defecto | - | - |
| /icfes/api/charts/departamentos/ | `views.api_ranking_departamentos` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60)  # 1 hora - ranking departamental | No | Protegido por defecto | - | Acepta query param limit; limit max 100 |
| /icfes/api/charts/regional/ | `views.api_distribucion_regional` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60)  # Cache 1 hora | No | Protegido por defecto | - | - |
| /icfes/api/charts/sectores/ | `views.api_comparacion_sectores_chart` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 30)  # Cache 30 minutos | No | Protegido por defecto | - | Acepta query param limit; limit max 100 |
| /icfes/api/charts/tendencias/ | `views.api_tendencias_nacionales` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60 * 24)  # Cache 24 horas - datos históricos no cambian | No | Protegido por defecto | - | Acepta query param limit; limit max 100 |
| /icfes/api/colegio/<str:colegio_sk>/ai-recommendations/ | `views.api_colegio_ai_recommendations` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/comparacion-chart-data/ | `views.api_colegio_comparacion_chart_data` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/comparacion-contexto/ | `views.api_colegio_comparacion_contexto` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/comparacion/ | `views.api_colegio_comparacion` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/distribucion-niveles/ | `views.api_colegio_distribucion_niveles` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/fortalezas-debilidades/ | `views_school_endpoints.api_colegio_fortalezas` | `icfes_dashboard/views_school_endpoints.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | Acepta query param limit; limit max 20 |
| /icfes/api/colegio/<str:colegio_sk>/historico/ | `views.api_colegio_historico` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/indicadores-excelencia/ | `views.api_colegio_indicadores_excelencia` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/indicadores-ingles/ | `views.api_colegio_indicadores_ingles` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/ingles/ | `views_school_endpoints.api_colegio_ingles` | `icfes_dashboard/views_school_endpoints.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/ml-diagnostico/ | `views_mi_colegio.api_colegio_ml_diagnostico` | `icfes_dashboard/views_mi_colegio.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/niveles-historico/ | `views_school_endpoints.api_colegio_niveles_historico` | `icfes_dashboard/views_school_endpoints.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/recomendaciones/ | `views_mi_colegio.api_colegio_recomendaciones` | `icfes_dashboard/views_mi_colegio.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/resumen/ | `views.api_colegio_resumen` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/riesgo/ | `views.api_colegio_riesgo` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/api/colegio/<str:colegio_sk>/similares/ | `views_school_endpoints.api_colegios_similares` | `icfes_dashboard/views_school_endpoints.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | str:colegio_sk | Acepta query param limit; limit max 20 |
| /icfes/api/colegio/<str:colegio_sk>/similares/ | `views.api_colegios_similares` | `icfes_dashboard/views.py` | N/D | N/D | N/D | N/D | N/D | str:colegio_sk | - |
| /icfes/api/colegio/buscar/ | `views_mi_colegio.api_colegio_buscar` | `icfes_dashboard/views_mi_colegio.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/colegios/ | `views.colegios_agregados` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | _public_api_rate_limit(max_requests=60, window_seconds=60) | Protegido por defecto | - | Acepta query param limit; limit max 500 |
| /icfes/api/colegios/<int:colegio_sk>/ | `views.colegio_detalle` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | int:colegio_sk | - |
| /icfes/api/colegios/destacados/ | `views.colegios_destacados` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 30)  # 30 minutos - top colegios | _public_api_rate_limit(max_requests=60, window_seconds=60) | Protegido por defecto | - | Acepta query param limit; limit max 500 |
| /icfes/api/comparacion-sectores/ | `views.comparacion_sectores` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 30)  # 30 minutos - comparación sectores | No | Protegido por defecto | - | - |
| /icfes/api/comparar-colegios/ | `views.api_comparar_colegios` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/cuadrante/data/ | `views_cuadrante.api_cuadrante_data` | `icfes_dashboard/views_cuadrante.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/departments/ | `api_views.get_departments` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/estadisticas/ | `views.icfes_estadisticas_generales` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 15)  # 15 minutos - estadísticas generales | _public_api_rate_limit(max_requests=120, window_seconds=60) | Protegido por defecto | - | Acepta query param limit; limit max 500 |
| /icfes/api/hierarchy/departments/ | `views.hierarchy_departments` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/hierarchy/history/ | `views.hierarchy_history` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Acepta query param limit; limit max 100; Busqueda minima 3 caracteres |
| /icfes/api/hierarchy/municipalities/ | `views.hierarchy_municipalities` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/hierarchy/regions/ | `views.hierarchy_regions` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/hierarchy/schools/ | `views.hierarchy_schools` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/historia/brechas/ | `api_views.historia_brechas` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/historia/convergencia/ | `api_views.historia_convergencia` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/historia/ingles/ | `api_views.historia_ingles` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/historia/regiones/ | `api_views.historia_regiones` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/historia/riesgo/ | `api_views.historia_riesgo` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/historia/riesgo/colegios/ | `api_views.historia_riesgo_colegios` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/historia/tendencia-nacional/ | `api_views.historia_tendencia_nacional` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/ai-analisis/ | `views_ingles.api_ingles_ai_analisis` | `icfes_dashboard/views_ingles.py` | GET, POST | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/alertas-declive/ | `views_ingles.api_ingles_alertas_declive` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/brechas/ | `views_ingles.api_ingles_brechas` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/clusters-depto/ | `views_ingles.api_ingles_clusters_depto` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/ingles/colegio-serie/ | `views_ingles.api_ingles_colegio_serie` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/ingles/colegios-top/ | `views_ingles.api_ingles_colegios_top` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/ingles/correlaciones/ | `views_ingles.api_ingles_correlaciones` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/distribucion/ | `views_ingles.api_ingles_distribucion` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/estado-animo/ | `views_ingles.api_ingles_estado_animo` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/kpis/ | `views_ingles.api_ingles_kpis` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/mapa-depto/ | `views_ingles.api_ingles_mapa_depto` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/mcer-historico/ | `views_ingles.api_ingles_mcer_historico` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/potencial/ | `views_ingles.api_ingles_potencial` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/prediccion/ | `views_ingles.api_ingles_prediccion` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/ingles/prioridad/ | `views_ingles.api_ingles_prioridad` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/ingles/story/ | `views_ingles.api_ingles_story` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/tendencia/ | `views_ingles.api_ingles_tendencia` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ingles/tendencias-regionales/ | `views_ingles.api_ingles_tendencias_regionales` | `icfes_dashboard/views_ingles.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/inteligencia/movilidad/ | `api_views.inteligencia_movilidad` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/inteligencia/potencial/ | `api_views.inteligencia_potencial` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/inteligencia/potencial/scatter/ | `api_views.inteligencia_potencial_scatter` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/inteligencia/promesa-ingles/ | `api_views.inteligencia_promesa_ingles` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/inteligencia/resilientes/ | `api_views.inteligencia_resilientes` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/inteligencia/trayectorias/ | `api_views.inteligencia_trayectorias` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/mapa-colegios/ | `views.api_mapa_colegios` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/mapa-departamentos/ | `views.api_mapa_departamentos` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/mapa-estudiantes-heatmap/ | `views.api_mapa_estudiantes_heatmap` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/mapa-municipios/ | `views.api_mapa_municipios` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/b1/ | `views_ml.api_ml_b1` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/generate-ia/ | `views_ml.api_ml_generate_ia` | `icfes_dashboard/views_ml.py` | ANY/No explicito | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/ia-analisis/ | `views_ml.api_ml_ia_analisis` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/palancas-nacional/ | `views_ml.api_ml_palancas_nacional` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/palancas/ | `views_ml.api_ml_palancas_colegio` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/partial-all/ | `views_ml.api_ml_partial_all` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/riesgo/ | `views_ml.api_ml_riesgo` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/shap/ | `views_ml.api_ml_shap` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/ml/social-clusters/ | `views_ml.api_ml_social_clusters` | `icfes_dashboard/views_ml.py` | GET | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/municipalities/ | `api_views.get_municipalities` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/panorama-riesgo/ | `views.api_panorama_riesgo` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/promedios-ubicacion/ | `views.api_promedios_ubicacion` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/api/ranking-departamental/ | `views.ranking_departamental` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60)  # 1 hora - ranking departamental | No | Protegido por defecto | - | - |
| /icfes/api/schools/search/ | `api_views.search_schools` | `icfes_dashboard/api_views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Busqueda minima 3 caracteres |
| /icfes/api/search/colegios/ | `views.api_search_colegios` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | Acepta query param limit; limit max 100; Busqueda minima 3 caracteres |
| /icfes/api/social/brecha-sector-gobierno/ | `views.api_social_brecha_sector` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 60) | No | Protegido por defecto | - | - |
| /icfes/api/social/colegios-heroes/ | `views.api_social_colegios_heroes` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 30) | No | Protegido por defecto | - | - |
| /icfes/api/social/conectividad-materias/ | `views.api_social_conectividad_materias` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 60) | No | Protegido por defecto | - | - |
| /icfes/api/social/era-tecnologica/ | `views.api_social_era_tecnologica` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 60) | No | Protegido por defecto | - | - |
| /icfes/api/social/estrato/ | `views.api_social_estrato` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 5) | No | Protegido por defecto | - | - |
| /icfes/api/social/kpis/ | `views.api_social_kpis` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 60) | No | Protegido por defecto | - | - |
| /icfes/api/social/mapa-departamentos/ | `views.api_social_mapa_departamentos` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 60) | No | Protegido por defecto | - | - |
| /icfes/api/social/nbi-brechas/ | `views.api_social_nbi_brechas` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 60) | No | Protegido por defecto | - | - |
| /icfes/api/social/scatter-municipios/ | `views.api_social_scatter_municipios` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/api/social/serie-historica-contexto/ | `views.api_social_serie_historica` | `icfes_dashboard/views.py` | ANY/No explicito | Login requerido | cache_page(60 * 60) | No | Protegido por defecto | - | - |
| /icfes/api/story/brechas/ | `views.api_story_brechas_clave` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 30)  # 30 minutos | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/story/priorizacion/ | `views.api_story_priorizacion` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 15)  # 15 minutos | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/story/resumen/ | `views.api_story_resumen_ejecutivo` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 30)  # 30 minutos | No | Protegido por defecto | - | - |
| /icfes/api/story/serie-anual/ | `views.api_story_serie_anual` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60)  # 1 hora | No | Protegido por defecto | - | Acepta query param limit |
| /icfes/api/tendencias/ | `views.tendencias_regionales` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60)  # 1 hora - tendencias regionales | No | Protegido por defecto | - | Acepta query param limit; limit max 500 |
| /icfes/data/ | `views.icfes_data` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/email-graphs/<path:slug>.png | `email_graph_views.email_graph_png` | `icfes_dashboard/email_graph_views.py` | GET | Publico (sin login_required visible) | cache_page(60 * 60 * 24)  # 24h | No | Protegido por defecto | path:slug | - |
| /icfes/export/comparison/pdf/ | `export_views.export_comparison_pdf` | `icfes_dashboard/export_views.py` | ANY/No explicito | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/export/ranking/csv/ | `export_views.export_ranking_csv` | `icfes_dashboard/export_views.py` | ANY/No explicito | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/export/school/<str:colegio_sk>/pdf/ | `export_views.export_school_report_pdf` | `icfes_dashboard/export_views.py` | ANY/No explicito | Login requerido | No | No | Protegido por defecto | str:colegio_sk | - |
| /icfes/export/schools/csv/ | `export_views.export_school_search_csv` | `icfes_dashboard/export_views.py` | ANY/No explicito | Login requerido | No | No | Protegido por defecto | - | - |
| /icfes/og/default.png | `email_graph_views.og_default_image` | `icfes_dashboard/email_graph_views.py` | GET, HEAD | Publico (sin login_required visible) | cache_page(60 * 60 * 24 * 7)  # 7 days — generic, no school data | No | Protegido por defecto | - | - |
| /icfes/resumen/ | `views.icfes_resumen` | `icfes_dashboard/views.py` | GET | Publico (sin login_required visible) | No | No | Protegido por defecto | - | - |
| /icfes/social-card/colegio/<path:slug>.png | `email_graph_views.social_card_school_png` | `icfes_dashboard/email_graph_views.py` | GET, HEAD | Publico (sin login_required visible) | cache_page(60 * 60 * 24)  # 24h | No | Protegido por defecto | path:slug | - |
