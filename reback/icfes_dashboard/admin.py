import csv
from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect

from .models import Campaign, CampaignProspect


# ============================================================================
# ACCIONES REUTILIZABLES
# ============================================================================

def export_csv(modeladmin, request, queryset):
    """Exporta prospectos seleccionados a CSV listo para envío."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="prospectos_campaña.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Colegio', 'Rector', 'Email', 'Teléfono',
        'Municipio', 'Departamento', 'Ranking Ciudad',
        'Puntaje Global', 'Demo URL', 'Estado'
    ])
    for p in queryset:
        writer.writerow([
            p.nombre_colegio, p.rector, p.email, p.telefono,
            p.municipio, p.departamento, p.rank_municipio,
            round(p.avg_punt_global, 1), p.demo_url, p.get_estado_display()
        ])
    return response

export_csv.short_description = "⬇ Exportar seleccionados a CSV"


def marcar_enviado(modeladmin, request, queryset):
    updated = queryset.filter(estado='pendiente').update(
        estado='enviado', fecha_envio=timezone.now()
    )
    messages.success(request, f"{updated} prospecto(s) marcados como enviados.")

marcar_enviado.short_description = "✉ Marcar como Email enviado"


def marcar_respondio(modeladmin, request, queryset):
    updated = queryset.update(estado='respondio', fecha_respuesta=timezone.now())
    messages.success(request, f"{updated} prospecto(s) marcados como Respondió.")

marcar_respondio.short_description = "💬 Marcar como Respondió"


def marcar_demo(modeladmin, request, queryset):
    updated = queryset.update(estado='demo')
    messages.success(request, f"{updated} prospecto(s) marcados como Demo agendada.")

marcar_demo.short_description = "📅 Marcar como Demo agendada"


def marcar_cliente(modeladmin, request, queryset):
    updated = queryset.update(estado='cliente')
    messages.success(request, f"{updated} prospecto(s) marcados como Cliente pagando.")

marcar_cliente.short_description = "🏆 Marcar como Cliente pagando"


# ============================================================================
# ADMIN: CAMPAIGN PROSPECT (tabla de detalle)
# ============================================================================

@admin.register(CampaignProspect)
class CampaignProspectAdmin(admin.ModelAdmin):
    list_display   = [
        'nombre_colegio', 'rector', 'email', 'municipio',
        'rank_ciudad', 'puntaje', 'estado_badge', 'demo_link', 'fecha_envio'
    ]
    list_filter    = ['campaign', 'estado', 'municipio', 'departamento']
    search_fields  = ['nombre_colegio', 'rector', 'email', 'municipio']
    ordering       = ['municipio', 'rank_municipio']
    actions        = [marcar_enviado, marcar_respondio, marcar_demo, marcar_cliente, export_csv]
    readonly_fields = ['demo_url', 'fecha_envio', 'fecha_respuesta']

    fieldsets = (
        ('Datos del Colegio', {
            'fields': ('campaign', 'nombre_colegio', 'rector', 'email',
                       'telefono', 'municipio', 'departamento',
                       'avg_punt_global', 'rank_municipio', 'demo_url')
        }),
        ('Tracking de Campaña', {
            'fields': ('estado', 'fecha_envio', 'fecha_respuesta', 'notas')
        }),
    )

    def rank_ciudad(self, obj):
        return f"#{obj.rank_municipio}"
    rank_ciudad.short_description = "Rank Ciudad"
    rank_ciudad.admin_order_field = 'rank_municipio'

    def puntaje(self, obj):
        return round(obj.avg_punt_global, 1)
    puntaje.short_description = "Puntaje"
    puntaje.admin_order_field = 'avg_punt_global'

    def estado_badge(self, obj):
        colors = {
            'pendiente':  '#6c757d',
            'enviado':    '#0d6efd',
            'respondio':  '#fd7e14',
            'demo':       '#6f42c1',
            'trial':      '#20c997',
            'cliente':    '#198754',
            'descartado': '#dc3545',
        }
        color = colors.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"

    def demo_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank" style="font-size:11px;">Ver demo ↗</a>',
            obj.demo_url
        )
    demo_link.short_description = "Demo"


# ============================================================================
# INLINE para Campaign → Prospects
# ============================================================================

class CampaignProspectInline(admin.TabularInline):
    model          = CampaignProspect
    extra          = 0
    max_num        = 0              # Solo lectura, no agregar manualmente
    can_delete     = False
    fields         = ['nombre_colegio', 'rector', 'email', 'municipio',
                      'rank_municipio', 'avg_punt_global', 'estado']
    readonly_fields = ['nombre_colegio', 'rector', 'email', 'municipio',
                       'rank_municipio', 'avg_punt_global']
    ordering       = ['municipio', 'rank_municipio']
    show_change_link = True


# ============================================================================
# ADMIN: CAMPAIGN (vista principal con botón LANZAR)
# ============================================================================

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display  = [
        'nombre', 'lote', 'estado_badge', 'pipeline_resumen',
        'nombre_remitente', 'email_remitente',
        'ciudades_objetivo', 'fecha_lanzamiento'
    ]
    list_filter   = ['estado', 'lote']
    search_fields = ['nombre', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_lanzamiento', 'fecha_completada', 'pipeline_detalle']
    inlines       = [CampaignProspectInline]

    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'lote', 'estado', 'descripcion')
        }),
        ('Configuración de envío', {
            'fields': ('nombre_remitente', 'email_remitente')
        }),
        ('Parámetros del lote', {
            'fields': ('ciudades_objetivo', 'top_n_por_ciudad')
        }),
        ('Pipeline actual', {
            'fields': ('pipeline_detalle',)
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_lanzamiento', 'fecha_completada'),
            'classes': ('collapse',)
        }),
    )

    # ------------------------------------------------------------------
    # URLs personalizadas para el botón LANZAR
    # ------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/lanzar/',
                self.admin_site.admin_view(self.lanzar_campana_view),
                name='campaign_lanzar',
            ),
            path(
                '<int:pk>/completar/',
                self.admin_site.admin_view(self.completar_campana_view),
                name='campaign_completar',
            ),
        ]
        return custom + urls

    def lanzar_campana_view(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)
        if campaign.estado == 'borrador':
            campaign.estado = 'activa'
            campaign.fecha_lanzamiento = timezone.now()
            campaign.save()
            messages.success(
                request,
                f"🚀 Campaña «{campaign.nombre}» lanzada. "
                f"{campaign.total_prospectos} prospectos listos para contactar."
            )
        else:
            messages.warning(request, f"La campaña ya estaba en estado: {campaign.get_estado_display()}")
        return redirect(reverse('admin:icfes_dashboard_campaign_change', args=[pk]))

    def completar_campana_view(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)
        campaign.estado = 'completada'
        campaign.fecha_completada = timezone.now()
        campaign.save()
        messages.success(request, f"✅ Campaña «{campaign.nombre}» marcada como completada.")
        return redirect(reverse('admin:icfes_dashboard_campaign_change', args=[pk]))

    # ------------------------------------------------------------------
    # Columnas y campos calculados
    # ------------------------------------------------------------------

    def estado_badge(self, obj):
        colors = {
            'borrador':   '#6c757d',
            'activa':     '#198754',
            'pausada':    '#fd7e14',
            'completada': '#0d6efd',
        }
        color = colors.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:4px;font-weight:600;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"

    def pipeline_resumen(self, obj):
        s = obj.stats
        if s['total'] == 0:
            return "Sin prospectos"
        return format_html(
            '<span style="font-size:11px;">'
            '📋 {total} | ✉ {enviado} | 💬 {respondio} | '
            '📅 {demo} | 🧪 {trial} | 🏆 {cliente}'
            '</span>',
            **s
        )
    pipeline_resumen.short_description = "Pipeline"

    def pipeline_detalle(self, obj):
        s = obj.stats
        if s['total'] == 0:
            return "Importa prospectos con: python manage.py import_campaign_prospects"
        rows = [
            ('Total prospectos', s['total'], ''),
            ('Pendiente de envío', s['pendiente'], '#6c757d'),
            ('Email enviado', s['enviado'], '#0d6efd'),
            ('Respondió', s['respondio'], '#fd7e14'),
            ('Demo agendada', s['demo'], '#6f42c1'),
            ('Trial activo', s['trial'], '#20c997'),
            ('Cliente pagando', s['cliente'], '#198754'),
            ('Descartado', s['descartado'], '#dc3545'),
        ]
        html = '<table style="border-collapse:collapse;min-width:250px;">'
        for label, count, color in rows:
            badge = (f'<span style="background:{color};color:#fff;padding:1px 7px;'
                     f'border-radius:3px;font-size:11px;">{count}</span>'
                     if color else f'<strong>{count}</strong>')
            html += f'<tr><td style="padding:3px 12px 3px 0;">{label}</td><td>{badge}</td></tr>'
        html += '</table>'
        return format_html(html)
    pipeline_detalle.short_description = "Pipeline detallado"

    # ------------------------------------------------------------------
    # Botón LANZAR en el change_view
    # ------------------------------------------------------------------

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            extra_context['show_lanzar_btn']   = (obj.estado == 'borrador')
            extra_context['show_completar_btn'] = (obj.estado == 'activa')
            extra_context['lanzar_url'] = reverse('admin:campaign_lanzar',   args=[obj.pk])
            extra_context['completar_url'] = reverse('admin:campaign_completar', args=[obj.pk])
        return super().change_view(request, object_id, form_url, extra_context)

    class Media:
        css = {'all': []}

    # Inyectar botones en el submit row via change_form_template
    change_form_template = 'admin/campaign_change_form.html'
