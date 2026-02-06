# Configuración de la API de Anthropic Claude para Recomendaciones IA

## Paso 1: Obtener API Key de Anthropic

1. Ve a https://console.anthropic.com/
2. Crea una cuenta o inicia sesión
3. Navega a "API Keys"
4. Crea una nueva API key
5. Copia la clave (empieza con `sk-ant-...`)

## Paso 2: Instalar la librería de Anthropic

```bash
uv pip install anthropic
```

✅ **Ya completado** - La librería ya está instalada en tu proyecto.

## Paso 3: Configurar la API Key

✅ **Ya completado** - La configuración ya está lista en `config/settings/local.py`

Tu variable de entorno de Windows `ANTHROPIC_API_KEY` ya está configurada y Django la leerá automáticamente.

Para verificar que está configurada, abre PowerShell y ejecuta:
```powershell
echo $env:ANTHROPIC_API_KEY
```

Deberías ver tu clave API (sk-ant-...).

## Paso 4: Reiniciar el servidor Django

Si el servidor está corriendo, reinícialo para que cargue la nueva configuración:

```bash
# Detén el servidor (Ctrl+C) y luego:
python manage.py runserver
```

## Uso

Una vez configurado (ya lo está ✅), ve a:

1. http://localhost:8000/icfes/colegio/
2. Busca cualquier colegio (ej: "GIMNASIO")
3. Haz clic en un colegio de los resultados
4. Desplázate hasta la sección "Análisis y Recomendaciones IA"
5. Haz clic en el botón "Generar Análisis"

El sistema enviará los datos históricos del colegio a Claude y recibirás:
- Evaluación general del colegio
- Fortalezas identificadas
- Debilidades identificadas
- Estrategias específicas para aumentar 5 puntos
- Recomendaciones por materia
- Plan de acción prioritario

## Costos

Claude cobra por tokens utilizados. Cada análisis usa aproximadamente:
- Input: ~2,000-3,000 tokens
- Output: ~1,500-2,000 tokens

Con el modelo `claude-3-5-sonnet-20241022`:
- Costo aproximado: $0.01 - $0.02 USD por análisis

## Troubleshooting

### Error: "API de IA no configurada"
- Verifica que `ANTHROPIC_API_KEY` esté configurada en `settings.py`
- Reinicia el servidor Django

### Error: "Authentication error"
- Verifica que la API key sea correcta
- Asegúrate de que la cuenta de Anthropic tenga créditos disponibles

### Error: "Rate limit exceeded"
- Espera unos minutos antes de intentar de nuevo
- Considera actualizar tu plan en Anthropic si necesitas más capacidad
