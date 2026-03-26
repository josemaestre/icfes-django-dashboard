"""
Bot ban middleware: two-layer bot detection system.

Layer 1 — Honeypot:
  A hidden link placed in all public pages. Any IP that visits the
  honeypot URL is immediately banned for 24 hours. Real users never
  see or click it; scrapers that parse HTML do.

Layer 2 — Bad-behavior signals:
  404 responses on non-asset paths accumulate as signals per IP.
  When an IP exceeds SIGNAL_THRESHOLD signals in SIGNAL_WINDOW
  seconds, it is banned for BAN_DURATION seconds.

Ban checks run before any view logic — banned IPs never reach Django.

Legitimate crawlers (Googlebot, Meta, Bing, etc.) are fully exempt —
they feed our SEO and social media reputation.
"""
import logging

from django.core.cache import cache
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)

# Honeypot path — must match the hidden link added to all public templates.
HONEYPOT_PATH = "/icfes/data-export/"

# Redis key prefixes
_BAN_PREFIX    = "botban:"    # key: botban:{ip}  → ban reason (string)
_SIGNAL_PREFIX = "botsig:"   # key: botsig:{ip}  → signal counter (int)

# Thresholds
SIGNAL_THRESHOLD = 6    # bad signals before auto-ban
SIGNAL_WINDOW    = 60   # seconds — rolling window per IP
BAN_DURATION     = 86400  # seconds — 24 hours

# Paths that should NOT generate 404 signals (static assets, favicons, etc.)
_NOSIGNAL_PREFIXES = ("/static/", "/media/", "/favicon", "/robots.txt", "/sitemap")

# Legitimate crawlers exempt from all bot detection.
# These feed SEO rankings and social media previews — never ban them.
_GOOD_CRAWLERS = (
    # Google
    "googlebot",
    "google-inspectiontool",
    "google-safety",
    "adsbot-google",
    # Bing / Microsoft
    "bingbot",
    "bingpreview",
    "msnbot",
    # Meta / Facebook
    "meta-externalagent",
    "meta-webindexer",
    "facebookexternalhit",
    "facebot",
    # Social platforms
    "twitterbot",
    "linkedinbot",
    "tiktokspider",
    "whatsapp",
    "telegrambot",
    # Apple / DuckDuckGo
    "applebot",
    "duckduckbot",
    # Yandex (cubre yandexbot, yandexmarket, etc.)
    "yandex",
    # Otros motores de búsqueda
    "baiduspider",
    "360spider",        # 360 Search (China)
    "slurp",            # Yahoo
    "ia_archiver",      # Internet Archive / Wayback Machine
    "amzn-searchbot",   # Amazon
    # AI search
    "perplexitybot",    # Perplexity
    "claudebot",        # Anthropic Claude
    "gptbot",           # OpenAI GPTBot
    "oai-searchbot",    # OpenAI SearchBot
    "chatgpt-user",     # ChatGPT browsing
    "anthropic-ai",     # Anthropic
    "cohere-ai",        # Cohere
    # SEO / herramientas legítimas
    "ahrefsbot",        # Ahrefs (2240 req en prod)
    "quillbot",         # QuillBot AI writing
)


def _is_good_crawler(request):
    """Return True if the request comes from a known legitimate crawler."""
    ua = request.META.get("HTTP_USER_AGENT", "").lower()
    return any(crawler in ua for crawler in _GOOD_CRAWLERS)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    remote = request.META.get("REMOTE_ADDR", "")
    return (xff.split(",")[-1].strip() if xff else remote) or "unknown"


def _ban_ip(ip, reason):
    """Write ban to Redis and log it."""
    cache.set(f"{_BAN_PREFIX}{ip}", reason, timeout=BAN_DURATION)
    logger.warning("bot_ban NEW ip=%s reason=%s duration_h=24", ip, reason)


def _record_signal(ip):
    """Add one bad-behavior signal; ban the IP if threshold is reached."""
    key = f"{_SIGNAL_PREFIX}{ip}"
    if not cache.add(key, 1, timeout=SIGNAL_WINDOW):
        try:
            count = cache.incr(key)
        except Exception:
            return  # Redis down — fail open
        if count >= SIGNAL_THRESHOLD:
            _ban_ip(ip, f"bad_behavior:{count}_signals_in_{SIGNAL_WINDOW}s")


class BotBanMiddleware:
    """Check bans, detect honeypot visits, and track bad-behavior signals."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ── 0. Legitimate crawlers are fully exempt. ─────────────────────────
        if _is_good_crawler(request):
            return self.get_response(request)

        ip = _client_ip(request)

        # ── 1. Already banned? Return 403 immediately. ──────────────────────
        if cache.get(f"{_BAN_PREFIX}{ip}"):
            return HttpResponseForbidden()

        # ── 2. Honeypot visit → ban instantly. ──────────────────────────────
        if request.path_info == HONEYPOT_PATH:
            _ban_ip(ip, "honeypot")
            return HttpResponseForbidden()

        response = self.get_response(request)

        # ── 3. Track bad-behavior signals from the response. ────────────────
        if response.status_code == 404:
            path = request.path_info or ""
            if not any(path.startswith(p) for p in _NOSIGNAL_PREFIXES):
                _record_signal(ip)

        return response
