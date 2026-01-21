@echo off
REM Script para DETENER la instancia EC2 de dbt processing
REM Uso: ec2-stop.bat
REM IMPORTANTE: Ejecutar esto después de terminar para AHORRAR DINERO

echo ========================================
echo Deteniendo instancia EC2 dbt-processing
echo ========================================
echo.
echo IMPORTANTE: Esto DETIENE la instancia para ahorrar costos
echo La instancia NO se eliminará, solo se apagará
echo Costo mientras está detenida: ~$10/mes (solo almacenamiento EBS)
echo.

REM TODO: Reemplaza con tu Instance ID real
set INSTANCE_ID=i-XXXXXXXXXXXXXXXXX

echo Instance ID: %INSTANCE_ID%
echo.

if "%INSTANCE_ID%"=="i-XXXXXXXXXXXXXXXXX" (
    echo ERROR: Debes configurar el INSTANCE_ID primero
    echo.
    echo 1. Ve a la consola AWS EC2
    echo 2. Busca la instancia "dbt-processing"
    echo 3. Copia el Instance ID (ejemplo: i-0123456789abcdef0)
    echo 4. Edita este archivo y reemplaza INSTANCE_ID
    echo.
    pause
    exit /b 1
)

set /p CONFIRM="¿Estás seguro de detener la instancia? (S/N): "
if /i not "%CONFIRM%"=="S" (
    echo.
    echo Operación cancelada
    pause
    exit /b 0
)

echo.
echo Deteniendo instancia...
aws ec2 stop-instances --instance-ids %INSTANCE_ID%

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ Comando enviado exitosamente
    echo.
    echo Esperando a que la instancia se detenga...
    aws ec2 wait instance-stopped --instance-ids %INSTANCE_ID%
    
    echo.
    echo ========================================
    echo ✓ Instancia detenida exitosamente
    echo ========================================
    echo.
    echo Ahorro estimado: $0.504/hora = $363/mes
    echo Costo mientras está detenida: ~$10/mes (solo EBS)
    echo.
    echo Para volver a iniciarla, ejecuta: ec2-start.bat
    echo.
) else (
    echo.
    echo ✗ Error al detener la instancia
    echo Código de error: %ERRORLEVEL%
)

pause
