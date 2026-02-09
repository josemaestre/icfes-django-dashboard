"""
Modelos para el sistema de suscripciones freemium.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date


class SubscriptionPlan(models.Model):
    """Planes de suscripción disponibles para ICFES Analytics."""
    
    TIER_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]
    
    # Identificación
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Límites de uso
    max_queries_per_day = models.IntegerField(
        help_text="Número máximo de consultas al dashboard por día"
    )
    max_export_rows = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Máximo de filas para exportación (null = ilimitado)"
    )
    
    # Acceso a API
    api_access = models.BooleanField(default=False)
    api_rate_limit = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Requests por hora (null = ilimitado)"
    )
    
    # Permisos de acceso geográfico
    access_regions = models.BooleanField(
        default=True,
        help_text="Acceso a datos agregados por región"
    )
    access_departments = models.BooleanField(
        default=False,
        help_text="Acceso a datos por departamento"
    )
    access_municipalities = models.BooleanField(
        default=False,
        help_text="Acceso a datos por municipio"
    )
    access_schools = models.BooleanField(
        default=False,
        help_text="Acceso a datos de colegios individuales"
    )
    
    # Límites temporales
    years_of_data = models.IntegerField(
        default=3,
        help_text="Años de datos históricos disponibles"
    )
    
    # Permisos de exportación
    export_csv = models.BooleanField(default=False)
    export_excel = models.BooleanField(default=False)
    export_pdf = models.BooleanField(default=False)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['price_monthly']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
    
    def __str__(self):
        return f"{self.name} (${self.price_monthly}/mo)"


class UserSubscription(models.Model):
    """Suscripción activa de un usuario."""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    
    # Fechas
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Null = suscripción activa indefinidamente"
    )
    is_active = models.BooleanField(default=True)
    
    # Información de pago Stripe
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    
    # Información de pago Wompi (Colombia)
    wompi_subscription_id = models.CharField(max_length=255, blank=True, default="")
    wompi_payment_method_id = models.CharField(max_length=255, blank=True, default="")
    
    # Tracking de uso diario
    queries_today = models.IntegerField(default=0)
    last_query_date = models.DateField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"
    
    def reset_daily_queries_if_needed(self):
        """Resetea el contador de queries si es un nuevo día."""
        today = date.today()
        if self.last_query_date != today:
            self.queries_today = 0
            self.last_query_date = today
            self.save(update_fields=['queries_today', 'last_query_date'])
    
    def can_make_query(self):
        """Verifica si el usuario puede hacer otra query."""
        self.reset_daily_queries_if_needed()
        return self.queries_today < self.plan.max_queries_per_day
    
    def increment_query_count(self):
        """Incrementa el contador de queries."""
        self.reset_daily_queries_if_needed()
        self.queries_today += 1
        self.save(update_fields=['queries_today'])
    
    def get_remaining_queries(self):
        """Retorna el número de queries restantes hoy."""
        self.reset_daily_queries_if_needed()
        return max(0, self.plan.max_queries_per_day - self.queries_today)


class QueryLog(models.Model):
    """Log de consultas para analytics y debugging."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='query_logs'
    )
    endpoint = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    query_params = models.JSONField(null=True, blank=True)
    
    # Información adicional
    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Tiempo de respuesta en milisegundos"
    )
    status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code de la respuesta"
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Query Log'
        verbose_name_plural = 'Query Logs'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['endpoint', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.endpoint} - {self.timestamp}"
