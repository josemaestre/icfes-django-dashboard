"""
Performance and cache debug middleware.
"""
import logging
import time

from django.conf import settings


perf_logger = logging.getLogger("perf")
_NOISY_PATH_PREFIXES = ("/static/", "/media/")
_NOISY_PATHS = ("/favicon.ico", "/robots.txt", "/sitemap.xml")


class CacheDebugHeaderMiddleware:
    """
    Attach cache status as X-Cache response header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(settings, "CACHE_DEBUG_HEADER_ENABLED", False):
            response["X-Cache"] = getattr(request, "_cache_status", "BYPASS")
        return response


class PerfLoggingMiddleware:
    """
    Log path, status, latency, cache status and user-agent.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "PERF_LOGGING_ENABLED", False):
            return self.get_response(request)

        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        path = request.path or ""
        if path.startswith(_NOISY_PATH_PREFIXES) or path in _NOISY_PATHS:
            return response

        cache_status = response.get("X-Cache", getattr(request, "_cache_status", "BYPASS"))
        user_agent = request.META.get("HTTP_USER_AGENT", "-")[:160]

        perf_logger.info(
            "path=%s status=%s ms=%.1f cache=%s ua=%s",
            path,
            response.status_code,
            elapsed_ms,
            cache_status,
            user_agent,
        )
        return response
