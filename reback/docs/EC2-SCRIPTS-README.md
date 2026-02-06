# Scripts de Gestión EC2 - Guía de Uso

## 📁 Scripts Creados

### 1. `ec2-start.bat` - Iniciar Instancia
Inicia la instancia EC2 cuando necesites procesar datos con dbt.

**Uso:**
```cmd
.\ec2-start.bat
```

**Qué hace:**
- Inicia la instancia EC2
- Espera a que esté corriendo
- Muestra la IP pública
- Muestra comando SSH para conectar

**Tiempo:** ~2 minutos

---

### 2. `ec2-stop.bat` - Detener Instancia ⚠️ IMPORTANTE
**SIEMPRE ejecuta esto cuando termines** para ahorrar dinero.

**Uso:**
```cmd
.\ec2-stop.bat
```

**Qué hace:**
- Pide confirmación
- Detiene la instancia
- Espera a que se detenga completamente
- Muestra ahorro estimado

**Ahorro:** $363/mes (vs siempre prendida)

---

### 3. `ec2-status.bat` - Ver Estado
Verifica si la instancia está corriendo o detenida.

**Uso:**
```cmd
.\ec2-status.bat
```

**Qué muestra:**
- Estado actual (running/stopped)
- IP pública (si está corriendo)
- Costo actual
- Comando SSH (si está corriendo)

---

## ⚙️ Configuración Inicial

**IMPORTANTE:** Antes de usar los scripts, debes configurar el Instance ID:

1. Ve a la consola AWS EC2: https://console.aws.amazon.com/ec2/
2. Busca la instancia "dbt-processing"
3. Copia el **Instance ID** (ejemplo: `i-0123456789abcdef0`)
4. Edita los 3 archivos `.bat` y reemplaza:
   ```batch
   set INSTANCE_ID=i-XXXXXXXXXXXXXXXXX
   ```
   Por:
   ```batch
   set INSTANCE_ID=i-0123456789abcdef0  REM Tu Instance ID real
   ```

---

## 🔄 Workflow Típico

### Cuando Necesites Procesar Datos:

```cmd
# 1. Iniciar instancia
.\ec2-start.bat

# 2. Conectar via SSH (usa la IP que muestra el script)
ssh -i C:\Proyectos\key\dbt-processing.pem ubuntu@<IP>

# 3. Trabajar en EC2...
cd /home/ubuntu/dbt/icfes_processing
source /home/ubuntu/venv_dbt/bin/activate
dbt run -m fact_icfes_analytics --full-refresh

# 4. Cuando termines, DETENER la instancia
.\ec2-stop.bat
```

---

## 💰 Costos

| Estado | Costo/mes | Cuándo |
|--------|-----------|--------|
| **Running** | $363/mes | Solo cuando procesas datos |
| **Stopped** | $10/mes | El resto del tiempo |

**Ejemplo de uso mensual:**
- Procesamiento: 3 horas/mes = $1.50
- Almacenamiento: 30 días = $10
- **Total: $11.50/mes** (vs $363/mes siempre prendida)

**Ahorro: 97%** 💰

---

## ⚠️ Recordatorios Importantes

1. **SIEMPRE detén la instancia** cuando termines
2. Verifica el estado antes de irte: `.\ec2-status.bat`
3. Si olvidas detenerla: **$12/día de costo extra**
4. Configura alarmas en CloudWatch para recordarte

---

## 🔧 Troubleshooting

### Error: "UnauthorizedOperation"
**Causa:** El usuario AWS no tiene permisos de EC2  
**Solución:** Usa la consola web o agrega permisos `AmazonEC2FullAccess`

### La instancia no inicia
**Causa:** Puede estar en otro estado  
**Solución:** 
```cmd
.\ec2-status.bat  # Ver estado actual
```
Espera a que termine de detenerse/iniciarse

### No puedo conectar via SSH
**Causa:** La instancia aún está iniciando  
**Solución:** Espera 1-2 minutos después de que muestre "running"

---

## 📝 Notas

- Los scripts usan AWS CLI, asegúrate de tenerlo configurado
- La instancia conserva todos los datos cuando está detenida
- Solo pagas por almacenamiento EBS cuando está detenida
- Puedes iniciar/detener cuantas veces quieras sin costo extra
