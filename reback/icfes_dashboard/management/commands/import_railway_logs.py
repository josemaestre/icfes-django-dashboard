import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from icfes_dashboard.models import RailwayTrafficLog
from icfes_dashboard.traffic_utils import classify_bot, extract_path_fields


class Command(BaseCommand):
    help = "Import Railway HTTP logs from JSONL into Postgres (RailwayTrafficLog)."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="Path to JSONL exported from Railway.")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Bulk insert batch size (default: 1000).",
        )
        parser.add_argument(
            "--allow-disabled",
            action="store_true",
            help="Allow import even when TRAFFIC_ANALYTICS_ENABLED=False.",
        )

    def handle(self, *args, **options):
        if not settings.TRAFFIC_ANALYTICS_ENABLED and not options["allow_disabled"]:
            raise CommandError(
                "TRAFFIC_ANALYTICS_ENABLED is False. Set it to True or use --allow-disabled."
            )

        input_path = Path(options["input"]).expanduser().resolve()
        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        batch_size = options["batch_size"]
        created = 0
        read = 0
        skipped = 0
        to_insert = []

        with input_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                read += 1

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue

                request_id = str(record.get("requestId", "")).strip()
                timestamp = parse_datetime(str(record.get("timestamp", "")))
                path = str(record.get("path", "")).strip()
                http_status = record.get("httpStatus")

                if not request_id or not timestamp or http_status is None:
                    skipped += 1
                    continue

                fields = extract_path_fields(path)

                user_agent = str(record.get("clientUa", "")).strip()

                to_insert.append(
                    RailwayTrafficLog(
                        request_id=request_id,
                        timestamp=timestamp,
                        method=str(record.get("method", "")).strip(),
                        path=path,
                        host=str(record.get("host", "")).strip(),
                        http_status=int(http_status),
                        total_duration_ms=record.get("totalDuration"),
                        upstream_rq_duration_ms=record.get("upstreamRqDuration"),
                        tx_bytes=record.get("txBytes"),
                        rx_bytes=record.get("rxBytes"),
                        client_ua=user_agent,
                        src_ip=record.get("srcIp") or None,
                        edge_region=str(record.get("edgeRegion", "")).strip(),
                        upstream_errors=str(record.get("upstreamErrors", "")).strip(),
                        bot_category=classify_bot(user_agent),
                        school_slug=fields["school_slug"],
                        utm_source=fields["utm_source"],
                        utm_medium=fields["utm_medium"],
                        utm_campaign=fields["utm_campaign"],
                    )
                )

                if len(to_insert) >= batch_size:
                    created += self._flush(to_insert, batch_size)
                    to_insert = []

        if to_insert:
            created += self._flush(to_insert, batch_size)

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete | read={read} inserted={created} skipped={skipped}"
            )
        )

    @staticmethod
    def _flush(batch, batch_size):
        before = len(batch)
        RailwayTrafficLog.objects.bulk_create(
            batch,
            batch_size=batch_size,
            ignore_conflicts=True,
        )
        return before
