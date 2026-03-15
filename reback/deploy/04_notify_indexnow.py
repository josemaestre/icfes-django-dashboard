"""
Script 4: Notify IndexNow

Submits all updated URLs to IndexNow after a deploy.
IndexNow is supported by Bing, Yandex and other search engines.

Requires env vars:
  INDEXNOW_KEY     — key registered at indexnow.org / Bing Webmaster Tools
  PUBLIC_SITE_URL  — e.g. https://www.icfes-analytics.com

Run after deploy:
  python deploy/04_notify_indexnow.py
"""
import json
import os
import platform
import urllib.request
import urllib.error
from pathlib import Path

import duckdb
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# DB path: env var > OS default
def _default_prod_db():
    if platform.system() == "Windows":
        return Path(r"C:\proyectos\dbt\icfes_processing\prod.duckdb")
    return Path("/home/ubuntu/dbt/icfes_processing/prod.duckdb")

PROD_DB = Path(os.getenv("PROD_DB_PATH", str(_default_prod_db())))
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH_SIZE = 10_000  # IndexNow max per request


def _load_env():
    # Try .env files in common locations
    for candidate in [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / ".envs" / ".local" / ".django",
        Path(__file__).parent.parent / ".envs" / ".production" / ".django",
    ]:
        if candidate.exists():
            load_dotenv(candidate)
            break

    key = os.getenv("INDEXNOW_KEY", "").strip()
    base = os.getenv("PUBLIC_SITE_URL", "").strip().rstrip("/")
    return key, base


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

def _static_urls(base):
    return [
        f"{base}/",
        f"{base}/icfes/ranking/",
        f"{base}/icfes/departamentos/",
        f"{base}/icfes/historia/",
        f"{base}/icfes/ingles/",
        f"{base}/icfes/historico/puntaje-global/",
        f"{base}/icfes/colegios-bilingues/",
        f"{base}/icfes/que-es-icfes-analytics/",
        f"{base}/icfes/materia/matematicas/",
        f"{base}/icfes/materia/ingles/",
        f"{base}/icfes/colegios-que-mas-mejoraron/",
    ]


def _db_urls(base):
    """Generate geo + school URLs from prod.duckdb."""
    urls = []

    if not PROD_DB.exists():
        print(f"  ⚠️  prod_v2.duckdb not found at {PROD_DB} — skipping DB URLs")
        return urls

    conn = duckdb.connect(str(PROD_DB), read_only=True)

    try:
        from slugify import slugify

        # Departamentos
        rows = conn.execute("""
            SELECT DISTINCT departamento
            FROM main.fct_agg_colegios_ano
            WHERE departamento IS NOT NULL AND departamento != ''
              AND ano = (SELECT MAX(ano) FROM main.fct_agg_colegios_ano)
            ORDER BY departamento
        """).fetchall()
        for (dept,) in rows:
            slug = slugify(dept)
            urls.append(f"{base}/icfes/departamento/{slug}/")
            urls.append(f"{base}/icfes/departamento/{slug}/colegios-bilingues/")
            urls.append(f"{base}/icfes/ranking/sector/oficiales/departamento/{slug}/")
            urls.append(f"{base}/icfes/ranking/sector/privados/departamento/{slug}/")

        # Municipios
        rows = conn.execute("""
            SELECT DISTINCT departamento, municipio
            FROM main.fct_agg_colegios_ano
            WHERE departamento IS NOT NULL AND departamento != ''
              AND municipio IS NOT NULL AND municipio != ''
              AND ano = (SELECT MAX(ano) FROM main.fct_agg_colegios_ano)
            ORDER BY departamento, municipio
        """).fetchall()
        for dept, muni in rows:
            d = slugify(dept)
            m = slugify(muni)
            urls.append(f"{base}/icfes/departamento/{d}/municipio/{m}/")

        # School pages (slug-based)
        rows = conn.execute("""
            SELECT slug FROM main.dim_colegios_slugs
            WHERE slug IS NOT NULL AND slug != ''
            ORDER BY slug
        """).fetchall()
        for (slug,) in rows:
            urls.append(f"{base}/icfes/colegio/{slug}/")

        # Ranking by year
        years = conn.execute("""
            SELECT DISTINCT CAST(ano AS INTEGER)
            FROM main.fct_agg_colegios_ano
            WHERE ano IS NOT NULL
            ORDER BY 1 DESC
            LIMIT 5
        """).fetchall()
        for (year,) in years:
            urls.append(f"{base}/icfes/ranking/colegios/{year}/")
            urls.append(f"{base}/icfes/materia/matematicas/{year}/")
            urls.append(f"{base}/icfes/materia/ingles/{year}/")
            urls.append(f"{base}/icfes/colegios-que-mas-mejoraron/{year}/")

    finally:
        conn.close()

    return urls


# ---------------------------------------------------------------------------
# IndexNow submission
# ---------------------------------------------------------------------------

def _post_batch(key, host, urls):
    payload = json.dumps({
        "host": host,
        "key": key,
        "urlList": urls,
    }).encode("utf-8")

    req = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return None, str(e)


def _submit(key, base, urls):
    from urllib.parse import urlparse
    host = urlparse(base).netloc

    total = len(urls)
    submitted = 0
    failed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = urls[i: i + BATCH_SIZE]
        status, body = _post_batch(key, host, batch)

        if status in (200, 202):
            submitted += len(batch)
            print(f"  ✅ Batch {i // BATCH_SIZE + 1}: {len(batch)} URLs → HTTP {status}")
        else:
            failed += len(batch)
            print(f"  ❌ Batch {i // BATCH_SIZE + 1}: HTTP {status} — {body[:200]}")

    return submitted, failed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 80)
    print("STEP 4: NOTIFY INDEXNOW")
    print("=" * 80)

    key, base = _load_env()

    if not key:
        print("\n⚠️  INDEXNOW_KEY not set — skipping (not a fatal error)")
        return True

    if not base:
        print("\n⚠️  PUBLIC_SITE_URL not set — skipping (not a fatal error)")
        return True

    print(f"\n🔑 Key: {key[:8]}...")
    print(f"🌐 Site: {base}")

    print("\n📋 Building URL list...")
    urls = _static_urls(base)
    print(f"  Static pages: {len(urls)}")

    db_urls = _db_urls(base)
    print(f"  DB pages (geo + schools + rankings): {len(db_urls)}")

    all_urls = list(dict.fromkeys(urls + db_urls))  # deduplicate, preserve order
    print(f"  Total unique URLs: {len(all_urls)}")

    print("\n📤 Submitting to IndexNow...")
    submitted, failed = _submit(key, base, all_urls)

    print(f"\n{'✅' if failed == 0 else '⚠️ '} Done — {submitted} submitted, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
