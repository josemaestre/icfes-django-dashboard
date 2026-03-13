"""
Management command: ping_indexnow

Notifica a Bing (y a través de IndexNow, a Google/Yandex) sobre
todas las landing pages nuevas: cuadrante, potencial, bilingues, etc.

Uso:
    python manage.py ping_indexnow              # dry-run, imprime URLs
    python manage.py ping_indexnow --send       # envía realmente a IndexNow
    python manage.py ping_indexnow --send --batch cuadrante potencial
"""
from __future__ import annotations

import json
import time
import urllib.request
from urllib.error import URLError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from icfes_dashboard.db_utils import get_duckdb_connection, resolve_schema

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH_LIMIT = 10_000   # IndexNow max per request
SITE = "https://www.icfes-analytics.com"

# ─── Cuadrantes ───────────────────────────────────────────────────────────────
_CUADRANTES = ["estrella", "consolidada", "emergente", "alerta"]

# ─── Potencial sectors ────────────────────────────────────────────────────────
_POTENCIAL_SECTORS = ["oficial", "privado"]


class Command(BaseCommand):
    help = "Ping IndexNow with new landing page URLs (cuadrante, potencial, etc.)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--send",
            action="store_true",
            default=False,
            help="Actually send to IndexNow (default: dry-run only)",
        )
        parser.add_argument(
            "--batch",
            nargs="*",
            choices=["cuadrante", "potencial", "bilingues", "colegios-mejoraron"],
            default=["cuadrante", "potencial"],
            help="Which URL groups to include (default: cuadrante potencial)",
        )

    def handle(self, *args, **options):
        key = getattr(settings, "INDEXNOW_KEY", "").strip()
        if not key:
            raise CommandError("INDEXNOW_KEY no configurado en settings/env")

        send = options["send"]
        batches = options["batch"] or ["cuadrante", "potencial"]

        self.stdout.write(f"Site   : {SITE}")
        self.stdout.write(f"Key    : {key[:6]}...")
        self.stdout.write(f"Batches: {batches}")
        self.stdout.write(f"Mode   : {'SEND' if send else 'DRY-RUN'}\n")

        # Build URL list
        urls = []
        with get_duckdb_connection() as conn:
            deptos = self._get_deptos(conn)

        if "cuadrante" in batches:
            urls.extend(self._cuadrante_urls(deptos))
        if "potencial" in batches:
            urls.extend(self._potencial_urls(deptos))
        if "bilingues" in batches:
            urls.extend(self._bilingues_urls(deptos))
        if "colegios-mejoraron" in batches:
            urls.extend(self._mejoraron_urls())

        # Deduplicate preserving order
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        self.stdout.write(f"Total URLs: {len(unique_urls)}")

        if not send:
            self.stdout.write("\n--- DRY RUN (first 20 URLs) ---")
            for u in unique_urls[:20]:
                self.stdout.write(f"  {u}")
            self.stdout.write(f"\nRun with --send to submit {len(unique_urls)} URLs to IndexNow.")
            return

        # Send in batches of BATCH_LIMIT
        chunks = [unique_urls[i:i+BATCH_LIMIT] for i in range(0, len(unique_urls), BATCH_LIMIT)]
        for idx, chunk in enumerate(chunks, 1):
            self.stdout.write(f"Sending batch {idx}/{len(chunks)} ({len(chunk)} URLs)...")
            success = self._send_batch(key, chunk)
            if success:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Batch {idx} accepted"))
            else:
                self.stdout.write(self.style.WARNING(f"  ✗ Batch {idx} failed"))
            if idx < len(chunks):
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"\nDone. {len(unique_urls)} URLs submitted to IndexNow."))

    # ─── URL generators ───────────────────────────────────────────────────────

    def _cuadrante_urls(self, deptos: list[str]) -> list[str]:
        urls = []
        for c in _CUADRANTES:
            urls.append(f"{SITE}/icfes/cuadrante/{c}/")
            for d in deptos:
                urls.append(f"{SITE}/icfes/cuadrante/{c}/{slugify(d)}/")
        return urls

    def _potencial_urls(self, deptos: list[str]) -> list[str]:
        urls = [f"{SITE}/icfes/supero-prediccion/"]
        for s in _POTENCIAL_SECTORS:
            urls.append(f"{SITE}/icfes/supero-prediccion/{s}/")
        for d in deptos:
            ds = slugify(d)
            urls.append(f"{SITE}/icfes/supero-prediccion/{ds}/")
            for s in _POTENCIAL_SECTORS:
                urls.append(f"{SITE}/icfes/supero-prediccion/{ds}/{s}/")
        return urls

    def _bilingues_urls(self, deptos: list[str]) -> list[str]:
        urls = [f"{SITE}/icfes/colegios-bilingues/"]
        for d in deptos:
            urls.append(f"{SITE}/icfes/departamento/{slugify(d)}/colegios-bilingues/")
        return urls

    def _mejoraron_urls(self) -> list[str]:
        return [
            f"{SITE}/icfes/colegios-que-mas-mejoraron/",
            f"{SITE}/icfes/colegios-que-mas-mejoraron/2024/",
            f"{SITE}/icfes/colegios-que-mas-mejoraron/2023/",
        ]

    # ─── DB helper ────────────────────────────────────────────────────────────

    def _get_deptos(self, conn) -> list[str]:
        rows = conn.execute(
            resolve_schema("""
                SELECT DISTINCT departamento
                FROM gold.fct_agg_colegios_ano
                WHERE CAST(ano AS INTEGER) = 2024
                  AND departamento IS NOT NULL AND departamento != ''
                ORDER BY departamento
            """)
        ).fetchall()
        return [r[0] for r in rows if r[0]]

    # ─── HTTP ─────────────────────────────────────────────────────────────────

    def _send_batch(self, key: str, url_list: list[str]) -> bool:
        payload = json.dumps({
            "host": "www.icfes-analytics.com",
            "key": key,
            "keyLocation": f"{SITE}/{key}.txt",
            "urlList": url_list,
        }).encode("utf-8")

        req = urllib.request.Request(
            INDEXNOW_ENDPOINT,
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "icfes-analytics-indexnow/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                self.stdout.write(f"    HTTP {status}")
                return status in (200, 202)
        except URLError as exc:
            self.stdout.write(f"    Error: {exc}")
            return False
