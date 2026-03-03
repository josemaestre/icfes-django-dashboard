"""
Migración de recuperación: crea icfes_dashboard_mlanalisisia si no existe.

La migración 0004 pudo haberse marcado como aplicada durante un deploy
fallido (volume al 100%), dejando la tabla sin crear. Esta migración
usa IF NOT EXISTS para ser idempotente.
"""
from django.db import migrations


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS icfes_dashboard_mlanalisisia (
    id              BIGSERIAL PRIMARY KEY,
    ano_referencia  INTEGER NOT NULL,
    estado          VARCHAR(20) NOT NULL DEFAULT 'activo',
    analisis_md     TEXT NOT NULL,
    shap_narrative      TEXT NOT NULL DEFAULT '',
    clusters_narrative  TEXT NOT NULL DEFAULT '',
    riesgo_narrative    TEXT NOT NULL DEFAULT '',
    oportunidad_narrative TEXT NOT NULL DEFAULT '',
    modelo_ia       VARCHAR(100) NOT NULL DEFAULT 'claude-sonnet-4-6',
    fecha_generacion TIMESTAMPTZ NOT NULL,
    tokens_input    INTEGER,
    tokens_output   INTEGER
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS icfes_dashb_ano_ref_29d1b8_idx
    ON icfes_dashboard_mlanalisisia (ano_referencia, estado);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("icfes_dashboard", "0004_add_ml_analisis_ia"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_SQL + CREATE_INDEX_SQL,
            reverse_sql="DROP TABLE IF EXISTS icfes_dashboard_mlanalisisia;",
        ),
    ]
