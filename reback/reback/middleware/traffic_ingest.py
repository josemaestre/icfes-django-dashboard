"""
Realtime traffic ingest middleware.
Stores request/response metadata into Postgres for traffic analytics.
"""
import logging
import time
import uuid

from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.utils import timezone

from icfes_dashboard.models import RailwayTrafficLog
from icfes_dashboard.traffic_utils import classify_bot, extract_path_fields


logger = logging.getLogger(__name__)


class TrafficIngestMiddleware:
    captured_count = 0

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)

        if not getattr(settings, "TRAFFIC_ANALYTICS_ENABLED", False):
            return response

        try:
            full_path = request.get_full_path() or request.path or ""
            ua = (request.META.get("HTTP_USER_AGENT", "") or "")[:1000]
            fields = extract_path_fields(full_path)

            # Prefer upstream request id if available; fallback to generated UUID.
            request_id = (
                request.META.get("HTTP_X_REQUEST_ID")
                or request.META.get("HTTP_X_RAILWAY_REQUEST_ID")
                or str(uuid.uuid4())
            )

            xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
            src_ip = (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")) or None

            payload = dict(
                request_id=str(request_id)[:64],
                timestamp=timezone.now(),
                method=(request.method or "")[:12],
                path=full_path,
                host=(request.get_host() or "")[:255],
                http_status=int(response.status_code),
                total_duration_ms=int((time.perf_counter() - start) * 1000),
                upstream_rq_duration_ms=None,
                tx_bytes=None,
                rx_bytes=None,
                client_ua=ua,
                src_ip=src_ip,
                edge_region=(request.META.get("HTTP_X_EDGE_REGION", "") or "")[:64],
                upstream_errors="",
                bot_category=classify_bot(ua),
                school_slug=fields["school_slug"],
                utm_source=fields["utm_source"],
                utm_medium=fields["utm_medium"],
                utm_campaign=fields["utm_campaign"],
            )
            try:
                RailwayTrafficLog.objects.create(**payload)
            except IntegrityError:
                # Retry with a generated id if upstream request id collides.
                payload["request_id"] = str(uuid.uuid4())
                RailwayTrafficLog.objects.create(**payload)

            TrafficIngestMiddleware.captured_count += 1
            if getattr(settings, "TRAFFIC_ANALYTICS_DEBUG_LOGS", False):
                logger.info(
                    "traffic_ingest captured_count=%s status=%s path=%s bot=%s",
                    TrafficIngestMiddleware.captured_count,
                    payload["http_status"],
                    payload["path"],
                    payload["bot_category"],
                )
        except DatabaseError:
            logger.exception("Traffic ingest DB error path=%s", request.get_full_path())
        except Exception:
            logger.exception("Traffic ingest unexpected error path=%s", request.get_full_path())

        return response
