"""
Export views for ICFES Dashboard.
Provides CSV and PDF export functionality for school reports.
"""
import csv
import logging
from datetime import datetime
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from reback.users.decorators import subscription_required
from .db_utils import get_duckdb_connection

logger = logging.getLogger(__name__)


# =============================================================================
# CSV EXPORTS (Basic Plan)
# =============================================================================

@login_required
@subscription_required(tier='basic')
def export_school_search_csv(request):
    """
    Export school search results to CSV.
    Requires Basic subscription or higher.
    """
    query = request.GET.get('query', '')
    ano = request.GET.get('ano', 2024)
    
    logger.info(f"CSV Export: School search - query='{query}', ano={ano}, user={request.user.email}")
    
    try:
        with get_duckdb_connection() as conn:
            # Query school data
            sql = """
                SELECT 
                    c.cole_nombre_establecimiento as nombre,
                    c.cole_depto_ubicacion as departamento,
                    c.cole_mcpio_ubicacion as municipio,
                    c.cole_naturaleza as naturaleza,
                    a.punt_global as puntaje_global,
                    a.punt_lectura_critica as lectura,
                    a.punt_matematicas as matematicas,
                    a.punt_sociales_ciudadanas as sociales,
                    a.punt_ciencias_naturales as ciencias,
                    a.punt_ingles as ingles,
                    COUNT(*) as num_estudiantes
                FROM gold.dim_colegios c
                LEFT JOIN gold.fct_icfes_analytics a 
                    ON c.colegio_sk = a.colegio_sk 
                    AND a.ano = ?
                WHERE c.cole_nombre_establecimiento ILIKE ?
                GROUP BY 
                    c.cole_nombre_establecimiento,
                    c.cole_depto_ubicacion,
                    c.cole_mcpio_ubicacion,
                    c.cole_naturaleza,
                    a.punt_global,
                    a.punt_lectura_critica,
                    a.punt_matematicas,
                    a.punt_sociales_ciudadanas,
                    a.punt_ciencias_naturales,
                    a.punt_ingles
                ORDER BY a.punt_global DESC NULLS LAST
                LIMIT 500
            """
            
            results = conn.execute(sql, [ano, f'%{query}%']).fetchall()
            
            # Create CSV response
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            filename = f"colegios_{query.replace(' ', '_')}_{ano}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Write CSV
            writer = csv.writer(response)
            writer.writerow([
                'Nombre', 'Departamento', 'Municipio', 'Naturaleza',
                'Puntaje Global', 'Lectura', 'Matemáticas', 'Sociales', 
                'Ciencias', 'Inglés', 'Estudiantes'
            ])
            
            for row in results:
                writer.writerow(row)
            
            logger.info(f"CSV Export successful: {len(results)} schools exported")
            return response
        
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise


@login_required
@subscription_required(tier='basic')
def export_ranking_csv(request):
    """
    Export departmental ranking to CSV.
    Requires Basic subscription or higher.
    """
    ano = request.GET.get('ano', 2024)
    
    logger.info(f"CSV Export: Ranking - ano={ano}, user={request.user.email}")
    
    try:
        with get_duckdb_connection() as conn:
            sql = """
                SELECT 
                    cole_depto_ubicacion as departamento,
                    ROUND(AVG(punt_global), 2) as promedio_global,
                    ROUND(AVG(punt_lectura_critica), 2) as promedio_lectura,
                    ROUND(AVG(punt_matematicas), 2) as promedio_matematicas,
                    ROUND(AVG(punt_sociales_ciudadanas), 2) as promedio_sociales,
                    ROUND(AVG(punt_ciencias_naturales), 2) as promedio_ciencias,
                    ROUND(AVG(punt_ingles), 2) as promedio_ingles,
                    COUNT(*) as total_estudiantes
                FROM gold.fct_icfes_analytics
                WHERE ano = ?
                GROUP BY cole_depto_ubicacion
                ORDER BY promedio_global DESC
            """
            
            results = conn.execute(sql, [ano]).fetchall()
            
            # Create CSV response
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="ranking_departamental_{ano}.csv"'
            
            # Write CSV
            writer = csv.writer(response)
            writer.writerow([
                'Departamento', 'Promedio Global', 'Lectura', 'Matemáticas',
                'Sociales', 'Ciencias', 'Inglés', 'Total Estudiantes'
            ])
            
            for row in results:
                writer.writerow(row)
            
            logger.info(f"CSV Export successful: {len(results)} departments exported")
            return response
        
    except Exception as e:
        logger.error(f"Error exporting ranking CSV: {e}")
        raise


# =============================================================================
# PDF EXPORTS (Premium Plan)
# =============================================================================

