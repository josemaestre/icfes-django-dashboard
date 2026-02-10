# 🧪 Guía de Testing Wompi - Paso a Paso

## ✅ Paso 1: Credenciales Verificadas

Las 4 claves de Wompi están configuradas correctamente:
- ✅ Public Key: `pub_test_4pTT3BMlL4i...`
- ✅ Private Key: `prv_test_iPOgVd2BALb...`
- ✅ Events Secret: `test_events_gBZBkM04...`
- ✅ Integrity Secret: `test_integrity_NG4Tc...`

---

## 🚀 Paso 2: Iniciar Servidor Django

```bash
python manage.py runserver
```

**Esperar a ver:**
```
Starting development server at http://127.0.0.1:8000/
```

---

## 🧪 Paso 3: Probar Checkout

### 3.1 Abrir en navegador:
```
http://localhost:8000/payments/wompi/checkout/?plan=premium
```

### 3.2 Verificar que carga:
- ✅ Widget de Wompi debe aparecer
- ✅ **NO** debe mostrar error "Firma Inválida"
- ✅ Debe mostrar el monto: $100,000 COP

---

## 💳 Paso 4: Probar Pago con Tarjeta de Prueba

### Datos de la tarjeta de prueba:
```
Número de tarjeta: 4242 4242 4242 4242
Fecha de expiración: 12/25 (cualquier fecha futura)
CVC: 123
Nombre: Tu Nombre
```

### Pasos:
1. Completar formulario con datos de prueba
2. Click en **"Pagar"**
3. Esperar confirmación

### Resultado esperado:
- ✅ Pago debe ser **APROBADO**
- ✅ Redirección a página de éxito
- ✅ Mensaje: "Pago exitoso"

---

## 🔍 Paso 5: Verificar en Django Admin

### 5.1 Ir al admin:
```
http://localhost:8000/admin/
```

### 5.2 Login con tu usuario admin

### 5.3 Verificar suscripción:
1. Click en **"Users"** → **"User subscriptions"**
2. Buscar tu usuario
3. Verificar:
   - ✅ Plan: Premium
   - ✅ Status: **active**
   - ✅ Wompi subscription ID: debe tener valor

---

## ❌ Troubleshooting

### Si aparece "Firma Inválida":
1. Verificar que `WOMPI_INTEGRITY_SECRET` en `.env` coincide EXACTAMENTE con el dashboard
2. Reiniciar servidor Django
3. Limpiar caché del navegador (Ctrl + Shift + R)

### Si no carga el widget:
1. Verificar que `WOMPI_PUBLIC_KEY` es correcta
2. Abrir consola del navegador (F12) y ver errores

### Si pago no se procesa:
1. Verificar que `WOMPI_PRIVATE_KEY` es correcta
2. Ver logs del servidor Django
3. Buscar errores de API

---

## 📊 Checklist de Testing

- [ ] Servidor Django iniciado
- [ ] Página de checkout carga sin errores
- [ ] Widget de Wompi aparece
- [ ] NO hay error "Firma Inválida"
- [ ] Formulario de pago se completa
- [ ] Pago se aprueba exitosamente
- [ ] Redirección a página de éxito
- [ ] Suscripción aparece en Admin
- [ ] Status de suscripción es "active"

---

## 🎯 Próximos Pasos (Después de Testing)

1. **Configurar en Railway:**
   - Agregar las 4 variables de Wompi
   - Probar en producción

2. **Configurar Webhook:**
   - Dashboard Wompi → Webhooks
   - URL: `https://tu-dominio.railway.app/payments/wompi/webhook/`

3. **Crear Celery Worker:**
   - Para cobros recurrentes automáticos

---

**Tiempo estimado:** 10-15 minutos
