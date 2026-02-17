"""
Middleware para capturar errores HTTP 4xx y 5xx.
Registra URL, método, status code, user-agent y traceback (para 5xx).
Escribe a console (stdout → Railway logs) y a archivo.
"""
import logging
import sys
import time
import traceback

logger = logging.getLogger("http_errors")


class ErrorLoggingMiddleware:
    """Logs all HTTP 4xx and 5xx responses with request details."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.exception_info = None

    def __call__(self, request):
        self.exception_info = None
        start_time = time.time()

        response = self.get_response(request)

        if response.status_code >= 400:
            duration = (time.time() - start_time) * 1000
            self._log_error(request, response, duration)

        return response

    def process_exception(self, request, exception):
        """Capture exception info before Django handles it."""
        self.exception_info = sys.exc_info()
        return None

    def _log_error(self, request, response, duration_ms):
        status = response.status_code
        method = request.method
        path = request.get_full_path()
        user_agent = request.META.get("HTTP_USER_AGENT", "-")
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "-"))
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        referer = request.META.get("HTTP_REFERER", "-")

        msg = (
            f"{status} | {method} {path} | {duration_ms:.0f}ms | "
            f"IP:{ip} | Referer:{referer} | UA:{user_agent}"
        )

        if status >= 500:
            if self.exception_info:
                tb = "".join(traceback.format_exception(*self.exception_info))
                msg += f"\nTraceback:\n{tb}"
            logger.error(msg)
        else:
            logger.warning(msg)