@login_required
@subscription_required(tier='premium')
def export_school_report_pdf(request, colegio_sk):
    """
    Export detailed school report to PDF.
    Requires Premium subscription.
    """
    logger.info(f"PDF Export: School report - colegio_sk={colegio_sk}, user={request.user.email}")
    
    try:
        with get_duckdb_connection() as conn:
            # Get school info
            school_sql = """
                SELECT 
                    cole_nombre_establecimiento,
                    cole_depto_ubicacion,
                    cole_mcpio_ubicacion,
                    cole_naturaleza,
                    cole_calendario
                FROM gold.dim_colegios
                WHERE colegio_sk = ?
            """
            school = conn.execute(school_sql, [colegio_sk]).fetchone()
            
            if not school:
                return HttpResponse("Colegio no encontrado", status=404)
            
            # Get historical data (last 5 years)
            history_sql = """
                SELECT 
                    ano,
                    ROUND(AVG(punt_global), 2) as promedio_global,
                    ROUND(AVG(punt_lectura_critica), 2) as lectura,
                    ROUND(AVG(punt_matematicas), 2) as matematicas,
                    ROUND(AVG(punt_sociales_ciudadanas), 2) as sociales,
                    ROUND(AVG(punt_ciencias_naturales), 2) as ciencias,
                    ROUND(AVG(punt_ingles), 2) as ingles,
                    COUNT(*) as estudiantes
                FROM gold.fct_icfes_analytics
                WHERE colegio_sk = ?
                GROUP BY ano
                ORDER BY ano DESC
                LIMIT 5
            """
            history = conn.execute(history_sql, [colegio_sk]).fetchall()
            
            # Create PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#1f77b4'),
                spaceAfter=30,
            )
            title = Paragraph(f"Reporte: {school[0]}", title_style)
            story.append(title)
            
            # School info
            info_data = [
                ['Departamento:', school[1]],
                ['Municipio:', school[2]],
                ['Naturaleza:', school[3]],
                ['Calendario:', school[4] or 'N/A'],
            ]
            
            info_table = Table(info_data, colWidths=[2*inch, 4*inch])
            info_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Historical performance
            if history:
                story.append(Paragraph("Desempeño Histórico", styles['Heading2']))
                story.append(Spacer(1, 0.2*inch))
                
                history_data = [['Año', 'Global', 'Lectura', 'Matemáticas', 'Sociales', 'Ciencias', 'Inglés', 'Estudiantes']]
                for row in history:
                    history_data.append(list(row))
                
                history_table = Table(history_data, colWidths=[0.7*inch] * 8)
                history_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(history_table)
            
            # Footer
            story.append(Spacer(1, 0.5*inch))
            footer_text = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - ICFES Analytics Platform"
            footer = Paragraph(footer_text, styles['Normal'])
            story.append(footer)
            
            # Build PDF
            doc.build(story)
            
            # Return response
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="reporte_{colegio_sk}.pdf"'
            
            logger.info(f"PDF Export successful: {colegio_sk}")
            return response
        
    except Exception as e:
        logger.error(f"Error exporting PDF: {e}")
        raise


@login_required
@subscription_required(tier='premium')
def export_comparison_pdf(request):
    """
    Export school comparison to PDF.
    Requires Premium subscription.
    """
    colegio_ids = request.GET.getlist('colegios[]')
    ano = request.GET.get('ano', 2024)
    
    logger.info(f"PDF Export: Comparison - colegios={colegio_ids}, ano={ano}, user={request.user.email}")
    
    if not colegio_ids or len(colegio_ids) < 2:
        return HttpResponse("Se requieren al menos 2 colegios para comparar", status=400)
    
    try:
        with get_duckdb_connection() as conn:
            # Get comparison data
            placeholders = ','.join(['?' for _ in colegio_ids])
            sql = f"""
                SELECT 
                    c.cole_nombre_establecimiento as nombre,
                    c.cole_depto_ubicacion as departamento,
                    ROUND(AVG(a.punt_global), 2) as global,
                    ROUND(AVG(a.punt_lectura_critica), 2) as lectura,
                    ROUND(AVG(a.punt_matematicas), 2) as matematicas,
                    ROUND(AVG(a.punt_sociales_ciudadanas), 2) as sociales,
                    ROUND(AVG(a.punt_ciencias_naturales), 2) as ciencias,
                    ROUND(AVG(a.punt_ingles), 2) as ingles,
                    COUNT(*) as estudiantes
                FROM gold.dim_colegios c
                LEFT JOIN gold.fct_icfes_analytics a 
                    ON c.colegio_sk = a.colegio_sk 
                    AND a.ano = ?
                WHERE c.colegio_sk IN ({placeholders})
                GROUP BY c.cole_nombre_establecimiento, c.cole_depto_ubicacion
            """
            
            results = conn.execute(sql, [ano] + colegio_ids).fetchall()
            
            # Create PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title = Paragraph(f"Comparación de Colegios - {ano}", styles['Heading1'])
            story.append(title)
            story.append(Spacer(1, 0.3*inch))
            
            # Comparison table
            table_data = [['Colegio', 'Depto', 'Global', 'Lectura', 'Matemáticas', 'Sociales', 'Ciencias', 'Inglés', 'Est.']]
            for row in results:
                table_data.append(list(row))
            
            comparison_table = Table(table_data, colWidths=[2*inch, 1*inch, 0.6*inch, 0.6*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.5*inch])
            comparison_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            story.append(comparison_table)
            
            # Footer
            story.append(Spacer(1, 0.5*inch))
            footer_text = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - ICFES Analytics Platform"
            footer = Paragraph(footer_text, styles['Normal'])
            story.append(footer)
            
            # Build PDF
            doc.build(story)
            
            # Return response
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="comparacion_{ano}.pdf"'
            
            logger.info(f"PDF Export successful: {len(results)} schools compared")
            return response
        
    except Exception as e:
        logger.error(f"Error exporting comparison PDF: {e}")
        raise
