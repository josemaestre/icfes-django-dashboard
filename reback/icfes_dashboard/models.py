"""
Django models for ICFES data from dbt gold layer.
These are read-only models that map to DuckDB tables.
"""
from django.db import models
from django.utils import timezone


# ============================================================================
# MÓDULO DE CAMPAÑAS COMERCIALES
# Gestión de outbound sales a colegios privados
# ============================================================================

class Campaign(models.Model):
    """
    Representa una campaña de outbound sales.
    Cada campaña agrupa un lote de prospectos con configuración propia.
    """
    ESTADO_CHOICES = [
        ('borrador',    'Borrador'),
        ('activa',      'Activa'),
        ('pausada',     'Pausada'),
        ('completada',  'Completada'),
    ]

    nombre            = models.CharField(max_length=150)
    lote              = models.IntegerField(default=1, help_text="Número de lote (1, 2, 3...)")
    estado            = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    descripcion       = models.TextField(blank=True, help_text="Segmento objetivo, estrategia, notas")

    # Configuración de envío
    email_remitente   = models.EmailField(default='icfes@sabededatos.com')
    nombre_remitente  = models.CharField(max_length=100, default='Jose Maestre',
                                         help_text="Nombre que ve el destinatario. Para Tier 1 usar nombre personal.")

    # Parámetros del lote importado
    ciudades_objetivo = models.TextField(blank=True, help_text="Ciudades incluidas, separadas por coma")
    top_n_por_ciudad  = models.IntegerField(default=10, help_text="Top N colegios por ciudad")

    # Fechas
    fecha_creacion    = models.DateTimeField(auto_now_add=True)
    fecha_lanzamiento = models.DateTimeField(null=True, blank=True)
    fecha_completada  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Campaña'
        verbose_name_plural = 'Campañas'

    def __str__(self):
        return f"[Lote {self.lote}] {self.nombre} — {self.get_estado_display()}"

    @property
    def total_prospectos(self):
        return self.prospects.count()

    @property
    def stats(self):
        qs = self.prospects
        return {
            'total':      qs.count(),
            'pendiente':  qs.filter(estado='pendiente').count(),
            'enviado':    qs.filter(estado='enviado').count(),
            'respondio':  qs.filter(estado='respondio').count(),
            'demo':       qs.filter(estado='demo').count(),
            'trial':      qs.filter(estado='trial').count(),
            'cliente':    qs.filter(estado='cliente').count(),
            'descartado': qs.filter(estado='descartado').count(),
        }


class CampaignProspect(models.Model):
    """
    Prospecto individual dentro de una campaña.
    Datos copiados desde DuckDB al importar — Postgres solo para tracking.
    """
    ESTADO_CHOICES = [
        ('pendiente',   'Pendiente'),
        ('enviado',     'Email enviado'),
        ('respondio',   'Respondió'),
        ('demo',        'Demo agendada'),
        ('trial',       'Trial activo'),
        ('cliente',     'Cliente pagando'),
        ('descartado',  'Descartado'),
    ]

    campaign         = models.ForeignKey(Campaign, on_delete=models.CASCADE,
                                         related_name='prospects')

    # Datos del colegio (snapshot desde DuckDB)
    nombre_colegio   = models.CharField(max_length=255)
    rector           = models.CharField(max_length=255, blank=True)
    email            = models.EmailField()
    telefono         = models.CharField(max_length=50, blank=True)
    municipio        = models.CharField(max_length=100)
    departamento     = models.CharField(max_length=100)
    slug             = models.CharField(max_length=255)
    avg_punt_global  = models.FloatField(default=0)
    rank_municipio   = models.IntegerField(default=0,
                                           help_text="Posición dentro de su municipio por puntaje")
    demo_url         = models.URLField(max_length=500)

    # Tracking de campaña
    estado           = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    fecha_envio      = models.DateTimeField(null=True, blank=True)
    fecha_respuesta  = models.DateTimeField(null=True, blank=True)
    notas            = models.TextField(blank=True)

    class Meta:
        ordering = ['municipio', 'rank_municipio']
        verbose_name = 'Prospecto'
        verbose_name_plural = 'Prospectos'
        unique_together = [['campaign', 'email']]

    def __str__(self):
        return f"{self.nombre_colegio} ({self.municipio}) — {self.get_estado_display()}"


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


