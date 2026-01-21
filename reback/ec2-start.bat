@echo off
REM Script para INICIAR la instancia EC2 de dbt processing
REM Uso: ec2-start.bat

echo ========================================
echo Iniciando instancia EC2 dbt-processing
echo ========================================
echo.

REM TODO: Reemplaza con tu Instance ID real
REM Lo puedes obtener de la consola AWS EC2
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

echo Iniciando instancia...
aws ec2 start-instances --instance-ids %INSTANCE_ID%

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ Comando enviado exitosamente
    echo.
    echo Esperando a que la instancia esté corriendo...
    aws ec2 wait instance-running --instance-ids %INSTANCE_ID%
    
    echo.
    echo ✓ Instancia corriendo!
    echo.
    echo Obteniendo IP pública...
    for /f %%i in ('aws ec2 describe-instances --instance-ids %INSTANCE_ID% --query "Reservations[0].Instances[0].PublicIpAddress" --output text') do set PUBLIC_IP=%%i
    
    echo.
    echo ========================================
    echo ✓ Instancia lista para usar
    echo ========================================
    echo IP pública: %PUBLIC_IP%
    echo.
    echo Conectar via SSH:
    echo ssh -i C:\Proyectos\key\dbt-processing.pem ubuntu@%PUBLIC_IP%
    echo.
) else (
    echo.
    echo ✗ Error al iniciar la instancia
    echo Código de error: %ERRORLEVEL%
)

pause
