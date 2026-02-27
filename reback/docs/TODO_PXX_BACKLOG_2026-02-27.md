# TODO PXX - Backlog Consolidado
**Fecha:** 2026-02-27  
**Contexto:** Pendientes detectados tras revisión de `web`, `dbt` y `data_science`.

---

## P0 (Crítico: cerrar en 1-2 semanas)

### P01 - Monetización end-to-end (web)
- [ ] Completar flujo Stripe/Wompi de punta a punta (checkout + webhook + actualización de suscripción).
- [ ] Validar enforcement real de paywall en vistas premium.
- [ ] Definir plan de rollback ante fallos de webhook.
**Criterio de cierre:** un usuario nuevo puede pagar, activar plan y perder acceso al vencer/cancelar.

### P02 - CI/CD mínimo obligatorio (web + dbt)
- [ ] GitHub Actions en `www/reback`: lint + tests.
- [ ] GitHub Actions en `dbt/icfes_processing`: `dbt test`.
- [ ] Branch protection en `main`.
**Criterio de cierre:** no hay merge a `main` sin checks verdes.

### P03 - Seguridad base de producción (web)
- [ ] Confirmar `DEBUG=False` en producción.
- [ ] Rate limiting en endpoints públicos.
- [ ] Revisar rotación de secretos y variables sensibles.
**Criterio de cierre:** checklist de seguridad mínima aplicado y validado.

---

## P1 (Alto impacto: 2-4 semanas)

### P04 - SEO técnico y control de crawl budget (web)
- [ ] Excluir del sitemap landings sin datos útiles.
- [ ] Definir política `noindex`/`410` para colegios sin histórico.
- [ ] Corregir fallback de año en FAQ cuando no existe dato real.
**Criterio de cierre:** reducción de páginas afectadas en GSC y menor rastreo inútil.

### P05 - Observabilidad accionable (web)
- [ ] Mantener `X-Cache` y logs `perf` por variable de entorno.
- [ ] Dashboard operativo con métricas: `%HIT`, p95, top rutas MISS, top bots.
- [ ] Alertas cuando MISS o latencia superen umbral.
**Criterio de cierre:** reporte semanal con decisiones basadas en métricas.

### P06 - Higiene de repos y convenciones (web + data_science)
- [ ] Estándar de carpetas para scripts ad-hoc (`scripts_local/` o `notebooks/`).
- [ ] Política para artefactos binarios (`.joblib`) y outputs.
- [ ] Documento de “qué se versiona y qué no”.
**Criterio de cierre:** repos limpios y reglas documentadas.

---

## P2 (Construcción de ventaja: 1-2 meses)

### P07 - Consolidar módulo de inglés en producción (dbt + web + ds)
- [ ] Desplegar/validar tablas de inglés en `prod`.
- [ ] Corregir bug de `Pre A1 = 0` en capa de datos.
- [ ] Alinear dashboard y documentación con modelo vigente.
**Criterio de cierre:** dashboard de inglés consistente con datos de producción.

### P08 - Data Science productizable (data_science)
- [ ] Pipeline reproducible (deps, config, versionado de modelos).
- [ ] Priorización de modelos pendientes (anomalías, forecasting).
- [ ] Validación/monitoreo de desempeño de modelos en producción.
**Criterio de cierre:** entrenamiento y deploy reproducibles, con métricas trazables.

### P09 - Tests funcionales del core de negocio (web)
- [ ] Tests de suscripciones, límites, upgrades y exportaciones.
- [ ] Tests de rutas SEO clave y respuestas de cache.
- [ ] Smoke tests post-deploy.
**Criterio de cierre:** cobertura mínima en rutas críticas y menor riesgo de regresión.

---

## Notas operativas
- Este backlog reemplaza listas dispersas para ejecución semanal.
- Revisión sugerida: cada viernes, con estado `Pendiente/En curso/Bloqueado/Done`.