class FctColegioHistorico(models.Model):
    """
    Estadísticas históricas año por año de cada colegio.
    Mapea a: gold.fct_colegio_historico
    Uso: Vista individual de colegio - evolución temporal
    """
    colegio_sk = models.BigIntegerField()
    codigo_dane = models.CharField(max_length=100)
    nombre_colegio = models.CharField(max_length=255)
    sector = models.CharField(max_length=50)
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    ano = models.IntegerField()
    total_estudiantes = models.IntegerField()
    
    # Puntajes del colegio
    avg_punt_global = models.FloatField(null=True)
    avg_punt_matematicas = models.FloatField(null=True)
    avg_punt_lectura_critica = models.FloatField(null=True)
    avg_punt_c_naturales = models.FloatField(null=True)
    avg_punt_sociales_ciudadanas = models.FloatField(null=True)
    avg_punt_ingles = models.FloatField(null=True)
    
    # Rankings
    ranking_nacional = models.IntegerField(null=True)
    percentil_sector = models.FloatField(null=True)
    ranking_municipal = models.IntegerField(null=True)
    
    # Contexto municipal
    promedio_municipal_global = models.FloatField(null=True)
    brecha_municipal_global = models.FloatField(null=True)
    total_colegios_municipio = models.IntegerField(null=True)
    
    # Contexto departamental
    promedio_departamental_global = models.FloatField(null=True)
    brecha_departamental_global = models.FloatField(null=True)
    total_colegios_departamento = models.IntegerField(null=True)
    
    # Contexto nacional
    promedio_nacional_global = models.FloatField(null=True)
    brecha_nacional_global = models.FloatField(null=True)
    
    # Tendencias YoY
    punt_global_ano_anterior = models.FloatField(null=True)
    cambio_absoluto_global = models.FloatField(null=True)
    cambio_porcentual_global = models.FloatField(null=True)
    clasificacion_tendencia = models.CharField(max_length=50, null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.fct_colegio_historico'
        ordering = ['colegio_sk', '-ano']
        unique_together = [['colegio_sk', 'ano']]


class FctColegioCorrelaciones(models.Model):
    """
    Correlaciones entre materias y puntaje global por colegio.
    Mapea a: gold.fct_colegio_correlaciones
    Uso: Identificar qué materia tiene mayor impacto en el puntaje global
    """
    colegio_sk = models.BigIntegerField(primary_key=True)
    codigo_dane = models.CharField(max_length=100)
    nombre_colegio = models.CharField(max_length=255)
    sector = models.CharField(max_length=50)
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    
    # Años de datos
    anos_con_datos = models.IntegerField()
    rango_historico = models.CharField(max_length=50, null=True)
    
    # Correlaciones (qué materia impacta más el puntaje global)
    corr_matematicas_global = models.FloatField(null=True)
    corr_lectura_global = models.FloatField(null=True)
    corr_naturales_global = models.FloatField(null=True)
    corr_sociales_global = models.FloatField(null=True)
    corr_ingles_global = models.FloatField(null=True)
    
    # Materia con mayor correlación
    materia_mayor_correlacion = models.CharField(max_length=50, null=True)
    valor_mayor_correlacion = models.FloatField(null=True)
    
    # Promedios históricos
    promedio_historico_global = models.FloatField(null=True)
    promedio_historico_matematicas = models.FloatField(null=True)
    promedio_historico_lectura = models.FloatField(null=True)
    promedio_historico_naturales = models.FloatField(null=True)
    promedio_historico_sociales = models.FloatField(null=True)
    promedio_historico_ingles = models.FloatField(null=True)
    
    # Volatilidad (desviación estándar)
    volatilidad_global = models.FloatField(null=True)
    volatilidad_matematicas = models.FloatField(null=True)
    
    # Mejor y peor año
    ano_mejor_puntaje = models.IntegerField(null=True)
    puntaje_mejor_ano = models.FloatField(null=True)
    ano_peor_puntaje = models.IntegerField(null=True)
    puntaje_peor_ano = models.FloatField(null=True)
    
    # Tendencia general (regresión lineal)
    tendencia_general = models.CharField(max_length=50, null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.fct_colegio_correlaciones'
        ordering = ['nombre_colegio']


class FctColegioFortalezasDebilidades(models.Model):
    """
    Análisis de fortalezas y debilidades por materia de cada colegio.
    Mapea a: gold.fct_colegio_fortalezas_debilidades
    Uso: Identificar áreas de mejora y fortalezas
    """
    colegio_sk = models.BigIntegerField()
    codigo_dane = models.CharField(max_length=100)
    nombre_colegio = models.CharField(max_length=255)
    sector = models.CharField(max_length=50)
    departamento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    materia = models.CharField(max_length=50)
    
    # Puntajes
    promedio_colegio = models.FloatField(null=True)
    promedio_nacional = models.FloatField(null=True)
    brecha_vs_nacional = models.FloatField(null=True)
    brecha_porcentual = models.FloatField(null=True)
    
    # Clasificación
    clasificacion_brecha = models.CharField(max_length=50, null=True)
    es_fortaleza = models.BooleanField(null=True)
    es_debilidad = models.BooleanField(null=True)
    
    # Ranking de la materia
    ranking_materia = models.IntegerField(null=True)
    
    # Identificación de materia más fuerte/débil
    es_materia_mas_fuerte = models.BooleanField(null=True)
    es_materia_mas_debil = models.BooleanField(null=True)
    
    # Análisis general del colegio
    total_fortalezas = models.IntegerField(null=True)
    total_debilidades = models.IntegerField(null=True)
    clasificacion_general = models.CharField(max_length=50, null=True)
    perfil_rendimiento = models.CharField(max_length=100, null=True)
    
    # Recomendaciones
    recomendacion = models.TextField(null=True)
    prioridad_mejora = models.CharField(max_length=20, null=True)
    potencial_mejora_estimado = models.FloatField(null=True)
    
    class Meta:
        managed = False
        db_table = 'gold.fct_colegio_fortalezas_debilidades'
        ordering = ['colegio_sk', 'ranking_materia']


class DimColegiosCluster(models.Model):
    """
    Dimensión de clusters de colegios.
    Mapea a: gold.dim_colegios_cluster
    Uso: Segmentación y comparación de colegios similares
    """
    colegio_sk = models.BigIntegerField()
    ano = models.IntegerField()
    cluster_id = models.IntegerField()
    cluster_name = models.CharField(max_length=100)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'gold.dim_colegios_cluster'
        unique_together = [['colegio_sk', 'ano']]
        ordering = ['ano', 'cluster_id']


class InglesAnalisisIA(models.Model):
    """
    Análisis generativo de inglés pre-calculado durante el deploy.

    Se almacena en PostgreSQL (default DB), NO en DuckDB.
    Razón: es dato operacional mutable — se regenera con cada deploy,
    sobrevive reinicios y redeploys del servidor web, y no requiere
    API key de IA en runtime (solo durante el proceso de deploy).

    El script que lo genera: deploy/generate_ingles_ia.py
    El endpoint que lo sirve: api_ingles_ai_analisis (views_ingles.py)
    """
    TIPO_NACIONAL      = 'nacional'
    TIPO_DEPARTAMENTO  = 'departamento'
    TIPO_CHOICES = [
        (TIPO_NACIONAL,     'Nacional'),
        (TIPO_DEPARTAMENTO, 'Departamental'),
    ]

    tipo            = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_NACIONAL)
    parametro       = models.CharField(max_length=100, blank=True, default='')  # '' = nacional; nombre dpto = departamental
    ano_referencia  = models.IntegerField()

    # Estado — solo UNO puede estar activo por (tipo, parametro, ano_referencia)
    # Los anteriores se archivan automáticamente al regenerar
    ESTADO_ACTIVO   = 'activo'
    ESTADO_ARCHIVADO = 'archivado'
    ESTADO_CHOICES  = [
        (ESTADO_ACTIVO,    'Activo'),
        (ESTADO_ARCHIVADO, 'Archivado'),
    ]
    estado          = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_ACTIVO)

    # Análisis completo en Markdown
    analisis_md     = models.TextField()

    # Secciones individuales (parseadas del markdown para render selectivo)
    situacion       = models.TextField(blank=True)
    geografia       = models.TextField(blank=True)
    prediccion      = models.TextField(blank=True)
    brecha          = models.TextField(blank=True)
    recomendacion   = models.TextField(blank=True)

    # Metadatos del modelo IA
    modelo_ia       = models.CharField(max_length=100, default='claude-sonnet-4-6')
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    tokens_input    = models.IntegerField(null=True, blank=True)
    tokens_output   = models.IntegerField(null=True, blank=True)

    class Meta:
        # No unique_together — permitimos múltiples versiones por (tipo, parametro, año)
        # Solo uno tendrá estado='activo' a la vez; los demás quedan como 'archivado'
        indexes = [
            models.Index(fields=['tipo', 'parametro', 'ano_referencia', 'estado']),
        ]
        ordering = ['-fecha_generacion']
        verbose_name = 'Análisis IA - Inglés'
        verbose_name_plural = 'Análisis IA - Inglés'

    def __str__(self):
        ref = self.parametro or 'nacional'
        return f"[{self.estado}] {self.tipo} {ref} {self.ano_referencia} ({self.fecha_generacion:%Y-%m-%d %H:%M})"
