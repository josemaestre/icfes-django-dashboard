"""
Utility functions for school landing pages.
"""
from django.utils.text import slugify
import re


def generate_school_slug(nombre_colegio, municipio):
    """
    Generate SEO-friendly slug for school landing page.
    
    Args:
        nombre_colegio: School name
        municipio: Municipality name
    
    Returns:
        str: URL-safe slug
    
    Example:
        >>> generate_school_slug("Colegio San José", "Bogotá D.C.")
        'colegio-san-jose-bogota-dc'
    """
    # Combine school name and municipality
    combined = f"{nombre_colegio} {municipio}"
    
    # Remove special characters and normalize
    combined = re.sub(r'[^\w\s-]', '', combined.lower())
    
    # Create slug
    slug = slugify(combined)
    
    return slug


def calculate_ranking(puntaje, all_scores):
    """
    Calculate national ranking based on score.
    
    Args:
        puntaje: School's score
        all_scores: List of all schools' scores
    
    Returns:
        dict: {'rank': int, 'total': int, 'percentile': float}
    """
    sorted_scores = sorted(all_scores, reverse=True)
    rank = sorted_scores.index(puntaje) + 1 if puntaje in sorted_scores else None
    total = len(sorted_scores)
    percentile = ((total - rank + 1) / total * 100) if rank else None
    
    return {
        'rank': rank,
        'total': total,
        'percentile': round(percentile, 1) if percentile else None
    }


def generate_ai_insights(colegio_data, comparacion_data):
    """
    Generate AI-powered insights for school performance.
    
    Args:
        colegio_data: School's performance data
        comparacion_data: Comparison with averages
    
    Returns:
        dict: {'strengths': list, 'opportunities': list}
    """
    strengths = []
    opportunities = []
    
    # Analyze subject performance
    subjects = {
        'Matemáticas': ('punt_matematicas', 'brecha_matematicas_municipal'),
        'Lectura Crítica': ('punt_lectura_critica', 'brecha_lectura_municipal'),
        'Ciencias Naturales': ('punt_ciencias_naturales', 'brecha_ciencias_municipal'),
        'Sociales': ('punt_sociales_ciudadanas', 'brecha_sociales_municipal'),
        'Inglés': ('punt_ingles', 'brecha_ingles_municipal'),
    }
    
    for subject_name, (score_field, gap_field) in subjects.items():
        if comparacion_data and gap_field in comparacion_data:
            gap = comparacion_data[gap_field]
            
            if gap and gap > 5:
                strengths.append(f"{subject_name}: +{gap:.0f} pts sobre promedio municipal")
            elif gap and gap < -5:
                opportunities.append(f"{subject_name}: {gap:.0f} pts bajo promedio municipal")
    
    # Add generic insights if none found
    if not strengths:
        strengths.append("Rendimiento estable en el tiempo")
    
    if not opportunities:
        opportunities.append("Continuar fortaleciendo todas las áreas")
    
    return {
        'strengths': strengths[:3],  # Top 3
        'opportunities': opportunities[:3]  # Top 3
    }
