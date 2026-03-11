"""
Vistas para generar graficas PNG on-the-fly para emails.
"""
from __future__ import annotations

from io import BytesIO
from textwrap import fill

from django.http import HttpResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods

from .db_utils import execute_query


def _safe_slug(value: str) -> str:
    txt = (value or "").strip().lower()
    return "".join(ch for ch in txt if ch.isalnum() or ch in ("-", "_"))


def _query_history(slug: str, years: int):
    query = """
        WITH hist AS (
            SELECT
                s.slug,
                CAST(f.ano AS INTEGER) AS ano,
                f.avg_punt_global,
                ROW_NUMBER() OVER (
                    PARTITION BY s.slug
                    ORDER BY CAST(f.ano AS INTEGER) DESC
                ) AS rn
            FROM gold.fct_agg_colegios_ano f
            INNER JOIN gold.dim_colegios_slugs s
                ON s.codigo = f.colegio_bk
            WHERE s.slug = ?
              AND f.sector IN ('NO OFICIAL', 'NO_OFICIAL')
              AND f.avg_punt_global IS NOT NULL
              AND f.avg_punt_global > 0
        )
        SELECT slug, ano, avg_punt_global
        FROM hist
        WHERE rn <= ?
        ORDER BY ano
    """
    return execute_query(query, params=[slug, years])


def _render_png(slug: str, years: int, df):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 2.8))

    if df.empty:
        ax.text(
            0.5,
            0.5,
            f"Sin datos historicos\n{slug}",
            ha="center",
            va="center",
            fontsize=12,
        )
        ax.set_axis_off()
    else:
        years_arr = df["ano"].astype(int).tolist()
        scores_arr = df["avg_punt_global"].astype(float).tolist()
        ax.plot(years_arr, scores_arr, marker="o", linewidth=2.0)
        ax.set_title("Evolucion del puntaje global (SABER 11)")
        ax.set_xlabel("Ano")
        ax.set_ylabel("Puntaje")
        ax.grid(alpha=0.25)

        ymin = max(0, min(scores_arr) - 15)
        ymax = max(scores_arr) + 15
        ax.set_ylim(ymin, ymax)
        ax.set_xticks(years_arr)

    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=120)
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


def _query_social_card_data(slug: str):
    query = """
        WITH school AS (
            SELECT
                s.codigo AS colegio_bk,
                s.slug,
                COALESCE(d.nombre_colegio, '') AS nombre_colegio,
                COALESCE(d.municipio, '') AS municipio,
                COALESCE(d.departamento, '') AS departamento,
                COALESCE(d.sector, '') AS sector
            FROM gold.dim_colegios_slugs s
            LEFT JOIN gold.dim_colegios d
                ON d.colegio_bk = s.codigo
            WHERE s.slug = ?
            LIMIT 1
        ),
        latest_score AS (
            SELECT
                f.colegio_bk,
                CAST(f.ano AS INTEGER) AS ano_icfes,
                f.avg_punt_global,
                ROW_NUMBER() OVER (
                    PARTITION BY f.colegio_bk
                    ORDER BY CAST(f.ano AS INTEGER) DESC
                ) AS rn
            FROM gold.fct_agg_colegios_ano f
            INNER JOIN school sc
                ON sc.colegio_bk = f.colegio_bk
            WHERE f.avg_punt_global IS NOT NULL
              AND f.avg_punt_global > 0
        )
        SELECT
            sc.slug,
            sc.nombre_colegio,
            sc.municipio,
            sc.departamento,
            sc.sector,
            ls.ano_icfes,
            ls.avg_punt_global
        FROM school sc
        LEFT JOIN latest_score ls
            ON ls.colegio_bk = sc.colegio_bk
           AND ls.rn = 1
    """
    return execute_query(query, params=[slug])


def _render_social_card_png(slug: str, df):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 1200x630 (Open Graph recommended)
    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    # Background gradient: 2x2 array, matplotlib bilinear-interpolates to full size.
    # Replaces a 1200x630 numpy meshgrid (756K floats) — same visual, near-zero cost.
    c1 = [30 / 255, 77 / 255, 146 / 255]   # blue
    c2 = [15 / 255, 118 / 255, 110 / 255]  # teal
    ax.imshow([[c1, c1], [c2, c2]], extent=[0, 1, 0, 1], aspect="auto", interpolation="bilinear")

    # Content
    if df.empty:
        name = slug.replace("-", " ").upper()
        subtitle = "Perfil ICFES del colegio"
        score_line = "Sin datos de puntaje"
        location_line = ""
    else:
        row = df.iloc[0]
        name = (row.get("nombre_colegio") or slug).upper()
        municipio = row.get("municipio") or ""
        departamento = row.get("departamento") or ""
        ano = row.get("ano_icfes")
        score = row.get("avg_punt_global")
        score_txt = "N/A" if score is None else str(int(round(float(score), 0)))
        ano_txt = "N/A" if ano is None else str(int(ano))

        subtitle = "Resultados SABER 11 (ICFES)"
        score_line = f"Puntaje global {ano_txt}: {score_txt}"
        location_line = f"{municipio}, {departamento}".strip(", ")

    wrapped_name = fill(name, width=34)

    ax.text(
        0.06, 0.80, "ICFES Analytics",
        color="white", fontsize=22, fontweight="bold", ha="left", va="top",
    )
    ax.text(
        0.06, 0.68, wrapped_name,
        color="white", fontsize=42, fontweight="bold", ha="left", va="top",
        linespacing=1.1,
    )
    ax.text(
        0.06, 0.34, subtitle,
        color="#e5e7eb", fontsize=22, ha="left", va="top",
    )
    ax.text(
        0.06, 0.24, score_line,
        color="white", fontsize=28, fontweight="bold", ha="left", va="top",
    )
    if location_line:
        ax.text(
            0.06, 0.16, location_line,
            color="#d1d5db", fontsize=20, ha="left", va="top",
        )

    # Brand badge
    ax.text(
        0.94, 0.08, "icfes-analytics.com",
        color="#e5e7eb", fontsize=16, ha="right", va="bottom",
    )

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=100)
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


@cache_page(60 * 60 * 24)  # 24h
@require_http_methods(["GET"])
def email_graph_png(request, slug):
    clean_slug = _safe_slug(slug)
    years_raw = request.GET.get("years", "4")
    try:
        years = int(years_raw)
    except ValueError:
        years = 4
    years = min(max(years, 1), 10)

    df = _query_history(clean_slug, years)
    png_bytes = _render_png(clean_slug, years, df)

    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="{clean_slug}.png"'
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Email-Graph"] = f"slug={clean_slug}; years={years}"
    return response


@cache_page(60 * 60 * 24)  # 24h
@require_http_methods(["GET", "HEAD"])
def social_card_school_png(request, slug):
    clean_slug = _safe_slug(slug)
    df = _query_social_card_data(clean_slug)
    png_bytes = _render_social_card_png(clean_slug, df)

    response = HttpResponse(png_bytes, content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="social-{clean_slug}.png"'
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Social-Card"] = f"slug={clean_slug}"
    return response
