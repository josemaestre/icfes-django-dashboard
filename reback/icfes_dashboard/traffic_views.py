from collections import Counter, defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Case, Count, IntegerField, Q, Subquery, Sum, When
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.db.models.functions import TruncDate

from icfes_dashboard.models import RailwayTrafficLog


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
    if "amazonbot" in ua:
        return "Amazonbot"
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

    now = timezone.now()
    since = now - timedelta(days=days_int)
    base_qs = RailwayTrafficLog.objects.filter(timestamp__gte=since)

    total_requests = base_qs.count()
    status_2xx = base_qs.filter(http_status__gte=200, http_status__lt=300).count()
    status_3xx = base_qs.filter(http_status__gte=300, http_status__lt=400).count()
    status_4xx = base_qs.filter(http_status__gte=400, http_status__lt=500).count()
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
            "client_ua",
            "bot_category",
            "src_ip",
            "upstream_errors",
        )[:60000]
    )

    minute_stats = defaultdict(lambda: {"requests": 0, "durations": [], "s4xx": 0, "s5xx": 0})
    group_stats = defaultdict(lambda: {"requests": 0, "durations": [], "errors": 0})
    bot_family_stats = defaultdict(lambda: {"requests": 0, "durations": [], "errors": 0, "paths": Counter()})
    bot_ua_stats = defaultdict(lambda: {"requests": 0, "durations": [], "errors": 0})
    suspicious_counter = Counter()
    upstream_error_counter = Counter()

    for row in detailed_rows:
        ts = row["timestamp"]
        minute_key = ts.replace(second=0, microsecond=0)
        path = row["path"] or ""
        status = row["http_status"] or 0
        duration = row["total_duration_ms"]

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
        if status >= 400:
            g["errors"] += 1
        if duration is not None:
            g["durations"].append(duration)

        family = _bot_family(row["client_ua"], row["bot_category"])
        b = bot_family_stats[family]
        b["requests"] += 1
        if status >= 400:
            b["errors"] += 1
        if duration is not None:
            b["durations"].append(duration)
        b["paths"][path] += 1

        if family != "Human":
            ua_literal = (row["client_ua"] or "").strip() or "(empty ua)"
            ua_stats = bot_ua_stats[ua_literal]
            ua_stats["requests"] += 1
            if status >= 400:
                ua_stats["errors"] += 1
            if duration is not None:
                ua_stats["durations"].append(duration)

        if _is_suspicious_path(path):
            suspicious_counter[path] += 1

        upstream_error = (row["upstream_errors"] or "").strip()
        if upstream_error:
            upstream_error_counter[upstream_error[:120]] += 1

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

    alerts_red = []
    alerts_yellow = []

    error_5xx_rate = _safe_pct(status_5xx, total_requests)
    error_4xx_rate = _safe_pct(status_4xx, total_requests)

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
        "top_ips_1h": top_ips_1h,
        "new_paths_today": new_paths_today,
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
    }
    return render(request, "icfes_dashboard/pages/dashboard-traffic.html", context)

