from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from icfes_dashboard.models import RailwayTrafficLog


def _percentile_95(values):
    if not values:
        return None
    sorted_values = sorted(values)
    idx = int(round((len(sorted_values) - 1) * 0.95))
    return sorted_values[idx]


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

    since = timezone.now() - timedelta(days=days_int)
    base_qs = RailwayTrafficLog.objects.filter(timestamp__gte=since)

    total_requests = base_qs.count()
    status_2xx = base_qs.filter(http_status__gte=200, http_status__lt=300).count()
    status_3xx = base_qs.filter(http_status__gte=300, http_status__lt=400).count()
    status_4xx = base_qs.filter(http_status__gte=400, http_status__lt=500).count()
    status_5xx = base_qs.filter(http_status__gte=500).count()

    bot_counts = (
        base_qs.values("bot_category")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    human_count = base_qs.filter(bot_category="human_or_other").count()

    duration_values = list(
        base_qs.exclude(total_duration_ms__isnull=True)
        .values_list("total_duration_ms", flat=True)[:50000]
    )
    p95_duration = _percentile_95(duration_values)
    avg_duration = base_qs.aggregate(v=Avg("total_duration_ms"))["v"]

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
    top_404 = (
        base_qs.filter(http_status=404)
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
    top_ai_bots = (
        base_qs.filter(bot_category="ai_bot")
        .values("client_ua")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )
    top_seo_bots = (
        base_qs.filter(bot_category="seo_bot")
        .values("client_ua")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )
    malformed_paths = (
        base_qs.filter(path__contains="http")
        .exclude(path__startswith="http")
        .values("path")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )
    unresolved_placeholders = (
        base_qs.filter(Q(path__contains="{{") | Q(path__contains="%7B%7B"))
        .values("path")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    context = {
        "days": days_int,
        "since": since,
        "total_requests": total_requests,
        "human_count": human_count,
        "status_2xx": status_2xx,
        "status_3xx": status_3xx,
        "status_4xx": status_4xx,
        "status_5xx": status_5xx,
        "avg_duration": round(avg_duration, 1) if avg_duration is not None else None,
        "p95_duration": p95_duration,
        "bot_counts": bot_counts,
        "top_paths": top_paths,
        "top_school_slugs": top_school_slugs,
        "top_404": top_404,
        "top_utm_campaigns": top_utm_campaigns,
        "top_ai_bots": top_ai_bots,
        "top_seo_bots": top_seo_bots,
        "malformed_paths": malformed_paths,
        "unresolved_placeholders": unresolved_placeholders,
    }
    return render(request, "icfes_dashboard/pages/dashboard-traffic.html", context)
