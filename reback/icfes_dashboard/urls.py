"""
URLs para el dashboard ICFES.
"""
from django.urls import path
from . import views

app_name = 'icfes_dashboard'

urlpatterns = [
    # Vista principal
    path('', views.icfes_dashboard, name='dashboard'),
    path('charts/', views.dashboard_charts, name='dashboard_charts'),
    path('colegio/', views.colegio_detalle_page, name='colegio_detalle_page'),
    
    # Endpoints de datos generales
    path('api/estadisticas/', views.icfes_estadisticas_generales, name='estadisticas_generales'),
    path('api/anos/', views.icfes_anos_disponibles, name='anos_disponibles'),
    
    # Endpoints de tendencias
    path('api/tendencias/', views.tendencias_regionales, name='tendencias_regionales'),
    
    # Endpoints de colegios
    path('api/colegios/', views.colegios_agregados, name='colegios_agregados'),
    path('api/colegios/destacados/', views.colegios_destacados, name='colegios_destacados'),
    path('api/colegios/<int:colegio_sk>/', views.colegio_detalle, name='colegio_detalle'),
    
    # Endpoints de análisis
    path('api/brechas/', views.brechas_educativas, name='brechas_educativas'),
    path('api/comparacion-sectores/', views.comparacion_sectores, name='comparacion_sectores'),
    path('api/ranking-departamental/', views.ranking_departamental, name='ranking_departamental'),
    
    # Endpoints legacy (compatibilidad)
    path('data/', views.icfes_data, name='icfes_data'),
    path('resumen/', views.icfes_resumen, name='icfes_resumen'),
    
    # Endpoints para gráficos
    path('api/charts/tendencias/', views.api_tendencias_nacionales, name='api_tendencias_nacionales'),
    path('api/charts/sectores/', views.api_comparacion_sectores_chart, name='api_comparacion_sectores_chart'),
    path('api/charts/departamentos/', views.api_ranking_departamentos, name='api_ranking_departamentos'),
    path('api/charts/regional/', views.api_distribucion_regional, name='api_distribucion_regional'),
    
    # Endpoints para explorador jerárquico
    path('api/hierarchy/regions/', views.hierarchy_regions, name='hierarchy_regions'),
    path('api/hierarchy/departments/', views.hierarchy_departments, name='hierarchy_departments'),
    path('api/hierarchy/municipalities/', views.hierarchy_municipalities, name='hierarchy_municipalities'),
    path('api/hierarchy/schools/', views.hierarchy_schools, name='hierarchy_schools'),
    
    # Endpoints para Vista Individual de Colegio
    path('api/search/colegios/', views.api_search_colegios, name='api_search_colegios'),
    path('api/colegio/<int:colegio_sk>/historico/', views.api_colegio_historico, name='api_colegio_historico'),
    path('api/colegio/<int:colegio_sk>/correlaciones/', views.api_colegio_correlaciones, name='api_colegio_correlaciones'),
    path('api/colegio/<int:colegio_sk>/fortalezas/', views.api_colegio_fortalezas, name='api_colegio_fortalezas'),
    path('api/colegio/<int:colegio_sk>/comparacion/', views.api_colegio_comparacion, name='api_colegio_comparacion'),
    path('api/colegio/<int:colegio_sk>/resumen/', views.api_colegio_resumen, name='api_colegio_resumen'),
]
