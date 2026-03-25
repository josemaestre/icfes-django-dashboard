"""
Redirect non-canonical hosts to the primary domain.

Railway exposes an internal *.up.railway.app URL in addition to any custom
domain. Bots and crawlers that hit the internal URL create duplicate content
and inflate Railway egress traffic. This middleware 301-redirects all such
requests to the canonical domain defined in settings.CANONICAL_HOST.
"""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.canonical = getattr(settings, 'CANONICAL_HOST', None)

    def __call__(self, request):
        if not self.canonical:
            return self.get_response(request)

        # Health check is probed by Railway against the internal container IP,
        # not the canonical domain — skip redirect so the probe gets 200 OK.
        if request.path == '/health/':
            return self.get_response(request)

        host = request.get_host().split(':')[0]  # strip port if present
        if host != self.canonical:
            url = f"https://{self.canonical}{request.get_full_path()}"
            return HttpResponsePermanentRedirect(url)

        return self.get_response(request)
