from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse


def robots_txt(request):
    base = request.build_absolute_uri("/").rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def bing_site_auth(request):
    """
    Serve Bing verification file from project root.
    Expected public URL: /BingSiteAuth.xml
    """
    file_path = Path(settings.BASE_DIR) / "BingSiteAuth.xml"
    if not file_path.exists():
        raise Http404("BingSiteAuth.xml no encontrado")
    return FileResponse(file_path.open("rb"), content_type="application/xml")
