"""
Rate limiting middleware: blocks IPs that exceed request thresholds.
Uses Django's Redis cache — no extra dependencies required.
Fail-open: if Redis is down, rate limiting is disabled (requests pass through).
"""
import logging

from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger(__name__)

# Paths worth rate-limiting (scraper targets)
_RATE_LIMITED_PREFIXES = (
    "/icfes/colegio/",
    "/icfes/cuadrante/",
    "/icfes/dashboard/",
    "/api/",
)

# Thresholds: MAX_REQUESTS per IP within WINDOW_SECONDS
_MAX_REQUESTS = 40
_WINDOW_SECONDS = 60


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    remote = request.META.get("REMOTE_ADDR", "")
    return (xff.split(",")[-1].strip() if xff else remote) or "unknown"


class RateLimitMiddleware:
    """Return 429 for IPs that exceed the per-minute request limit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info or ""
        if not any(path.startswith(p) for p in _RATE_LIMITED_PREFIXES):
            return self.get_response(request)

        ip = _client_ip(request)
        key = f"rl:{ip}"

        # cache.add sets key only if absent (atomic); returns True on first hit.
        if not cache.add(key, 1, timeout=_WINDOW_SECONDS):
            try:
                count = cache.incr(key)
            except Exception:
                # Redis down — fail open
                return self.get_response(request)

            if count > _MAX_REQUESTS:
                logger.warning("rate_limit blocked ip=%s path=%s count=%s", ip, path, count)
                return HttpResponse(status=429, content="Too Many Requests")

        return self.get_response(request)
