"""
Security middleware: blocks well-known vulnerability scanner patterns.
Returns 404 immediately, before any view logic or DB access.
"""
import re

from django.http import HttpResponseNotFound


# Matches paths that only scanners would probe on a Django/Python app.
_BLOCKED_PATH_RE = re.compile(
    r"(?:"
    r"\.php(?:[/?#]|$)"                          # .php files
    r"|\.asp(?:x)?(?:[/?#]|$)"                   # .asp / .aspx
    r"|\.jsp(?:[/?#]|$)"                         # .jsp
    r"|/\.env(?:[/?#]|$)"                        # .env credential files
    r"|/\.git(?:/|$)"                            # .git directory
    r"|/\.aws(?:/|$)"                            # AWS credentials
    r"|/wp-(?:admin|login|content|includes)"     # WordPress
    r"|/phpmyadmin"                              # phpMyAdmin
    r"|/xmlrpc\.php"                             # WordPress XML-RPC
    r"|/cgi-bin/"                                # CGI scripts
    r"|/etc/passwd"                              # Unix credential probe
    r")",
    re.IGNORECASE,
)


class ScannerBlockMiddleware:
    """Drop requests that match well-known vulnerability scanner patterns."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _BLOCKED_PATH_RE.search(request.path_info or ""):
            return HttpResponseNotFound()
        return self.get_response(request)
