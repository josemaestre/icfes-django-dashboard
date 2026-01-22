-- Export Tier 1: Top 50 Bogotá
COPY (
SELECT
    c.nombre_colegio,
    c.rector,
    c.email,
    c.telefono,
    c.direccion,
    c.web,
    ROUND(f.avg_punt_global, 1) AS puntaje_2024,
    f.ranking_nacional,
    f.total_estudiantes,
    CONCAT('https://icfes-django-dashboard-production.up.railway.app/colegio/', c.colegio_sk) AS url_demo
FROM icfes_silver.colegios c
JOIN gold.fct_agg_colegios_ano f ON c.colegio_sk = f.colegio_sk AND f.ano = '2024'
WHERE c.sector = 'NO_OFICIAL'
  AND c.departamento = 'Bogotá DC'
  AND c.email IS NOT NULL
  AND LENGTH(c.email) > 5
  AND f.total_estudiantes >= 20
ORDER BY f.avg_punt_global DESC
LIMIT 50
) TO 'c:/proyectos/dbt/icfes_processing/tier1_prospects_bogota.csv' (HEADER, DELIMITER ',');
