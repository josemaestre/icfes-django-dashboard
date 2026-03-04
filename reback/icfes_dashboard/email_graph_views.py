"""
Vistas para generar graficas PNG on-the-fly para emails.
"""
from __future__ import annotations

from io import BytesIO

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
