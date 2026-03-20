"""
Middleware that removes 'Cookie' from the Vary header for public landing pages.

Django's SessionMiddleware adds Vary: Cookie to every response as a safety measure.
For public pages (school/department/municipality landings) the content is identical
for all visitors, so keeping Cookie in Vary kills CDN caching on Railway's edge.

This middleware strips Cookie from Vary, marks the response public, and ensures
max-age is set so Railway's CDN knows how long to cache each page type.
"""

from django.utils.cache import patch_cache_control


# (prefix, max_age_seconds)
# Views using manual cache (cache.get/set) don't set Cache-Control headers,
# so we provide the TTL here to match the intended caching strategy.
_PUBLIC_PREFIXES = (
    ('/icfes/colegio/',       86400),   # 24 h — school landings
    ('/icfes/departamento/',  604800),  # 7 d  — department/municipality landings
    ('/icfes/municipio/',     604800),
    ('/icfes/departamentos/', 43200),   # 12 h — department index
    ('/icfes/ranking/',       21600),   # 6 h  — ranking pages
    ('/icfes/historico/',     43200),   # 12 h — historical pages
    ('/social-card/',         86400),   # 24 h — OG social card images (pure public, no user data)
)


class PublicCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        max_age = next(
            (ttl for prefix, ttl in _PUBLIC_PREFIXES if request.path.startswith(prefix)),
            None,
        )
        if max_age is None or response.status_code != 200:
            return response

        # Strip Cookie from Vary so CDN can cache regardless of session cookie
        vary = response.get('Vary', '')
        if vary:
            parts = [h.strip() for h in vary.split(',') if h.strip().lower() != 'cookie']
            if parts:
                response['Vary'] = ', '.join(parts)
            else:
                del response['Vary']

        # Set max-age only if the view didn't already set a longer one
        cc = response.get('Cache-Control', '')
        existing_max_age = None
        for part in cc.split(','):
            part = part.strip()
            if part.startswith('max-age='):
                try:
                    existing_max_age = int(part.split('=', 1)[1])
                except ValueError:
                    pass

        if existing_max_age is None or existing_max_age < max_age:
            patch_cache_control(response, public=True, max_age=max_age)
        else:
            patch_cache_control(response, public=True)

        return response
