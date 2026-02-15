import json

from django.shortcuts import redirect, render
from django.templatetags.static import static

from django.contrib.auth.decorators import login_required
from django.template import TemplateDoesNotExist


def landing_page_view(request):
    """
    Landing page - public, no login required.
    """
    # Canonical URL is now the root
    canonical_url = request.build_absolute_uri("/")
    # Ensure no trailing slash issues if needed, but build_absolute_uri('/') usually returns ".../"
    
    og_image = request.build_absolute_uri(
        static("images/screenshots/dashboard_main.png")
    )

    seo_title = (
        "ICFES Analytics: Ranking ICFES por colegio, municipio y departamento"
    )
    seo_description = (
        "Analiza resultados ICFES históricos en Colombia: ranking por colegio, "
        "departamento y municipio, tendencias por año y reportes accionables."
    )

    structured_data = [
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "ICFES Analytics",
            "url": canonical_url,
            "logo": request.build_absolute_uri(static("images/logo-icfes-light.svg")),
        },
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "ICFES Analytics",
            "url": canonical_url,
            "potentialAction": {
                "@type": "SearchAction",
                "target": request.build_absolute_uri(
                    "/icfes/api/search/colegios/?q={search_term_string}"
                ),
                "query-input": "required name=search_term_string",
            },
        },
    ]

    return render(
        request,
        "pages/landing.html",
        {
            "seo": {
                "title": seo_title,
                "description": seo_description,
                "keywords": (
                    "ranking icfes por departamento, promedio icfes por colegio, "
                    "puntaje global icfes historico, mejores colegios icfes colombia"
                ),
                "canonical_url": canonical_url,
                "og_image": og_image,
            },
            "structured_data_json": json.dumps(structured_data, ensure_ascii=False),
        },
    )


def home_redirect_view(request):
    """
    Redirect /landing/ traffic to root / to avoid duplicate content.
    """
    return redirect("pages:home", permanent=True)


@login_required
def root_page_view(request):
    try:
        return render(request, 'pages/index.html')
    except TemplateDoesNotExist:
        return render(request, 'pages/pages-404.html')


def dynamic_pages_view(request, template_name):
    """
    Render dynamic pages. 
    Pricing page is public, all other pages require login.
    """
    # Public pages that don't require authentication
    public_pages = ['pages-pricing']
    
    # Require login for non-public pages
    if template_name not in public_pages and not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    try:
        return render(request, f'pages/{template_name}.html')
    except TemplateDoesNotExist:
        return render(request, f'pages/pages-404.html')


def pricing_page_view(request):
    """
    Pricing page - public.
    """
    canonical_url = request.build_absolute_uri(request.path)
    
    seo_title = "Planes y Precios - ICFES Analytics"
    seo_description = (
        "Conoce nuestros planes Free, Basic, Premium y Enterprise. "
        "Escoge la mejor opción para acceder a datos históricos y análisis detallados del ICFES."
    )

    return render(
        request,
        "pages/pricing.html",
        {
            "seo": {
                "title": seo_title,
                "description": seo_description,
                "canonical_url": canonical_url,
            }
        },
    )



