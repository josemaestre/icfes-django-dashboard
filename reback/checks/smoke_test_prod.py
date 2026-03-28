"""
smoke_test_prod.py — Verifica que todas las páginas clave responden 200.

Uso:
    python checks/smoke_test_prod.py                    # contra prod (icfes-analytics.com)
    python checks/smoke_test_prod.py --base http://127.0.0.1:8000   # contra dev local

Lee el sitemap-index para descubrir URLs automáticamente + lista de URLs
críticas hardcodeadas que representan cada tipo de página.

Salida:
    ✅  200  /icfes/departamentos/
    ❌  404  /icfes/ranking/matematicas/2024/
    ⚠️  302  /icfes/departamento/bogota-dc/  (redirect)

Al final imprime un resumen con el conteo de errores.
"""

import sys
import time
import argparse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Instala requests: pip install requests")
    sys.exit(1)

BASE = "https://www.icfes-analytics.com"

# URLs críticas que representan cada tipo de página (siempre se testean)
CRITICAL_URLS = [
    # Índices
    "/icfes/departamentos/",
    "/icfes/ranking/colegios/2024/",
    "/icfes/ranking/matematicas/2024/",
    "/icfes/historico/puntaje-global/",
    "/icfes/materia/ingles/2024/",
    "/icfes/materia/matematicas/2024/",
    "/icfes/colegios-que-mas-mejoraron/",    # 302 → /2024/ (hub redirect — expected)
    "/icfes/colegios-que-mas-mejoraron/2024/",

    # Departamentos
    "/icfes/departamento/bogota-dc/",
    "/icfes/departamento/antioquia/",
    "/icfes/departamento/amazonas/",        # depto pequeño
    "/icfes/departamento/quindio/",         # depto con bug histórico

    # Municipios
    "/icfes/departamento/bogota-dc/municipio/bogota-dc/",
    "/icfes/departamento/amazonas/municipio/leticia/",
    "/icfes/departamento/amazonas/municipio/puerto-arica/",  # municipio sin datos

    # Ranking sector
    "/icfes/ranking/sector/privados/colombia/",
    "/icfes/ranking/sector/oficiales/colombia/",
    "/icfes/ranking/sector/privados/departamento/bogota-dc/",
    "/icfes/ranking/sector/privados/departamento/bogota-dc/municipio/bogota-dc/",

    # Colegios bilingues
    "/icfes/departamento/antioquia/colegios-bilingues/",

    # Bandas motivacionales
    "/icfes/bandas-motivacionales/",
    "/icfes/bandas-motivacionales/antioquia/",

    # Cuadrante / supero predicción
    "/icfes/cuadrante/estrella/bogota-dc/",
    "/icfes/supero-prediccion/bogota-dc/",

    # Landing pages
    "/icfes/que-es-icfes-analytics/",

    # Auth
    "/accounts/login/",
    "/accounts/signup/",

    # Sitemaps
    "/sitemap.xml",
    "/sitemap-departamentos.xml",
    "/sitemap-municipios.xml",
    "/sitemap-colegios.xml",
]

# Códigos que se consideran "OK" (200 y 301 perm redirect son OK para SEO)
OK_CODES = {200, 301}
WARN_CODES = {302}      # redirect temporal — puede ser intencional
SKIP_CODES = {410}      # Gone — intencional para URLs obsoletas


def fetch_sitemap_urls(base, max_urls=200):
    """Descarga el sitemap-index y extrae una muestra de URLs de cada sub-sitemap."""
    urls = []
    try:
        resp = requests.get(f"{base}/sitemap.xml", timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return urls
        root = ET.fromstring(resp.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemaps = [el.text for el in root.findall(".//sm:loc", ns)]
        print(f"  → {len(sitemaps)} sub-sitemaps encontrados")

        per_sitemap = max(1, max_urls // max(len(sitemaps), 1))
        for sitemap_url in sitemaps:
            try:
                r = requests.get(sitemap_url, timeout=15)
                if r.status_code != 200:
                    continue
                sub = ET.fromstring(r.content)
                locs = [el.text for el in sub.findall(".//sm:loc", ns)]
                # Toma una muestra: primero, último, y algunos del medio
                sample = locs[:per_sitemap]
                for loc in sample:
                    path = urlparse(loc).path
                    if path not in urls:
                        urls.append(path)
            except Exception:
                pass
    except Exception as e:
        print(f"  ⚠️  No se pudo leer el sitemap: {e}")
    return urls


def check_url(base, path, session, timeout=15):
    url = f"{base}{path}"
    try:
        t0 = time.time()
        resp = session.get(url, timeout=timeout, allow_redirects=False,
                          headers={"User-Agent": "smoke-test/1.0"})
        ms = int((time.time() - t0) * 1000)
        return path, resp.status_code, ms, None
    except requests.exceptions.ConnectionError:
        return path, 0, 0, "connection error"
    except requests.exceptions.Timeout:
        return path, 0, 0, "timeout"
    except Exception as e:
        return path, 0, 0, str(e)


def main():
    parser = argparse.ArgumentParser(description="Smoke test de páginas ICFES Analytics")
    parser.add_argument("--base", default=BASE, help="Base URL (default: producción)")
    parser.add_argument("--sitemap", action="store_true", help="También testea URLs del sitemap")
    parser.add_argument("--workers", type=int, default=5, help="Requests paralelos (default: 5)")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout en segundos (default: 20)")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    print(f"\n🔍  Smoke test contra: {base}")
    print(f"    Workers: {args.workers} | Timeout: {args.timeout}s\n")

    paths = list(CRITICAL_URLS)

    if args.sitemap:
        print("📦  Descargando URLs del sitemap...")
        sitemap_paths = fetch_sitemap_urls(base, max_urls=150)
        new = [p for p in sitemap_paths if p not in paths]
        paths.extend(new)
        print(f"    +{len(new)} URLs del sitemap\n")

    results = []
    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(check_url, base, p, session, args.timeout): p for p in paths}
            done = 0
            for future in as_completed(futures):
                path, code, ms, err = future.result()
                results.append((path, code, ms, err))
                done += 1
                # Progreso en línea
                icon = "✅" if code in OK_CODES else ("⚠️ " if code in WARN_CODES else ("⏭️ " if code in SKIP_CODES else "❌"))
                code_str = str(code) if code else "ERR"
                print(f"  {icon}  {code_str:>3}  {ms:>5}ms  {path}", flush=True)

    # Resumen
    errors = [(p, c, e) for p, c, ms, e in results if c not in OK_CODES | WARN_CODES | SKIP_CODES]
    warns  = [(p, c, e) for p, c, ms, e in results if c in WARN_CODES]
    skips  = [(p, c, e) for p, c, ms, e in results if c in SKIP_CODES]
    ok     = [(p, c, e) for p, c, ms, e in results if c in OK_CODES]

    print(f"\n{'='*60}")
    print(f"  Total:    {len(results)}")
    print(f"  ✅  OK:    {len(ok)}")
    print(f"  ⚠️   Warn: {len(warns)}  (redirects temporales)")
    print(f"  ⏭️   Skip: {len(skips)}  (410 Gone — intencional)")
    print(f"  ❌  Errores: {len(errors)}")

    if errors:
        print(f"\n❌  Páginas con error:")
        for path, code, err in errors:
            detail = f" ({err})" if err else ""
            print(f"     {code:>3}  {path}{detail}")

    print()
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
