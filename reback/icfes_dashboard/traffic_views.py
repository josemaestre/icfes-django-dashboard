from collections import Counter, defaultdict
from datetime import timedelta
import hashlib

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Case, Count, IntegerField, Min, Q, Subquery, Sum, When
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.db.models.functions import TruncDate

from icfes_dashboard.models import RailwayTrafficLog
from reback.users.models import User

CONTROLLED_HTTP_STATUSES = {410}


def _percentile(values, p):
    if not values:
        return None
    sorted_values = sorted(values)
    idx = int(round((len(sorted_values) - 1) * p))
    return sorted_values[idx]


def _safe_pct(part, total):
    if not total:
        return 0.0
    return round((part * 100.0) / total, 2)


def _is_operational_error(status):
    code = status or 0
    return code >= 400 and code not in CONTROLLED_HTTP_STATUSES


def _path_group(path):
    path = (path or "").lower()
    if path == "/":
        return "home"
    if path.startswith("/icfes/colegio/"):
        return "colegio"
    if "/departamento/" in path and "/municipio/" in path:
        return "municipio"
    if "/departamento/" in path:
        return "departamento"
    if "/ranking/" in path:
        return "rankings"
    if path.startswith("/social-card/"):
        return "social-card"
    if path.startswith("/icfes/email-graphs/") or path.startswith("/email-graphs/"):
        return "email-graphs"
    if "sitemap" in path:
        return "sitemaps"
    if path.startswith("/robots.txt"):
        return "robots"
    if "/admin" in path:
        return "admin"
    if path.startswith("/icfes/trafico"):
        return "trafico/dashboard"
    if path.startswith("/static/") or path.startswith("/media/"):
        return "static/media"
    return "unknown"


def _bot_family(user_agent, bot_category):
    ua = (user_agent or "").lower()
    if "adsbot-google" in ua:
        return "AdsBot-Google"
    if "googlebot" in ua:
        return "Googlebot"
    if "bingbot" in ua:
        return "Bingbot"
    if "ahrefsbot" in ua:
        return "AhrefsBot"
    if "semrushbot" in ua:
        return "SemrushBot"
    if any(token in ua for token in ["gptbot", "chatgpt-user", "claudebot", "ccbot", "perplexitybot", "bytespider"]):
        return "AI bot"
    if "amazonbot" in ua:
        return "Amazonbot"
    if "twitterbot" in ua or "xbot" in ua:
        return "Twitter/X"
    if "facebookexternalhit" in ua:
        return "Facebook"
    if "linkedinbot" in ua:
        return "LinkedIn"
    if "meta-externalagent" in ua or "metabot" in ua:
        return "Meta"
    if bot_category == "human_or_other":
        return "Human"
    if "bot" in ua or bot_category in {"seo_bot", "ai_bot", "social_bot", "other_bot"}:
        return "Other bot"
    return "Human"


def _social_source(user_agent, utm_source, bot_family):
    ua = (user_agent or "").lower()
    src = (utm_source or "").lower()
    if bot_family in {"Twitter/X", "Facebook", "LinkedIn", "Meta"}:
        return bot_family
    if "instagram" in src:
        return "Instagram"
    if "facebook" in src or "fb" == src:
        return "Facebook"
    if "twitter" in src or src in {"x", "x.com"}:
        return "Twitter/X"
    if "linkedin" in src:
        return "LinkedIn"
    if "meta" in src:
        return "Meta"
    return None


def _clean_path(path):
    p = (path or "").strip()
    if not p:
        return ""
    return p.split("?", 1)[0].split("#", 1)[0]


def _is_indexable_path(path):
    p = _clean_path(path).lower()
    if not p:
        return False
    if p.endswith(".map"):
        return False
    blocked_prefixes = (
        "/static/",
        "/media/",
        "/admin",
        "/dashboard",
        "/api/",
        "/icfes/api/",
        "/icfes/trafico",
    )
    blocked_exact = {
        "/robots.txt",
        "/favicon.ico",
    }
    if p in blocked_exact:
        return False
    if any(p.startswith(prefix) for prefix in blocked_prefixes):
        return False
    if "sitemap" in p:
        return False
    return p.startswith("/icfes/")


def _url_depth(path):
    p = _clean_path(path)
    if p == "/":
        return 0
    segments = [seg for seg in p.strip("/").split("/") if seg]
    return len(segments)


def _is_suspicious_path(path):
    p = (path or "").lower()
    suspicious_tokens = [
        "{{",
        "}}",
        "%7b%7b",
        "%7d%7d",
        "/.well-known/",
        "/wp-admin",
        "/phpmyadmin",
        "/.env",
        "/xmlrpc.php",
    ]
    return any(token in p for token in suspicious_tokens)


def _is_public_api_path(path):
    p = _clean_path(path).lower()
    return p.startswith("/icfes/api/") or p.startswith("/api/")


