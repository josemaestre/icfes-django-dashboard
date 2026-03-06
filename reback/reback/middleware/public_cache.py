"""
Middleware that removes 'Cookie' from the Vary header for public landing pages.

Django's SessionMiddleware adds Vary: Cookie to every response as a safety measure.
For public pages (school/department/municipality landings) the content is identical
for all visitors, so keeping Cookie in Vary kills CDN caching on Railway's edge.

This middleware strips Cookie from Vary and marks the response public so that
Railway's CDN can cache school and geographic landing pages at the edge.
"""

from django.utils.cache import patch_cache_control


# URL prefixes whose content is identical for every visitor
_PUBLIC_PREFIXES = (
    '/icfes/colegio/',
    '/icfes/departamento/',
    '/icfes/municipio/',
    '/icfes/departamentos/',
)


class PublicCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not any(request.path.startswith(p) for p in _PUBLIC_PREFIXES):
            return response

        # Only touch 200 OK responses
        if response.status_code != 200:
            return response

        # Strip Cookie from Vary so CDN can cache regardless of session cookie
        vary = response.get('Vary', '')
        if vary:
            parts = [h.strip() for h in vary.split(',') if h.strip().lower() != 'cookie']
            if parts:
                response['Vary'] = ', '.join(parts)
            else:
                del response['Vary']

        # Mark as publicly cacheable so Railway edge actually stores it
        patch_cache_control(response, public=True)

        return response
