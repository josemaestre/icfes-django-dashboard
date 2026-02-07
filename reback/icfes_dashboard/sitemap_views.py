import math
from xml.sax.saxutils import escape

from django.http import HttpResponse

from .db_utils import get_duckdb_connection, resolve_schema


SITEMAP_PAGE_SIZE = 40000


def _base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


def sitemap_index(request):
    base = _base_url(request)

    with get_duckdb_connection() as conn:
        count_query = "SELECT COUNT(*) FROM gold.dim_colegios_slugs"
        total = conn.execute(resolve_schema(count_query)).fetchone()[0]

    pages = max(1, math.ceil(total / SITEMAP_PAGE_SIZE))

    items = [f"{base}/sitemap-static.xml"]
    items.extend(f"{base}/sitemap-icfes-{i}.xml" for i in range(1, pages + 1))

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for loc in items:
        xml.append("  <sitemap>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append("  </sitemap>")
    xml.append("</sitemapindex>")

    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_static(request):
    base = _base_url(request)
    urls = [
        f"{base}/",
        f"{base}/landing/",
        f"{base}/pricing/",
        f"{base}/icfes/",
        f"{base}/icfes/colegio/",
    ]

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for loc in urls:
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append("    <changefreq>weekly</changefreq>")
        xml.append("    <priority>0.8</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")

    return HttpResponse("\n".join(xml), content_type="application/xml")


def sitemap_icfes(request, page):
    if page < 1:
        return HttpResponse(status=404)

    base = _base_url(request)
    limit = SITEMAP_PAGE_SIZE
    offset = (page - 1) * limit

    query = """
        SELECT slug
        FROM gold.dim_colegios_slugs
        ORDER BY slug
        LIMIT ? OFFSET ?
    """
    with get_duckdb_connection() as conn:
        rows = conn.execute(resolve_schema(query), [limit, offset]).fetchall()

    if not rows:
        return HttpResponse(status=404)

    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    xml.append("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">")
    for (slug,) in rows:
        loc = f"{base}/icfes/colegio/{slug}/"
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(loc)}</loc>")
        xml.append("    <changefreq>monthly</changefreq>")
        xml.append("    <priority>0.6</priority>")
        xml.append("  </url>")
    xml.append("</urlset>")

    return HttpResponse("\n".join(xml), content_type="application/xml")
