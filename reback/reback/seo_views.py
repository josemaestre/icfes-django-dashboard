from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse


def _public_base_url(request):
    configured = getattr(settings, "PUBLIC_SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def robots_txt(request):
    base = _public_base_url(request)
    lines = [
        # General crawlers
        "User-agent: *",
        "Allow: /",
        "",
        # Private/product areas that should not be crawled.
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /users/",
        "Disallow: /payments/",
        "Disallow: /dashboard/",
        "Disallow: /app/",
        "",
        # Programmatic/data endpoints that don't add search value.
        "Disallow: /icfes/api/",
        "Disallow: /icfes/export/",
        "Disallow: /email-graphs/",
        "Disallow: /social-card/",
        "Disallow: /*.map$",
        "",
        # SEO/audit bots — throttled (aportan auditorías pero no tráfico)
        "User-agent: SemrushBot",
        "Crawl-delay: 10",
        "",
        "User-agent: AhrefsBot",
        "Crawl-delay: 10",
        "",
        # Bots que no aportan tráfico relevante — bloqueados
        "User-agent: Amazonbot",
        "Disallow: /",
        "",
        "User-agent: DotBot",
        "Disallow: /",
        "",
        "User-agent: MJ12bot",
        "Disallow: /",
        "",
        # AI crawlers — explicitly allowed for public educational content
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: ChatGPT-User",
        "Allow: /",
        "",
        "User-agent: OAI-SearchBot",
        "Allow: /",
        "",
        "User-agent: Google-Extended",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        "User-agent: anthropic-ai",
        "Allow: /",
        "",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def llms_txt(request):
    """
    Serve llms.txt — machine-readable site description for AI crawlers.
    Spec: https://llmstxt.org
    """
    base = _public_base_url(request)
    content = f"""# ICFES Analytics

> La plataforma de análisis educativo más completa de Colombia.
> Rankings, tendencias y análisis de colegios basados en 17.7 millones de registros
> del examen ICFES Saber 11 (1996–2024).

## Qué es ICFES Analytics

ICFES Analytics transforma los datos abiertos del examen de Estado colombiano (Saber 11)
en inteligencia educativa accionable. Permite comparar colegios, explorar tendencias
históricas, identificar brechas por región y estrato, y encontrar los mejores colegios
por materia o municipio.

## Cobertura de datos

- 22,684 colegios indexados a nivel nacional
- 17.7 millones de registros de estudiantes
- 28 años de historia: 1996–2024
- 32 departamentos y 1,100+ municipios de Colombia

## Secciones principales

- [Ranking nacional de colegios]({base}/icfes/ranking/)
- [Ranking por departamento]({base}/icfes/departamentos/)
- [Dashboard histórico 1996–2024]({base}/icfes/historia/)
- [Dashboard de inglés MCER]({base}/icfes/ingles/)
- [Colegios bilingues]({base}/icfes/colegios-bilingues/)
- [Colegios que más mejoraron]({base}/icfes/colegios-que-mas-mejoraron/)
- [Ranking de matemáticas]({base}/icfes/materia/matematicas/)
- [Ranking de inglés]({base}/icfes/materia/ingles/)

## Fuente de datos

Los microdatos provienen del ICFES (Instituto Colombiano para la Evaluación de la Educación),
entidad pública colombiana. Los datos son de acceso público bajo la política de datos abiertos
del gobierno colombiano.

## Uso permitido

El contenido factual (puntajes, rankings, estadísticas) proviene de datos públicos del ICFES.
Los análisis, visualizaciones y modelos predictivos son propiedad de ICFES Analytics.
"""
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "public, max-age=86400"  # 24h
    return response


def favicon_view(request):
    for static_dir in settings.STATICFILES_DIRS:
        path = Path(static_dir) / "images" / "favicon.ico"
        if path.exists():
            response = FileResponse(path.open("rb"), content_type="image/x-icon")
            response["Cache-Control"] = "public, max-age=604800"  # 7 days
            return response
    raise Http404("favicon.ico not found")


def bing_site_auth(request):
    """
    Serve Bing verification file from project root.
    Expected public URL: /BingSiteAuth.xml
    """
    file_path = Path(settings.BASE_DIR) / "BingSiteAuth.xml"
    if not file_path.exists():
        raise Http404("BingSiteAuth.xml no encontrado")
    return FileResponse(file_path.open("rb"), content_type="application/xml")


def indexnow_key_txt(request):
    """
    Serve IndexNow key verification file content.
    Expected public URL: /<INDEXNOW_KEY>.txt
    """
    key = getattr(settings, "INDEXNOW_KEY", "").strip()
    if not key:
        raise Http404("INDEXNOW_KEY no configurado")
    response = HttpResponse(key, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response
