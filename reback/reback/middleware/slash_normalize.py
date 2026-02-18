"""Middleware to normalize duplicate slashes in URL paths."""
import re

from django.http import HttpResponsePermanentRedirect


class SlashNormalizeMiddleware:
    """Redirects paths with duplicate slashes (e.g. //icfes/ -> /icfes/)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        normalized = re.sub(r"/{2,}", "/", path)
        if normalized != path:
            qs = request.META.get("QUERY_STRING", "")
            new_url = normalized
            if qs:
                new_url = f"{normalized}?{qs}"
            return HttpResponsePermanentRedirect(new_url)
        return self.get_response(request)
