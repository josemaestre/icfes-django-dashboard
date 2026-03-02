# TODO PXX - Backlog Consolidado
**Fecha:** 2026-02-27  
**Contexto:** Pendientes detectados tras revisión de `web`, `dbt` y `data_science`.

---

## P0 (Crítico: cerrar en 1-2 semanas)

### P01 - Monetización end-to-end (web)
- [x] Completar flujo Wompi base de punta a punta (checkout + webhook + actualización de suscripción).
- [x] Corregir error de firma/checksum en webhook y validación con `X-Event-Checksum`.
- [x] Corregir `ALLOWED_HOSTS` local para pruebas webhook con ngrok (evitar 400 por host inválido).
- [x] Hacer pricing dinámico desde DB (`SubscriptionPlan`) para reflejar piloto/precios reales.
- [ ] Validar enforcement real de paywall en vistas premium.
- [ ] Definir plan de rollback ante fallos de webhook.
**Criterio de cierre:** un usuario nuevo puede pagar, activar plan y perder acceso al vencer/cancelar.

### P01.1 - Recurrente real Wompi (pendiente)
- [ ] Implementar flujo de `payment_source`/tokenización para guardar método reutilizable.
- [ ] Persistir `wompi_payment_method_id` en checkout para todos los casos aprobados.
- [ ] Ajustar `charge_monthly_subscriptions` para cobrar solo cuando exista `payment_source_id` válido.
- [ ] Definir fallback funcional: renovación manual cuando no exista `payment_source_id`.
**Criterio de cierre:** cobro mensual automático funcionando en al menos 3 usuarios de prueba y fallback manual operativo.

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

### P06.1 - Facturación electrónica DIAN (web + pagos)
- [ ] Seleccionar proveedor tecnológico DIAN (Siigo/Alegra/otro) y credenciales sandbox/prod.
- [ ] Capturar datos fiscales mínimos en checkout/perfil (`tipo_doc`, `num_doc`, `razon_social`, `direccion`, `municipio`, `departamento`, `email_facturacion`).
- [ ] Implementar modelo `Invoice` con trazabilidad (`wompi_transaction_id`, estado, `provider_invoice_id`, `cufe`, `pdf_url`, `xml_url`).
- [ ] Disparar emisión de factura tras `transaction.updated` APPROVED (task async con reintentos).
- [ ] Panel operativo para facturas `pending/rejected` y reproceso manual.
**Criterio de cierre:** cada pago aprobado genera factura electrónica validada DIAN (o queda en cola con estado trazable y reproceso).

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

### P10 - Gap de pipeline: Bogotá, Medellín y ranking por puntaje en campañas (dbt)

**Detectado:** 2026-03-01, durante importación de Campaña #1 de outbound sales.

**Síntomas:**
- `gold.fct_agg_colegios_ano` no tiene registros para Bogotá D.C. ni Medellín en ningún año.
  Son las dos ciudades con más colegios privados de Colombia — su ausencia es un bug, no un dato.
- `icfes_silver.colegios.colegio_bk` y `gold.fct_agg_colegios_ano.colegio_bk` no se solapan
  para los mismos colegios en 2024: los 375 colegios en Cali que tienen performance data tienen
  `email = NULL` en silver, y los 493 con email no aparecen en fct_agg.
- Consecuencia directa: el comando `import_campaign_prospects` no puede ordenar por puntaje ICFES.
  La Campaña #1 usa orden alfabético como fallback.

**Causa probable:**
- `colegio_bk` en `fct_agg` se deriva del código DANE del estudiante (campo `cole_cod_dane_establecimiento`
  del CSV de resultados), que puede incluir un prefijo de sede (1xx, 2xx, 3xx...).
- `colegio_bk` en `icfes_silver.colegios` viene de un registro administrativo diferente (SINEB o similar)
  con código sin prefijo de sede, o con diferente normalización.
- Bogotá puede estar registrada bajo un código de departamento especial (D.C.) que no mapea
  al departamento `Cundinamarca` en la tabla de dimensiones.

