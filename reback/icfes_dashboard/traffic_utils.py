import re
from urllib.parse import parse_qs, urlsplit


SCHOOL_PATH_RE = re.compile(r"^/icfes/colegio/([^/?#]+)/?")

AI_BOT_TOKENS = ("gptbot", "oai-searchbot", "chatgpt-user", "perplexitybot", "claudebot")
SEO_BOT_TOKENS = ("googlebot", "bingbot", "semrushbot", "ahrefsbot", "mj12bot", "yandexbot")
SOCIAL_BOT_TOKENS = ("meta-externalagent", "facebookexternalhit", "linkedinbot", "twitterbot", "slackbot")


def classify_bot(user_agent: str) -> str:
    if not user_agent:
        return "unknown"

    ua = user_agent.lower()
    if any(token in ua for token in AI_BOT_TOKENS):
        return "ai_bot"
    if any(token in ua for token in SEO_BOT_TOKENS):
        return "seo_bot"
    if any(token in ua for token in SOCIAL_BOT_TOKENS):
        return "social_bot"
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        return "other_bot"
    return "human_or_other"


def extract_path_fields(path: str):
    parsed = urlsplit(path or "")
    path_only = parsed.path or path or ""
    query = parse_qs(parsed.query)

    school_slug = ""
    match = SCHOOL_PATH_RE.match(path_only)
    if match:
        school_slug = match.group(1)

    return {
        "school_slug": school_slug,
        "utm_source": (query.get("utm_source", [""])[0] or "")[:128],
        "utm_medium": (query.get("utm_medium", [""])[0] or "")[:128],
        "utm_campaign": (query.get("utm_campaign", [""])[0] or "")[:128],
    }
