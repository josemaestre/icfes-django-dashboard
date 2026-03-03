"""
Encodings y mapeos de features categóricas para el modelo ICFES.
Todas las funciones son puras — sin efectos secundarios.
"""
import numpy as np
import pandas as pd

# ── Mapeos ordinales ───────────────────────────────────────────────────────────

ESTRATO_MAP = {
    'Sin Estrato': 0,
    'Estrato 1': 1,
    'Estrato 2': 2,
    'Estrato 3': 3,
    'Estrato 4': 4,
    'Estrato 5': 5,
    'Estrato 6': 6,
}

EDU_MAP = {
    'Ninguno': 0,
    'No sabe': 0,
    'Primaria incompleta': 1,
    'Primaria completa': 2,
    'Secundaria (Bachillerato) incompleta': 3,
    'Secundaria (Bachillerato) completa': 4,
    'Técnica o tecnológica incompleta': 5,
    'Técnica o tecnológica completa': 6,
    'Educación profesional incompleta': 7,
    'Educación profesional completa': 8,
    'Postgrado': 9,
}

LIBROS_MAP = {
    '0 a 10': 1,
    '11 a 25': 2,
    '26 a 100': 3,
    'Más de 100': 4,
}

SITUACION_ECO_MAP = {
    'Le alcanza para cubrir los gastos mínimos': 1,
    'No le alcanza, tiene dificultades': 2,
    'No le alcanza y tiene deudas': 3,
    'Cubre los gastos mínimos y algo más': 4,
    'Cubre más que los gastos mínimos': 5,
}

HORAS_TRABAJO_MAP = {
    '0': 0,
    'Menos de 10 horas': 1,
    'Entre 11 y 20 horas': 2,
    'Entre 21 y 30 horas': 3,
    'Más de 30 horas': 4,
}

HORAS_LECTURA_MAP = {
    'No leo': 0,
    'Entre 0 y 30 minutos': 1,
    'Entre 30 minutos y 1 hora': 2,
    'Entre 1 y 2 horas': 3,
    'Más de 2 horas': 4,
}

BINARY_MAP = {'Si': 1, 'No': 0, 'S': 1, 'N': 0}

NATURALEZA_MAP = {'NO OFICIAL': 1, 'OFICIAL': 0}

AREA_MAP = {'URBANO': 1, 'RURAL': 0}

GENERO_MAP = {'F': 0, 'M': 1}

# ── Columnas del modelo ────────────────────────────────────────────────────────

FEATURE_COLS = [
    'fami_estratovivienda',
    'fami_educacionmadre',
    'fami_educacionpadre',
    'fami_tieneinternet',
    'fami_tienecomputador',
    'fami_numlibros',
    'fami_personashogar',
    'fami_situacioneconomica',
    'cole_naturaleza',
    'cole_area_ubicacion',
    'estu_genero',
    'estu_horassemanatrabaja',
    'estu_dedicacionlecturadiaria',
    'ano',
    'pct_nbi_total',
]

# Nombres legibles para la UI del dashboard
FEATURE_LABELS = {
    'fami_estratovivienda':       'Estrato de la vivienda',
    'fami_educacionmadre':        'Educación de la madre',
    'fami_educacionpadre':        'Educación del padre',
    'fami_tieneinternet':         'Internet en el hogar',
    'fami_tienecomputador':       'Computador en el hogar',
    'fami_numlibros':             'Libros en casa',
    'fami_personashogar':         'Personas en el hogar',
    'fami_situacioneconomica':    'Situación económica familiar',
    'cole_naturaleza':            'Colegio privado (no oficial)',
    'cole_area_ubicacion':        'Área urbana',
    'estu_genero':                'Género del estudiante',
    'estu_horassemanatrabaja':    'Horas semanales trabajando',
    'estu_dedicacionlecturadiaria': 'Lectura diaria del estudiante',
    'ano':                        'Año del examen',
    'pct_nbi_total':              'NBI del municipio (% pobreza)',
}

FEATURE_ICONS = {
    'fami_estratovivienda':       '🏠',
    'fami_educacionmadre':        '👩‍🎓',
    'fami_educacionpadre':        '👨‍🎓',
    'fami_tieneinternet':         '🌐',
    'fami_tienecomputador':       '💻',
    'fami_numlibros':             '📚',
    'fami_personashogar':         '👨‍👩‍👧',
    'fami_situacioneconomica':    '💰',
    'cole_naturaleza':            '🏫',
    'cole_area_ubicacion':        '🏙️',
    'estu_genero':                '⚧',
    'estu_horassemanatrabaja':    '⏰',
    'estu_dedicacionlecturadiaria': '📖',
    'ano':                        '📅',
    'pct_nbi_total':              '📍',
}


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte columnas categóricas a numéricas e imputa valores faltantes.
    Devuelve un DataFrame con exactamente las columnas FEATURE_COLS, todas numéricas.
    """
    out = pd.DataFrame(index=df.index)

    out['fami_estratovivienda'] = (
        df['fami_estratovivienda'].map(ESTRATO_MAP).fillna(0).astype(float)
    )
    out['fami_educacionmadre'] = (
        df['fami_educacionmadre'].map(EDU_MAP).fillna(df['fami_educacionmadre'].map(EDU_MAP).median()).astype(float)
    )
    out['fami_educacionpadre'] = (
        df['fami_educacionpadre'].map(EDU_MAP).fillna(df['fami_educacionpadre'].map(EDU_MAP).median()).astype(float)
    )
    out['fami_tieneinternet'] = (
        df['fami_tieneinternet'].str.strip().map(BINARY_MAP).fillna(0).astype(float)
    )
    out['fami_tienecomputador'] = (
        df['fami_tienecomputador'].str.strip().map(BINARY_MAP).fillna(0).astype(float)
    )
    out['fami_numlibros'] = (
        df['fami_numlibros'].map(LIBROS_MAP).fillna(1).astype(float)
    )
    out['fami_personashogar'] = (
        pd.to_numeric(df['fami_personashogar'], errors='coerce').fillna(4).astype(float)
    )
    out['fami_situacioneconomica'] = (
        df['fami_situacioneconomica'].map(SITUACION_ECO_MAP).fillna(3).astype(float)
    )
    out['cole_naturaleza'] = (
        df['cole_naturaleza'].str.strip().str.upper().map(NATURALEZA_MAP).fillna(0).astype(float)
    )
    out['cole_area_ubicacion'] = (
        df['cole_area_ubicacion'].str.strip().str.upper().map(AREA_MAP).fillna(1).astype(float)
    )
    out['estu_genero'] = (
        df['estu_genero'].str.strip().map(GENERO_MAP).fillna(0).astype(float)
    )
    out['estu_horassemanatrabaja'] = (
        df['estu_horassemanatrabaja'].map(HORAS_TRABAJO_MAP).fillna(0).astype(float)
    )
    out['estu_dedicacionlecturadiaria'] = (
        df['estu_dedicacionlecturadiaria'].map(HORAS_LECTURA_MAP).fillna(1).astype(float)
    )
    out['ano'] = pd.to_numeric(df['ano'], errors='coerce').fillna(2020).astype(float)
    out['pct_nbi_total'] = pd.to_numeric(df['pct_nbi_total'], errors='coerce').fillna(
        df['pct_nbi_total'].astype(float).median() if 'pct_nbi_total' in df.columns else 30.0
    ).astype(float)

    return out[FEATURE_COLS]