def _funnel_stage(path):
    p = _clean_path(path).lower()
    if not p:
        return None
    if p.startswith("/icfes/api/search/colegios/") or p.startswith("/icfes/api/schools/search/"):
        return "Search"
    if p.startswith("/icfes/api/colegio/buscar/"):
        return "Search"
    if p.startswith("/icfes/colegio/"):
        return "School detail"
    if p.startswith("/icfes/api/colegio/") and "/resumen/" in p:
        return "School detail"
    deep_tokens = (
        "/historico/",
        "/comparacion",
        "/ingles/",
        "/ai-recommendations/",
        "/indicadores-",
        "/riesgo/",
        "/niveles-",
        "/fortalezas-debilidades/",
        "/similares/",
    )
    if p.startswith("/icfes/api/colegio/") and any(token in p for token in deep_tokens):
        return "Deep analysis"
    if p.startswith("/icfes/api/comparar-colegios/") or p.startswith("/icfes/api/story/"):
        return "Deep analysis"
    if p.startswith("/icfes/export/") or p.startswith("/accounts/") or p.startswith("/users/") or p.startswith("/payments/"):
        return "Conversion"
    if p == "/icfes/" or (p.startswith("/icfes/") and not p.startswith("/icfes/api/") and not p.startswith("/icfes/trafico")):
        return "Landing"
    return None


def _session_actor_id(src_ip, user_agent):
    raw = f"{src_ip or '-'}|{(user_agent or '').strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _first_seen_label(dt_value, today_start):
    if not dt_value:
        return "-"
    if dt_value >= today_start:
        return "today"
    return dt_value.strftime("%Y-%m-%d")


