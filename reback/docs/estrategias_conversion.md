# Estrategia de Conversión y Ventas B2B - ICFES Analytics

## Contexto Actual
- **Hito:** 30 usuarios registrados en el primer mes de lanzamiento. (¡Excelente validación de mercado!)
- **Desafío:** 0 ventas del plan *Pro Estratégico*.
- **Plan Pro:** $990.000 COP / año.
- **Ciclo B2B:** El ciclo de ventas promedio en EdTech para tickets superiores a $500,000 COP toma entre **3 a 8 semanas**. Los rectores o coordinadores deben probar el valor, presentarlo al colegio, aprobar presupuesto y pagar (generalmente con factura/cuenta de cobro, no tarjeta).

---

## Análisis del Embudo (Google Analytics 4)

1. **Tráfico Sano:** Más de 1.800 usuarios activos y una tasa de registro muy positiva (~25% de los que visitan la página de login).
2. **Fricción de Visibilidad:** La página de *Planes y Precios* **no** aparece en el Top 10 de páginas visitadas. Los usuarios entran, ven la información gratuita de su colegio (1 min promedio) y se van sin conocer los beneficios del plan Pro.

---

## Estrategias a Corto y Mediano Plazo

### 1. Venta "Concierge" Inmediata (Para los 30 leads actuales)
Dado que llevas un mes, la venta requiere intervención humana y personalizada. Wompi no cerrará estas ventas automáticamente por ahora.
- **Acción:** Envía un email manual y corto a cada uno de los 30 usuarios registrados.
- **Ejemplo de correo:**
  > *"Hola [Nombre], soy [Tu Nombre/José], creador de ICFES Analytics. Vi que te registraste hace unos días buscando métricas. Quería preguntarte: ¿Te fue útil la información gratuita? Me encantaría regalarte 15 minutos en videollamada para mostrarte el historial absoluto de tu colegio desde 1996 y analizar cómo estas herramientas ayudan a subir en el ranking."*
- **Objetivo:** No es enviar un enlace de pago inmediato, sino agendar reuniones (Demos) para entender sus necesidades y mostrarles el valor de los datos históricos.

### 2. Diversificar Métodos de Pago y Cotización
Pagar $990.000 COP con tarjeta de crédito corporativa no es viable para la mayoría de instituciones educativas en Colombia debido a controles de tesorería.
- **Acción:** En la página `pricing.html`, agrega un botón secundario llamado **"Solicitar Cotización Anual"** o **"Hablar con Ventas"**.
- **Mecánica:** Este botón debe abrir WhatsApp o un formulario para recolectar el NIT y emitir una Pre-Factura o Cuenta de Cobro, habilitando pago por transferencia interbancaria o consignación corporativa.

### 3. Implementar "Soft Paywalls" (Muros de pago psicológicos)
Actualmente, el dashboard "Comunidad" entrega mucho valor sin "antojar" sobre lo que falta.
- **Acción:** Integrar el modal existente (`id="upgradeModal"`) dentro del dashboard gratuito.
- **Mecánica:** En lugar de ocultar las funciones Pro, **muéstralas deshabilitadas o con un candado**. Si el usuario hace clic en "Exportar CSV" o "Ver Histórico 1996", lanza el modal explicando el beneficio del plan Pro Estratégico.

### 4. Automatización de Correos (Drip Campaign)
Educar al usuario automáticamente sobre el valor de los datos que se está perdiendo.
- **Día 1:** Correo de bienvenida y confirmación de que encontraron a su colegio.
- **Día 4:** Correo educativo mostrando el valor de los *Z-Scores* y comparativas históricas (con capturas de pantalla de la cuenta Pro).
- **Día 7:** Último correo ofreciendo agendar una demostración de 15 minutos gratuita (Llamado a la acción principal).

### 5. Periodo de Prueba Premium (Free Trial) o Garantías
Para tickets altos anuales en productos nuevos, el riesgo percibido es muy alto.
- **Free Trial de 7 días:** Asignar temporalmente el rango Pro a los usuarios nuevos. Al degradarlos a cuenta "Comunidad" al octavo día, el sesgo psicológico de aversión a la pérdida actuará como motivador de compra.
- **Garantías de Retorno:** Asegurar "Devolución en 15 días si los datos no ayudan a tu estrategia académica" reduce el miedo del colegio al aprobar el presupuesto.

---

*Documento generado luego de análisis de tráfico web y arquitectura de conversión el 25 de Marzo de 2026.*
