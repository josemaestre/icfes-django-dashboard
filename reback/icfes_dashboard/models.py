"""
Django models for ICFES data from dbt gold layer.
These are read-only models that map to DuckDB tables.
"""
from django.db import models


class FactIcfesAnalytics(models.Model):
    """
    Modelo analítico principal de desempeño ICFES por estudiante.
    Mapea a: gold.fact_icfes_analytics
    """
    estudiante_sk = models.BigIntegerField(primary_key=True)
    colegio_ano_sk = models.BigIntegerField()
    colegio_sk = models.BigIntegerField()
    colegio_bk = models.CharField(max_length=100)
    ano = models.IntegerField()
    sector = models.CharField(max_length=50)
    
    # Puntajes
    punt_c_naturales = models.FloatField(null=True)
    punt_lectura_critica = models.FloatField(null=True)
    punt_matematicas = models.FloatField(null=True)
    punt_sociales_ciudadanas = models.FloatField(null=True)
    punt_ingles = models.FloatField(null=True)
    punt_global = models.FloatField(null=True)
    
    # Geografía
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    
    # Rankings
    ranking_colegio = models.IntegerField(null=True)
    ranking_municipio = models.IntegerField(null=True)
    ranking_departamento = models.IntegerField(null=True)
    ranking_sector = models.IntegerField(null=True)
    
    # Percentiles
    percentile_municipio = models.FloatField(null=True)
    percentile_departamento = models.FloatField(null=True)
    percentile_sector = models.FloatField(null=True)
    
    # Z-scores
    global_zscore = models.FloatField(null=True)
    zscore_municipio = models.FloatField(null=True)
    zscore_departamento = models.FloatField(null=True)
    zscore_sector = models.FloatField(null=True)
    
    # Clasificaciones
    desempeno_global = models.CharField(max_length=50, null=True)
    categoria_zscore = models.CharField(max_length=100, null=True)
    nivel_ingles_mcer = models.CharField(max_length=10, null=True)
    perfil_dual = models.CharField(max_length=50, null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.fact_icfes_analytics'
        ordering = ['-ano', '-punt_global']


class DimColegios(models.Model):
    """
    Dimensión de colegios.
    Mapea a: gold.dim_colegios
    """
    colegio_sk = models.BigIntegerField(primary_key=True)
    colegio_bk = models.CharField(max_length=100)
    nombre_colegio = models.CharField(max_length=255)
    sector = models.CharField(max_length=50)
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    
    class Meta:
        managed = False
        db_table = 'gold.dim_colegios'
        ordering = ['nombre_colegio']


class DimColegiosAno(models.Model):
    """
    Dimensión de colegios por año.
    Mapea a: gold.dim_colegios_ano
    """
    colegio_ano_sk = models.BigIntegerField(primary_key=True)
    colegio_sk = models.BigIntegerField()
    colegio_bk = models.CharField(max_length=100)
    nombre_colegio = models.CharField(max_length=255)
    ano = models.IntegerField()
    sector = models.CharField(max_length=50)
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    region = models.CharField(max_length=100, null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.dim_colegios_ano'
        ordering = ['-ano', 'nombre_colegio']


class FctAggColegiosAno(models.Model):
    """
    Agregaciones por colegio y año.
    Mapea a: gold.fct_agg_colegios_ano
    """
    # Composite key: ano + colegio_sk
    ano = models.IntegerField()
    colegio_sk = models.BigIntegerField()
    colegio_bk = models.CharField(max_length=100)
    nombre_colegio = models.CharField(max_length=255)
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    sector = models.CharField(max_length=50)
    
    # Conteos
    total_estudiantes = models.IntegerField()
    count_colegios_nacional = models.IntegerField(null=True)
    count_colegios_departamento = models.IntegerField(null=True)
    count_colegios_municipio = models.IntegerField(null=True)
    
    # Promedios
    avg_punt_global = models.FloatField(null=True)
    median_punt_global = models.FloatField(null=True)
    avg_global_zscore = models.FloatField(null=True)
    avg_punt_c_naturales = models.FloatField(null=True)
    avg_punt_lectura_critica = models.FloatField(null=True)
    avg_punt_matematicas = models.FloatField(null=True)
    avg_punt_sociales_ciudadanas = models.FloatField(null=True)
    avg_punt_ingles = models.FloatField(null=True)
    
    # Gap y rendimiento relativo
    gap_municipio_promedio = models.FloatField(null=True)
    rendimiento_relativo_municipal = models.CharField(max_length=100, null=True)
    
    # Rankings
    ranking_nacional = models.IntegerField(null=True)
    ranking_departamental_general = models.IntegerField(null=True)
    ranking_sector_departamental = models.IntegerField(null=True)
    ranking_sector_municipal = models.IntegerField(null=True)
    
    fecha_carga = models.DateTimeField(null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.fct_agg_colegios_ano'
        ordering = ['-ano', '-avg_punt_global']
        unique_together = [['ano', 'colegio_sk']]


class TendenciasRegionales(models.Model):
    """
    Tendencias temporales por región.
    Mapea a: gold.tendencias_regionales
    """
    ano = models.IntegerField()
    region = models.CharField(max_length=100)
    total_colegios = models.IntegerField()
    total_estudiantes = models.IntegerField()
    
    # Puntajes
    avg_punt_global = models.FloatField(null=True)
    avg_punt_matematicas = models.FloatField(null=True)
    avg_punt_c_naturales = models.FloatField(null=True)
    avg_punt_lectura_critica = models.FloatField(null=True)
    avg_punt_sociales_ciudadanas = models.FloatField(null=True)
    avg_punt_ingles = models.FloatField(null=True)
    avg_global_zscore = models.FloatField(null=True)
    
    # Crecimientos YoY
    yoy_growth_global_pct = models.FloatField(null=True)
    yoy_growth_matematicas_pct = models.FloatField(null=True)
    yoy_growth_c_naturales_pct = models.FloatField(null=True)
    yoy_growth_lectura_critica_pct = models.FloatField(null=True)
    yoy_growth_sociales_ciudadanas_pct = models.FloatField(null=True)
    yoy_growth_ingles_pct = models.FloatField(null=True)
    
    # Métricas avanzadas
    cambio_absoluto_global = models.FloatField(null=True)
    aceleracion_global = models.FloatField(null=True)
    tendencia_3y_global = models.FloatField(null=True)
    volatilidad_3y_global = models.FloatField(null=True)
    
    # Clasificaciones
    clasificacion_tendencia = models.CharField(max_length=50, null=True)
    clasificacion_aceleracion = models.CharField(max_length=50, null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.tendencias_regionales'
        ordering = ['-ano', 'region']
        unique_together = [['ano', 'region']]


class BrechasEducativas(models.Model):
    """
    Análisis de brechas educativas.
    Mapea a: gold.brechas_educativas
    """
    ano = models.IntegerField()
    departamento = models.CharField(max_length=100)
    
    # Promedios por sector
    avg_oficial = models.FloatField(null=True)
    avg_no_oficial = models.FloatField(null=True)
    
    # Brecha
    brecha_absoluta = models.FloatField(null=True)
    brecha_porcentual = models.FloatField(null=True)
    
    # Conteos
    count_oficial = models.IntegerField(null=True)
    count_no_oficial = models.IntegerField(null=True)
    
    # Clasificación
    clasificacion_brecha = models.CharField(max_length=50, null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.brechas_educativas'
        ordering = ['-ano', 'departamento']
        unique_together = [['ano', 'departamento']]


class ColegiosDestacados(models.Model):
    """
    Rankings de colegios destacados.
    Mapea a: gold.colegios_destacados
    """
    ano = models.IntegerField()
    colegio_sk = models.BigIntegerField()
    nombre_colegio = models.CharField(max_length=255)
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    sector = models.CharField(max_length=50)
    
    avg_punt_global = models.FloatField(null=True)
    total_estudiantes = models.IntegerField()
    ranking_nacional = models.IntegerField(null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.colegios_destacados'
        ordering = ['-ano', 'ranking_nacional']