**Tareas para resolver:**
- [ ] Verificar qué valores de `cole_cod_dane_establecimiento` tienen los estudiantes de Bogotá
  en `icfes_silver.icfes` (campo `cole_depto_ubicacion` = 'Bogotá D.C.'?).
- [ ] Comparar longitud y formato de `colegio_bk` entre `fct_agg_colegios_ano` y `icfes_silver.colegios`
  para el mismo municipio → identificar si el prefijo de sede es el diferenciador.
- [ ] Corregir el modelo dbt que genera `colegio_bk` en `fct_agg` para normalizar al código
  base del colegio (sin prefijo de sede), igual que `icfes_silver.colegios`.
- [ ] Validar que después del fix, `JOIN fct_agg ON colegio_bk` retorna colegios con email.
- [ ] Actualizar `import_campaign_prospects` para usar `avg_punt_global` de `fct_agg` como criterio
  de ordenamiento (reemplazar el `0.0` y el `ORDER BY nombre_colegio`).
- [ ] Investigar por qué Bogotá y Medellín no aparecen en `fct_agg_colegios_ano` — revisar el
  modelo silver `icfes` para esas ciudades y el modelo gold que agrega por colegio.

**Impacto en campañas:**
- Campaña #1 funciona correctamente (80 prospectos con email, rector, demo URL).
- El ranking por puntaje es un "nice to have" para Tier 1 — el rector no sabe en qué orden
  está en nuestra lista.
- Bogotá y Medellín quedan fuera de la Campaña #1. Son las ciudades con más colegios privados
  premium → fix de pipeline es necesario antes de la Campaña #2.

**Criterio de cierre:** `SELECT COUNT(*) FROM gold.fct_agg_colegios_ano WHERE municipio IN ('Bogotá','Medellín') AND ano='2024'` retorna > 0, y el JOIN con `icfes_silver.colegios` en email retorna > 0 para Cali 2024.

### P11 - Módulo de Campañas Comerciales — Operación y Evolución

**Estado actual (2026-03-01):** Campaña #1 importada y lista para lanzar.
- 80 prospectos (8 ciudades × 10 colegios privados) con email, rector, teléfono y demo URL.
- Datos desde `gold.dim_colegios` (disponible en dev y prod).
- Gestión desde `/admin-icfes-2026/icfes_dashboard/campaign/`.

**Próximos pasos operativos (hacer ya):**
- [ ] Lanzar Campaña #1: ir al admin → abrir campaña → clic en **🚀 LANZAR CAMPAÑA**.
- [ ] Exportar CSV: admin → Ver prospectos → seleccionar todos → "Exportar a CSV".
- [ ] Decidir herramienta de envío (Mailchimp, Brevo, envío manual) y enviar primer batch.
- [ ] A medida que lleguen respuestas, marcar estado en admin (Respondió / Demo / Trial / Cliente).

**Speech / pitch sugerido para el email:**
> "Rector/a [nombre], le escribo desde ICFES Analytics. Su colegio [nombre colegio] tiene
> un análisis completo de sus resultados ICFES 2024 disponible en [demo_url]. Incluye
> comparación vs el país, fortalezas por materia, trayectoria histórica y potencial en inglés.
> ¿Le parece si agendamos 20 minutos para revisarlo juntos?"

**Mejoras técnicas pendientes:**
- [ ] Agregar integración de envío de email directo desde el admin (Anymail/SendGrid).
- [ ] Tracking de apertura y clicks en los emails enviados.
- [ ] Campaña #2: Bogotá + Medellín (requiere fix P10 de pipeline primero).
- [ ] Agregar columna `avg_punt_global` real desde `fct_agg` una vez resuelto P10.
- [ ] Vista de pipeline Kanban (visual por estado) en el admin o en una página dedicada.
- [ ] Automatizar importación periódica (Celery beat task mensual para nuevas ciudades).

**Criterio de cierre P11:** primer cliente pagando proveniente de esta campaña.

---

## Notas operativas
- Este backlog reemplaza listas dispersas para ejecución semanal.
- Revisión sugerida: cada viernes, con estado `Pendiente/En curso/Bloqueado/Done`.