@login_required
def traffic_dashboard(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Forbidden")
    if not settings.TRAFFIC_ANALYTICS_ENABLED:
        raise Http404("Traffic analytics disabled")

    days = request.GET.get("days", "7")
    try:
        days_int = max(1, min(int(days), 90))
    except ValueError:
        days_int = 7
    explorer_ua = (request.GET.get("explorer_ua") or "").strip()
    explorer_path = (request.GET.get("explorer_path") or "").strip()
    show_explorer = request.GET.get("show_explorer") == "1" or bool(explorer_ua or explorer_path)

    now = timezone.now()
    since = now - timedelta(days=days_int)
    base_qs = RailwayTrafficLog.objects.filter(timestamp__gte=since)

    # User signups counters
    users_total = User.objects.count()
    users_non_admin_total = User.objects.filter(is_staff=False, is_superuser=False).count()
    users_new_period = User.objects.filter(date_joined__gte=since).count()
    users_non_admin_new_period = User.objects.filter(
        date_joined__gte=since,
        is_staff=False,
        is_superuser=False,
    ).count()

    total_requests = base_qs.count()
    status_2xx = base_qs.filter(http_status__gte=200, http_status__lt=300).count()
    status_3xx = base_qs.filter(http_status__gte=300, http_status__lt=400).count()
    status_4xx = base_qs.filter(http_status__gte=400, http_status__lt=500).count()
    status_4xx_controlled = base_qs.filter(http_status__in=CONTROLLED_HTTP_STATUSES).count()
    status_4xx_operational = max(status_4xx - status_4xx_controlled, 0)
    status_5xx = base_qs.filter(http_status__gte=500).count()

    requests_5m = RailwayTrafficLog.objects.filter(timestamp__gte=now - timedelta(minutes=5)).count()
    requests_1h = RailwayTrafficLog.objects.filter(timestamp__gte=now - timedelta(hours=1)).count()
    requests_24h = RailwayTrafficLog.objects.filter(timestamp__gte=now - timedelta(hours=24)).count()

    prev_1h = RailwayTrafficLog.objects.filter(
        timestamp__gte=now - timedelta(hours=2),
        timestamp__lt=now - timedelta(hours=1),
    ).count()
    prev_24h = RailwayTrafficLog.objects.filter(
        timestamp__gte=now - timedelta(hours=48),
        timestamp__lt=now - timedelta(hours=24),
    ).count()

    change_1h_pct = _safe_pct(requests_1h - prev_1h, prev_1h) if prev_1h else None
    change_24h_pct = _safe_pct(requests_24h - prev_24h, prev_24h) if prev_24h else None

    bot_counts = (
        base_qs.values("bot_category")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    human_count = base_qs.filter(bot_category="human_or_other").count()
    bot_count = total_requests - human_count

    duration_values = list(
        base_qs.exclude(total_duration_ms__isnull=True)
        .values_list("total_duration_ms", flat=True)[:80000]
    )
    p50_duration = _percentile(duration_values, 0.50)
    p95_duration = _percentile(duration_values, 0.95)
    p99_duration = _percentile(duration_values, 0.99)
    avg_duration = base_qs.aggregate(v=Avg("total_duration_ms"))["v"]

    status_counts = (
        base_qs.values("http_status")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    daily_status = (
        base_qs.annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(
            s2xx=Sum(
                Case(
                    When(http_status__gte=200, http_status__lt=300, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            s3xx=Sum(
                Case(
                    When(http_status__gte=300, http_status__lt=400, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            s4xx=Sum(
                Case(
                    When(http_status__gte=400, http_status__lt=500, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            s5xx=Sum(
                Case(
                    When(http_status__gte=500, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("day")
    )

    daily_traffic_split = (
        base_qs.annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(
            total=Count("id"),
            humans=Sum(
                Case(
                    When(bot_category="human_or_other", then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            bots=Sum(
                Case(
                    When(~Q(bot_category="human_or_other"), then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("day")
    )

    top_paths = (
        base_qs.values("path")
        .annotate(total=Count("id"))
        .order_by("-total")[:25]
    )
    top_school_slugs = (
        base_qs.exclude(school_slug="")
        .values("school_slug")
        .annotate(total=Count("id"))
        .order_by("-total")[:25]
    )

    top_slow_paths = (
        base_qs.exclude(total_duration_ms__isnull=True)
        .values("path")
        .annotate(hits=Count("id"), avg_ms=Avg("total_duration_ms"))
        .filter(hits__gte=5)
        .order_by("-avg_ms")[:25]
    )

    top_404 = (
        base_qs.filter(http_status=404)
        .values("path")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )
    top_500 = (
        base_qs.filter(http_status__gte=500)
        .values("path")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    top_utm_campaigns = (
        base_qs.exclude(utm_campaign="")
        .values("utm_source", "utm_medium", "utm_campaign")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    malformed_paths = (
        base_qs.filter(path__contains="http")
        .exclude(path__startswith="http")
        .values("path")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    detailed_rows = list(
        base_qs.values(
            "timestamp",
            "path",
            "http_status",
            "total_duration_ms",
            "tx_bytes",
            "client_ua",
            "bot_category",
            "utm_source",
            "src_ip",
            "upstream_errors",
        )[:60000]
    )

    minute_stats = defaultdict(lambda: {"requests": 0, "durations": [], "s4xx": 0, "s5xx": 0})
    group_stats = defaultdict(lambda: {"requests": 0, "durations": [], "errors": 0})
    bot_family_stats = defaultdict(lambda: {"requests": 0, "durations": [], "errors": 0, "paths": Counter()})
    bot_ua_stats = defaultdict(lambda: {"requests": 0, "durations": [], "errors": 0})
    social_daily = defaultdict(Counter)
    social_totals = Counter()
    daily_crawl_stats = defaultdict(
        lambda: {
            "bot_total": 0,
            "googlebot": 0,
            "paths_all": set(),
            "paths_indexable": set(),
            "depth_sum": 0,
            "depth_count": 0,
            "families": Counter(),
        }
    )
    period_crawl_stats = {
        "bot_total": 0,
        "googlebot": 0,
        "paths_all": set(),
        "paths_indexable": set(),
        "depth_sum": 0,
        "depth_count": 0,
    }
    suspicious_counter = Counter()
    upstream_error_counter = Counter()
    funnel_stage_order = ["Landing", "Search", "School detail", "Deep analysis", "Conversion"]
    funnel_stage_stats = {
        stage: {
            "sessions": set(),
            "requests": 0,
            "session_hits": Counter(),
        }
        for stage in funnel_stage_order
    }
    funnel_session_meta = {}
    api_public_endpoint_stats = defaultdict(
        lambda: {
            "requests": 0,
            "tx_total": 0,
            "tx_values": [],
            "ips": set(),
            "actors": Counter(),
        }
    )
    api_public_actor_stats = defaultdict(
        lambda: {
            "requests": 0,
            "tx_total": 0,
            "paths": Counter(),
        }
    )

    for row in detailed_rows:
        ts = row["timestamp"]
        minute_key = ts.replace(second=0, microsecond=0)
        path = row["path"] or ""
        clean_path = _clean_path(path)
        status = row["http_status"] or 0
        duration = row["total_duration_ms"]
        tx_bytes = max(row.get("tx_bytes") or 0, 0)

        m = minute_stats[minute_key]
        m["requests"] += 1
        if status >= 400 and status < 500:
            m["s4xx"] += 1
        if status >= 500:
            m["s5xx"] += 1
        if duration is not None:
            m["durations"].append(duration)

        group = _path_group(path)
        g = group_stats[group]
        g["requests"] += 1
        if _is_operational_error(status):
            g["errors"] += 1
        if duration is not None:
            g["durations"].append(duration)

        family = _bot_family(row["client_ua"], row["bot_category"])
        src_ip = row.get("src_ip") or "-"
        ua_literal = (row.get("client_ua") or "").strip() or "(empty ua)"
        session_id = _session_actor_id(src_ip, ua_literal)
        funnel_session_meta.setdefault(
            session_id,
            {"src_ip": src_ip, "agent_type": family, "client_ua": ua_literal},
        )

        stage = _funnel_stage(clean_path)
        if stage:
            stage_data = funnel_stage_stats[stage]
            stage_data["sessions"].add(session_id)
            stage_data["requests"] += 1
            stage_data["session_hits"][session_id] += 1

        b = bot_family_stats[family]
        b["requests"] += 1
        if _is_operational_error(status):
            b["errors"] += 1
        if duration is not None:
            b["durations"].append(duration)
        b["paths"][path] += 1

        if family != "Human":
            ua_literal = (row["client_ua"] or "").strip() or "(empty ua)"
            ua_stats = bot_ua_stats[ua_literal]
            ua_stats["requests"] += 1
            if _is_operational_error(status):
                ua_stats["errors"] += 1
            if duration is not None:
                ua_stats["durations"].append(duration)

            day_key = ts.date()
            day_stat = daily_crawl_stats[day_key]
            day_stat["bot_total"] += 1
            if family == "Googlebot":
                day_stat["googlebot"] += 1
            bucket_family = "Other bots"
            if family == "Googlebot":
                bucket_family = "Googlebot"
            elif family == "Bingbot":
                bucket_family = "Bingbot"
            elif family == "AhrefsBot":
                bucket_family = "AhrefsBot"
            elif family == "SemrushBot":
                bucket_family = "SemrushBot"
            elif family == "AI bot":
                bucket_family = "AI bots"
            elif family == "Amazonbot":
                bucket_family = "Amazonbot"
            elif family == "AdsBot-Google":
                bucket_family = "AdsBot-Google"
            elif family == "Facebook":
                bucket_family = "Facebook"
            elif family == "LinkedIn":
                bucket_family = "LinkedIn"
            elif family == "Meta":
                bucket_family = "Meta"
            day_stat["families"][bucket_family] += 1
            if clean_path:
                day_stat["paths_all"].add(clean_path)
            if _is_indexable_path(clean_path):
                day_stat["paths_indexable"].add(clean_path)
                day_stat["depth_sum"] += _url_depth(clean_path)
                day_stat["depth_count"] += 1

            period_crawl_stats["bot_total"] += 1
            if family == "Googlebot":
                period_crawl_stats["googlebot"] += 1
            if clean_path:
                period_crawl_stats["paths_all"].add(clean_path)
            if _is_indexable_path(clean_path):
                period_crawl_stats["paths_indexable"].add(clean_path)
                period_crawl_stats["depth_sum"] += _url_depth(clean_path)
                period_crawl_stats["depth_count"] += 1

        social_source = _social_source(row["client_ua"], row.get("utm_source"), family)
        if social_source:
            day_label = ts.date().isoformat()
            social_daily[day_label][social_source] += 1
            social_totals[social_source] += 1

        if _is_suspicious_path(path):
            suspicious_counter[path] += 1

        upstream_error = (row["upstream_errors"] or "").strip()
        if upstream_error:
            upstream_error_counter[upstream_error[:120]] += 1

        if _is_public_api_path(clean_path):
            actor_key = (src_ip, family, ua_literal)

            endpoint_data = api_public_endpoint_stats[clean_path]
            endpoint_data["requests"] += 1
            endpoint_data["tx_total"] += tx_bytes
            endpoint_data["tx_values"].append(tx_bytes)
            endpoint_data["ips"].add(src_ip)
            endpoint_data["actors"][actor_key] += tx_bytes

            actor_data = api_public_actor_stats[actor_key]
            actor_data["requests"] += 1
            actor_data["tx_total"] += tx_bytes
            actor_data["paths"][clean_path] += tx_bytes

    minute_series = []
    for minute_key, data in sorted(minute_stats.items(), key=lambda x: x[0], reverse=True)[:90]:
        minute_series.append(
            {
                "minute": minute_key,
                "requests": data["requests"],
                "p95_ms": _percentile(data["durations"], 0.95),
                "status_4xx": data["s4xx"],
                "status_5xx": data["s5xx"],
            }
        )

    perf_by_group = []
    for group, data in sorted(group_stats.items(), key=lambda x: x[1]["requests"], reverse=True):
        perf_by_group.append(
            {
                "path_group": group,
                "total": data["requests"],
                "avg_ms": round(sum(data["durations"]) / len(data["durations"]), 1) if data["durations"] else None,
                "p95_ms": _percentile(data["durations"], 0.95),
                "error_rate": _safe_pct(data["errors"], data["requests"]),
            }
        )

    bot_families = []
    for family, data in sorted(bot_family_stats.items(), key=lambda x: x[1]["requests"], reverse=True):
        top_path = data["paths"].most_common(1)[0][0] if data["paths"] else ""
        bot_families.append(
            {
                "bot_family": family,
                "total": data["requests"],
                "p95_ms": _percentile(data["durations"], 0.95),
                "error_rate": _safe_pct(data["errors"], data["requests"]),
                "top_path": top_path,
            }
        )

    all_bot_user_agents = []
    for ua_literal, data in sorted(bot_ua_stats.items(), key=lambda x: x[1]["requests"], reverse=True):
        all_bot_user_agents.append(
            {
                "client_ua": ua_literal,
                "total": data["requests"],
                "p95_ms": _percentile(data["durations"], 0.95),
                "error_rate": _safe_pct(data["errors"], data["requests"]),
            }
        )

    suspicious_paths = [{"path": p, "total": c} for p, c in suspicious_counter.most_common(20)]
    upstream_error_rows = [{"upstream_error": e, "total": c} for e, c in upstream_error_counter.most_common(15)]
    api_public_bytes_by_endpoint = []
    for endpoint, data in sorted(
        api_public_endpoint_stats.items(),
        key=lambda x: (x[1]["tx_total"], x[1]["requests"]),
        reverse=True,
    )[:25]:
        top_actor = data["actors"].most_common(1)[0] if data["actors"] else None
        top_actor_key = top_actor[0] if top_actor else ("-", "-", "-")
        api_public_bytes_by_endpoint.append(
            {
                "path": endpoint,
                "requests": data["requests"],
                "tx_total": data["tx_total"],
                "avg_tx": round(data["tx_total"] / data["requests"], 1) if data["requests"] else 0,
                "p95_tx": _percentile(data["tx_values"], 0.95),
                "unique_ips": len(data["ips"]),
                "top_src_ip": top_actor_key[0],
                "top_agent_type": top_actor_key[1],
                "top_ua": top_actor_key[2],
            }
        )

    api_public_bytes_by_actor = []
    for actor_key, data in sorted(
        api_public_actor_stats.items(),
        key=lambda x: (x[1]["tx_total"], x[1]["requests"]),
        reverse=True,
    )[:25]:
        src_ip, agent_type, ua_literal = actor_key
        top_path = data["paths"].most_common(1)[0][0] if data["paths"] else "-"
        api_public_bytes_by_actor.append(
            {
                "src_ip": src_ip,
                "agent_type": agent_type,
                "client_ua": ua_literal,
                "requests": data["requests"],
                "tx_total": data["tx_total"],
                "avg_tx": round(data["tx_total"] / data["requests"], 1) if data["requests"] else 0,
                "top_path": top_path,
            }
        )

    interaction_funnel_rows = []
    for idx, stage in enumerate(funnel_stage_order):
        stage_data = funnel_stage_stats[stage]
        current_sessions = stage_data["sessions"]
        current_count = len(current_sessions)
        progressed = None
        progression_rate = None
        next_stage = "-"
        if idx < len(funnel_stage_order) - 1:
            next_stage = funnel_stage_order[idx + 1]
            next_sessions = funnel_stage_stats[next_stage]["sessions"]
            progressed = len(current_sessions & next_sessions)
            progression_rate = _safe_pct(progressed, current_count) if current_count else 0
        interaction_funnel_rows.append(
            {
                "stage": stage,
                "unique_users": current_count,
                "requests": stage_data["requests"],
                "next_stage": next_stage,
                "progressed": progressed,
                "progression_rate": progression_rate,
            }
        )

    interaction_funnel_top_actors = []
    for stage in funnel_stage_order:
        for session_id, hits in funnel_stage_stats[stage]["session_hits"].most_common(5):
            meta = funnel_session_meta.get(session_id, {})
            interaction_funnel_top_actors.append(
                {
                    "stage": stage,
                    "session_id": session_id,
                    "requests": hits,
                    "src_ip": meta.get("src_ip", "-"),
                    "agent_type": meta.get("agent_type", "-"),
                    "client_ua": meta.get("client_ua", "-"),
                }
            )

    one_hour_ago = now - timedelta(hours=1)
    top_ips_1h = (
        RailwayTrafficLog.objects.filter(timestamp__gte=one_hour_ago)
        .exclude(src_ip__isnull=True)
        .values("src_ip")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    yesterday_paths = RailwayTrafficLog.objects.filter(
        timestamp__gte=yesterday_start,
        timestamp__lt=today_start,
    ).values("path")
    yesterday_uas = RailwayTrafficLog.objects.filter(
        timestamp__gte=yesterday_start,
        timestamp__lt=today_start,
    ).values("client_ua")

    new_paths_today = (
        RailwayTrafficLog.objects.filter(timestamp__gte=today_start, timestamp__lt=now)
        .exclude(path__in=Subquery(yesterday_paths))
        .values("path")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    new_uas_today = (
        RailwayTrafficLog.objects.filter(timestamp__gte=today_start, timestamp__lt=now)
        .exclude(client_ua__in=Subquery(yesterday_uas))
        .exclude(client_ua="")
        .values("client_ua")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    request_explorer_total = 0
    request_explorer_rows = []
    if show_explorer:
        request_explorer_qs = base_qs
        if explorer_ua:
            request_explorer_qs = request_explorer_qs.filter(client_ua=explorer_ua)
        if explorer_path:
            request_explorer_qs = request_explorer_qs.filter(path=explorer_path)
        request_explorer_total = request_explorer_qs.count()
        request_explorer_rows = list(
            request_explorer_qs.values(
                "request_id",
                "timestamp",
                "method",
                "path",
                "http_status",
                "total_duration_ms",
                "src_ip",
                "client_ua",
            ).order_by("-timestamp")[:300]
        )

    discovered_paths_today_qs = (
        RailwayTrafficLog.objects.values("path")
        .annotate(
            first_seen=Min("timestamp"),
            hits_today=Sum(
                Case(
                    When(timestamp__gte=today_start, timestamp__lt=now, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            human_hits_today=Sum(
                Case(
                    When(
                        timestamp__gte=today_start,
                        timestamp__lt=now,
                        bot_category="human_or_other",
                        then=1,
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            bot_hits_today=Sum(
                Case(
                    When(
                        condition=Q(timestamp__gte=today_start)
                        & Q(timestamp__lt=now)
                        & ~Q(bot_category="human_or_other"),
                        then=1,
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .filter(first_seen__gte=today_start, hits_today__gt=0)
        .order_by("-hits_today")[:40]
    )

    discovered_paths_today = list(discovered_paths_today_qs)
    discovered_path_keys = [row["path"] for row in discovered_paths_today]
    source_by_path = {}
    if discovered_path_keys:
        source_rows = RailwayTrafficLog.objects.filter(
            timestamp__gte=today_start,
            timestamp__lt=now,
            path__in=discovered_path_keys,
        ).values("path", "client_ua", "bot_category")
        tmp = defaultdict(Counter)
        for row in source_rows:
            source = _bot_family(row["client_ua"], row["bot_category"])
            tmp[row["path"]][source] += 1
        for path_key, counts in tmp.items():
            source_by_path[path_key] = counts.most_common(1)[0][0] if counts else "-"

    discovered_paths_enriched = []
    for row in discovered_paths_today[:20]:
        human_hits = row.get("human_hits_today") or 0
        bot_hits = row.get("bot_hits_today") or 0
        discovered_paths_enriched.append(
            {
                "path": row["path"],
                "total": row.get("hits_today") or 0,
                "first_seen_label": _first_seen_label(row.get("first_seen"), today_start),
                "type_label": "Human" if human_hits >= bot_hits else "Bot",
                "source_label": source_by_path.get(row["path"], "Human" if human_hits >= bot_hits else "Other bot"),
            }
        )

    discovered_colleges_today = (
        RailwayTrafficLog.objects.exclude(school_slug="")
        .values("school_slug")
        .annotate(
            first_seen=Min("timestamp"),
            hits_today=Sum(
                Case(
                    When(timestamp__gte=today_start, timestamp__lt=now, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .filter(first_seen__gte=today_start, hits_today__gt=0)
        .order_by("-hits_today")[:20]
    )

    crawled_colleges_today_qs = (
        RailwayTrafficLog.objects.filter(
            timestamp__gte=today_start,
            timestamp__lt=now,
        )
        .exclude(school_slug="")
        .exclude(bot_category="human_or_other")
        .values("school_slug")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )
    crawled_colleges_today = list(crawled_colleges_today_qs)
    crawled_slug_keys = [row["school_slug"] for row in crawled_colleges_today]
    crawler_source_by_slug = {}
    if crawled_slug_keys:
        crawl_rows = RailwayTrafficLog.objects.filter(
            timestamp__gte=today_start,
            timestamp__lt=now,
            school_slug__in=crawled_slug_keys,
        ).exclude(bot_category="human_or_other").values("school_slug", "client_ua", "bot_category")
        tmp = defaultdict(Counter)
        for row in crawl_rows:
            source = _bot_family(row["client_ua"], row["bot_category"])
            tmp[row["school_slug"]][source] += 1
        for slug_key, counts in tmp.items():
            crawler_source_by_slug[slug_key] = counts.most_common(1)[0][0] if counts else "Other bot"

    crawled_colleges_enriched = []
    for row in crawled_colleges_today:
        crawled_colleges_enriched.append(
            {
                "school_slug": row["school_slug"],
                "total": row["total"],
                "bot_type": crawler_source_by_slug.get(row["school_slug"], "Other bot"),
            }
        )

    alerts_red = []
    alerts_yellow = []

    error_5xx_rate = _safe_pct(status_5xx, total_requests)
    error_4xx_rate = _safe_pct(status_4xx_operational, total_requests)

    if error_5xx_rate > 1:
        alerts_red.append(f"5xx alto: {error_5xx_rate}%")
    if p95_duration and p95_duration > 1500:
        alerts_red.append(f"p95 alto: {p95_duration} ms")

    top_404_count = top_404[0]["total"] if top_404 else 0
    if top_404_count >= 50:
        alerts_yellow.append(f"404 elevado en top path: {top_404_count} hits")
    if requests_1h and prev_1h and requests_1h > prev_1h * 2:
        alerts_yellow.append("spike de trafico >2x vs hora anterior")

    daily_status_labels = [row["day"].strftime("%Y-%m-%d") for row in daily_status]
    daily_status_2xx = [row["s2xx"] or 0 for row in daily_status]
    daily_status_3xx = [row["s3xx"] or 0 for row in daily_status]
    daily_status_4xx = [row["s4xx"] or 0 for row in daily_status]
    daily_status_5xx = [row["s5xx"] or 0 for row in daily_status]

    daily_split_labels = [row["day"].strftime("%Y-%m-%d") for row in daily_traffic_split]
    daily_split_total = [row["total"] or 0 for row in daily_traffic_split]
    daily_split_humans = [row["humans"] or 0 for row in daily_traffic_split]
    daily_split_bots = [row["bots"] or 0 for row in daily_traffic_split]

    crawl_labels = []
    crawl_ratio_google = []
    crawl_efficiency = []
    crawl_depth_avg = []
    bot_dist_google = []
    bot_dist_bing = []
    bot_dist_ahrefs = []
    bot_dist_semrush = []
    bot_dist_ai = []
    bot_dist_amazon = []
    bot_dist_adsbot = []
    bot_dist_facebook = []
    bot_dist_linkedin = []
    bot_dist_meta = []
    bot_dist_other = []
    discovery_new_urls = []
    discovery_velocity = []
    seen_indexable_paths = set()
    prev_new = None

    for day_key in sorted(daily_crawl_stats.keys()):
        data = daily_crawl_stats[day_key]
        crawl_labels.append(day_key.strftime("%Y-%m-%d"))
        crawl_ratio_google.append(_safe_pct(data["googlebot"], data["bot_total"]))
        crawl_efficiency.append(_safe_pct(len(data["paths_indexable"]), len(data["paths_all"])))
        depth_avg = (
            round(data["depth_sum"] / data["depth_count"], 2)
            if data["depth_count"]
            else None
        )
        crawl_depth_avg.append(depth_avg)

        families = data["families"]
        bot_dist_google.append(families.get("Googlebot", 0))
        bot_dist_bing.append(families.get("Bingbot", 0))
        bot_dist_ahrefs.append(families.get("AhrefsBot", 0))
        bot_dist_semrush.append(families.get("SemrushBot", 0))
        bot_dist_ai.append(families.get("AI bots", 0))
        bot_dist_amazon.append(families.get("Amazonbot", 0))
        bot_dist_adsbot.append(families.get("AdsBot-Google", 0))
        bot_dist_facebook.append(families.get("Facebook", 0))
        bot_dist_linkedin.append(families.get("LinkedIn", 0))
        bot_dist_meta.append(families.get("Meta", 0))
        other_count = max(
            data["bot_total"]
            - (
                families.get("Googlebot", 0)
                + families.get("Bingbot", 0)
                + families.get("AhrefsBot", 0)
                + families.get("SemrushBot", 0)
                + families.get("AI bots", 0)
                + families.get("Amazonbot", 0)
                + families.get("AdsBot-Google", 0)
                + families.get("Facebook", 0)
                + families.get("LinkedIn", 0)
                + families.get("Meta", 0)
            ),
            0,
        )
        bot_dist_other.append(other_count)

        new_today = len(data["paths_indexable"] - seen_indexable_paths)
        seen_indexable_paths.update(data["paths_indexable"])
        discovery_new_urls.append(new_today)
        if prev_new is None:
            discovery_velocity.append(0)
        else:
            discovery_velocity.append(new_today - prev_new)
        prev_new = new_today

    crawl_ratio_period = _safe_pct(period_crawl_stats["googlebot"], period_crawl_stats["bot_total"])
    crawl_efficiency_period = _safe_pct(
        len(period_crawl_stats["paths_indexable"]),
        len(period_crawl_stats["paths_all"]),
    )
    indexable_depth_period = (
        round(period_crawl_stats["depth_sum"] / period_crawl_stats["depth_count"], 2)
        if period_crawl_stats["depth_count"]
        else None
    )
    if indexable_depth_period is None:
        depth_status = "Sin datos"
    elif indexable_depth_period <= 3:
        depth_status = "Ideal"
    elif indexable_depth_period <= 5:
        depth_status = "Aceptable"
    else:
        depth_status = "Riesgo (profundidad alta)"

    social_labels = daily_split_labels
    social_twitter = [social_daily[label].get("Twitter/X", 0) for label in social_labels]
    social_facebook = [social_daily[label].get("Facebook", 0) for label in social_labels]
    social_linkedin = [social_daily[label].get("LinkedIn", 0) for label in social_labels]
    social_meta = [social_daily[label].get("Meta", 0) for label in social_labels]
    social_instagram = [social_daily[label].get("Instagram", 0) for label in social_labels]

    context = {
        "days": days_int,
        "since": since,
        "total_requests": total_requests,
        "requests_5m": requests_5m,
        "requests_1h": requests_1h,
        "requests_24h": requests_24h,
        "change_1h_pct": change_1h_pct,
        "change_24h_pct": change_24h_pct,
        "human_count": human_count,
        "bot_count": bot_count,
        "bot_ratio": _safe_pct(bot_count, total_requests),
        "status_2xx": status_2xx,
        "status_3xx": status_3xx,
        "status_4xx": status_4xx,
        "status_4xx_controlled": status_4xx_controlled,
        "status_4xx_operational": status_4xx_operational,
        "status_5xx": status_5xx,
        "error_4xx_rate": error_4xx_rate,
        "error_5xx_rate": error_5xx_rate,
        "avg_duration": round(avg_duration, 1) if avg_duration is not None else None,
        "p50_duration": p50_duration,
        "p95_duration": p95_duration,
        "p99_duration": p99_duration,
        "status_counts": status_counts,
        "bot_counts": bot_counts,
        "all_bot_user_agents": all_bot_user_agents,
        "top_paths": top_paths,
        "top_slow_paths": top_slow_paths,
        "top_school_slugs": top_school_slugs,
        "top_404": top_404,
        "top_500": top_500,
        "top_utm_campaigns": top_utm_campaigns,
        "malformed_paths": malformed_paths,
        "minute_series": minute_series,
        "perf_by_group": perf_by_group,
        "bot_families": bot_families,
        "suspicious_paths": suspicious_paths,
        "upstream_error_rows": upstream_error_rows,
        "api_public_bytes_by_endpoint": api_public_bytes_by_endpoint,
        "api_public_bytes_by_actor": api_public_bytes_by_actor,
        "interaction_funnel_rows": interaction_funnel_rows,
        "interaction_funnel_top_actors": interaction_funnel_top_actors,
        "top_ips_1h": top_ips_1h,
        "new_paths_today": new_paths_today,
        "discovered_paths_today": discovered_paths_enriched,
        "discovered_colleges_today": discovered_colleges_today,
        "crawled_colleges_today": crawled_colleges_enriched,
        "new_uas_today": new_uas_today,
        "alerts_red": alerts_red,
        "alerts_yellow": alerts_yellow,
        "daily_status_labels": daily_status_labels,
        "daily_status_2xx": daily_status_2xx,
        "daily_status_3xx": daily_status_3xx,
        "daily_status_4xx": daily_status_4xx,
        "daily_status_5xx": daily_status_5xx,
        "daily_split_labels": daily_split_labels,
        "daily_split_total": daily_split_total,
        "daily_split_humans": daily_split_humans,
        "daily_split_bots": daily_split_bots,
        "crawl_ratio_period": crawl_ratio_period,
        "crawl_efficiency_period": crawl_efficiency_period,
        "indexable_depth_period": indexable_depth_period,
        "depth_status": depth_status,
        "discovery_new_today": discovery_new_urls[-1] if discovery_new_urls else 0,
        "discovery_velocity_today": discovery_velocity[-1] if discovery_velocity else 0,
        "crawl_labels": crawl_labels,
        "crawl_ratio_google": crawl_ratio_google,
        "crawl_efficiency": crawl_efficiency,
        "crawl_depth_avg": crawl_depth_avg,
        "bot_dist_google": bot_dist_google,
        "bot_dist_bing": bot_dist_bing,
        "bot_dist_ahrefs": bot_dist_ahrefs,
        "bot_dist_semrush": bot_dist_semrush,
        "bot_dist_ai": bot_dist_ai,
        "bot_dist_amazon": bot_dist_amazon,
        "bot_dist_adsbot": bot_dist_adsbot,
        "bot_dist_facebook": bot_dist_facebook,
        "bot_dist_linkedin": bot_dist_linkedin,
        "bot_dist_meta": bot_dist_meta,
        "bot_dist_other": bot_dist_other,
        "discovery_new_urls": discovery_new_urls,
        "discovery_velocity": discovery_velocity,
        "users_total": users_total,
        "users_non_admin_total": users_non_admin_total,
        "users_new_period": users_new_period,
        "users_non_admin_new_period": users_non_admin_new_period,
        "request_explorer_ua": explorer_ua,
        "request_explorer_path": explorer_path,
        "show_request_explorer": show_explorer,
        "request_explorer_total": request_explorer_total,
        "request_explorer_rows": request_explorer_rows,
        "social_total_twitter": social_totals.get("Twitter/X", 0),
        "social_total_facebook": social_totals.get("Facebook", 0),
        "social_total_linkedin": social_totals.get("LinkedIn", 0),
        "social_total_meta": social_totals.get("Meta", 0),
        "social_total_instagram": social_totals.get("Instagram", 0),
        "social_labels": social_labels,
        "social_twitter": social_twitter,
        "social_facebook": social_facebook,
        "social_linkedin": social_linkedin,
        "social_meta": social_meta,
        "social_instagram": social_instagram,
        "human_queries_labels": daily_split_labels,
        "human_queries_values": daily_split_humans,
    }
    return render(request, "icfes_dashboard/pages/dashboard-traffic.html", context)

