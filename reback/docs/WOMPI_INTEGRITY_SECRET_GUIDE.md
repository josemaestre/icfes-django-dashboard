# 🔍 Guía para Obtener el WOMPI_INTEGRITY_SECRET Correcto

## El Problema

El error "Firma Inválida" significa que el `WOMPI_INTEGRITY_SECRET` en tu `.env` **NO coincide** con el del dashboard de Wompi.

---

## ✅ Solución: Obtener la Clave Correcta

### Paso 1: Ir al Dashboard de Wompi

1. Abre: **https://comercios.wompi.co/**
2. Inicia sesión con tu cuenta
3. Ve a: **Desarrolladores** → **API Keys**
4. Asegúrate de estar en modo: **Pruebas (Test)**

### Paso 2: Identificar el Integrity Secret

En el dashboard verás algo como:

```
┌─────────────────────────────────────────────┐
│ Claves de Prueba (Test)                     │
├─────────────────────────────────────────────┤
│                                             │
│ Public Key:                                 │
│ pub_test_XXXXXXXXXXXXXXXXXXXXXXXXXX         │
│                                             │
│ Private Key:                                │
│ prv_test_XXXXXXXXXXXXXXXXXXXXXXXXXX         │
│                                             │
│ Events Secret: (para webhooks)              │
│ test_events_XXXXXXXXXXXXXXXXXXXXXXXXXX      │
│                                             │
│ Integrity Secret: (para widget)             │
│ test_integrity_XXXXXXXXXXXXXXXXXXXXXXXXXX   │  ← ESTA ES LA QUE NECESITAS
│                                             │
└─────────────────────────────────────────────┘
```

**IMPORTANTE:** Busca específicamente la que dice **"Integrity Secret"** o **"Llave de integridad"**

### Paso 3: Copiar EXACTAMENTE

1. Click en el botón de copiar (📋) junto al Integrity Secret
2. O selecciona el texto completo y copia (Ctrl+C)
3. **IMPORTANTE:** Asegúrate de copiar TODO el valor, sin espacios extra

### Paso 4: Actualizar `.env`

Abre: `c:\proyectos\www\reback\.env`

Reemplaza esta línea:
```bash
WOMPI_INTEGRITY_SECRET=test_integrity_NG4TcoV179zbNjzEnnXnHcuYJdEhC3Qc
```

Con el valor que copiaste del dashboard:
```bash
WOMPI_INTEGRITY_SECRET=test_integrity_TU_VALOR_REAL_AQUI
```

### Paso 5: Reiniciar Servidor

1. Detén el servidor (Ctrl+C)
2. Inicia de nuevo:
   ```bash
   python manage.py runserver --noreload
   ```

### Paso 6: Probar de Nuevo

1. Ir a: `http://localhost:8000/payments/wompi/checkout/?plan=premium`
2. El widget debe cargar **sin** error de "Firma Inválida"

---

## 🔍 Verificación Adicional

Si el problema persiste, verifica que:

1. **No hay espacios extra:**
   - ❌ `WOMPI_INTEGRITY_SECRET= test_integrity_...` (espacio después de =)
   - ✅ `WOMPI_INTEGRITY_SECRET=test_integrity_...` (sin espacio)

2. **El valor es completo:**
   - Debe empezar con: `test_integrity_`
   - Debe tener ~50 caracteres en total

3. **Estás en modo Test:**
   - En el dashboard de Wompi, asegúrate de estar en "Pruebas (Test)"
   - NO uses las claves de producción (prod_)

---

## 🆘 Si Sigue Fallando

Si después de copiar el Integrity Secret correcto sigue fallando:

1. **Verifica que sea la clave correcta:**
   - En el dashboard, debe decir específicamente "Integrity Secret" o "Llave de integridad"
   - NO uses el "Events Secret" (esa es para webhooks)

2. **Contacta a Wompi:**
   - Es posible que tu cuenta tenga un problema
   - Soporte: soporte@wompi.co

3. **Crea una nueva cuenta de prueba:**
   - A veces las cuentas de prueba tienen problemas
   - Crea una nueva y obtén claves frescas

---

## 📝 Checklist

- [ ] Ir a Dashboard Wompi
- [ ] Modo: Pruebas (Test)
- [ ] Copiar "Integrity Secret" completo
- [ ] Actualizar `.env`
- [ ] Verificar que no hay espacios extra
- [ ] Reiniciar servidor
- [ ] Probar checkout
- [ ] Widget carga sin error

---

**Tiempo estimado:** 5 minutos
