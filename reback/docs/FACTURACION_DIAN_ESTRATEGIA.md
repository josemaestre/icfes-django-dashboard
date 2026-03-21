# Estrategia de Facturación Electrónica DIAN (SaaS B2B Colombia)

## 1. Contexto y Problema
En el modelo B2B (Business-to-Business) en Colombia, las instituciones educativas (Colegios Privados) exigen una **Factura Electrónica de Venta** validada por la DIAN para sus procesos contables y deducciones tributarias (impuestos). 
Actualmente, nuestra pasarela de pagos, **Wompi, procesa los pagos pero NO emite la factura electrónica de la DIAN.** Wompi únicamente nos avisa que el dinero entró (vía webhook), pero nosotros (ICFES Analytics) tenemos la obligación legal de emitir y enviar el documento.

## 2. Estrategia a Corto Plazo: Emisión Manual ("Do Things That Don't Scale")
Para minimizar el riesgo, el costo operativo y la complejidad técnica antes de la primera venta:
1. Las primeras 10-20 ventas/suscripciones se facturarán **manualmente**. Cada vez que llegue un pago de Wompi o una transferencia manual para los paquetes "Enterprise", entraremos a emitir la factura a través del **Facturador Gratuito de la DIAN** (MUISCA) o un software contable económico.
2. Requisito al cerrar la venta: En el *onboarding* de los primeros colegios Tier 1/Tier 2, nuestro equipo de ventas pedirá el RUT y extraerá manualmente la siguiente información obligatoria para elaborar una factura:
   - NIT
   - Razón Social
   - Correo exclusivo para la recepción de facturación electrónica
   - Responsabilidades Tributarias / Obligaciones Fiscales
   - Código CIIU Principal
   - Dirección y Municipio

## 3. Estrategia a Mediano Plazo: Automatización (SaaS Escalable)
Una vez validadas las ventas recurrentes de la plataforma (Product-Market Fit del plan B2B), migraremos a un desarrollo 100% automatizado mediante un API de un **Proveedor Tecnológico**.

### El Flujo Automatizado Completo:
1. **Checkout Inteligente:** En el portal de precios (`/pricing/`), el colegio proporcionará sus datos fiscales en un formulario propio de la plataforma antes de ir a Wompi. Esto quedará guardado junto a su perfil en nuestra BD PostgreSQL.
2. **Proceso Desatendido:** El cliente paga. Wompi envía el Webhook asíncrono confirmando el cobro en `/payments/wompi/webhook/`.
3. **Orquestación en Celery:** Ese webhook activa una tarea remota de nuestro backend que llama por HTTP/POST a nuestro Proveedor Tecnológico.
4. **Emisión Inmediata:** El Proveedor valida con la DIAN devolviendo el CUFE asíncronamente y envía automáticamente el `.xml` junto con la representación `.pdf` de la factura al correo contable del colegio.

### Opciones de APIs/Proveedores:
1. **Alegra API (Recomendado):** Es la mejor documentación de API REST (con Python) en el mercado regional. Costo asociado alrededor de ~$90k COP/mes para emprendedores.
2. **Siigo API (Alternativa):** Muy conocido por las contabilidades de colegios en Colombia pero la integración requiere algo más de trabajo profundo a nivel HTTP.

## 4. Requisitos en Base de Datos (Cuando Pasemos a Fase 2)
- Extender el modelo de perfil de usuario actual en Django para soportar campos obligatorios que requiere la DIAN antes de invocar la API:
   - `billing_nit`
   - `billing_razon_social`
   - `billing_email`
   - `billing_address`
   - `billing_ciiu`

---
*Este documento es fundamental para las políticas comerciales de la startup antes de escalar masivamente campañas B2B en Colombia.*
