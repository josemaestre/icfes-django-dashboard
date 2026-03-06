"""Middleware to normalize URL paths: duplicate slashes and non-ASCII characters."""
import re
import unicodedata

from django.http import HttpResponsePermanentRedirect


class SlashNormalizeMiddleware:
    """
    301-redirects paths with:
    - Duplicate slashes  (//icfes/ → /icfes/)
    - Non-ASCII chars    (/peque½os/ → /pequeos/  |  /pequeños/ → /pequenos/)

    Handles crawlers (Bingbot, Googlebot) that arrive with stale URLs containing
    accented or mis-encoded characters that Django's <slug:> converter rejects.
    """

    # Slug-safe characters: lowercase letters, digits, hyphens, underscores
    _SLUG_SAFE = re.compile(r'[^a-z0-9\-_/.]')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # 1. Fix duplicate slashes
        normalized = re.sub(r"/{2,}", "/", path)

        # 2. If non-ASCII chars present, apply NFKD normalization → ASCII
        if any(ord(c) > 127 for c in normalized):
            nfkd = unicodedata.normalize('NFKD', normalized)
            normalized = nfkd.encode('ascii', 'ignore').decode('ascii')
            # Remove any leftover non-slug-safe chars (can appear after NFKD drop)
            normalized = self._SLUG_SAFE.sub('', normalized)
            # Collapse multiple dashes that may result from dropped chars
            normalized = re.sub(r'-{2,}', '-', normalized)

        if normalized != path:
            qs = request.META.get("QUERY_STRING", "")
            new_url = normalized + (f"?{qs}" if qs else "")
            return HttpResponsePermanentRedirect(new_url)

        return self.get_response(request)
