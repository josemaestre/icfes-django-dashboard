@echo off
REM Script para ver el ESTADO de la instancia EC2
REM Uso: ec2-status.bat

echo ========================================
echo Estado de instancia EC2 dbt-processing
echo ========================================
echo.

REM TODO: Reemplaza con tu Instance ID real
set INSTANCE_ID=i-XXXXXXXXXXXXXXXXX

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

echo Instance ID: %INSTANCE_ID%
echo.

echo Consultando estado...
echo.

for /f %%i in ('aws ec2 describe-instances --instance-ids %INSTANCE_ID% --query "Reservations[0].Instances[0].State.Name" --output text') do set STATE=%%i
for /f %%i in ('aws ec2 describe-instances --instance-ids %INSTANCE_ID% --query "Reservations[0].Instances[0].PublicIpAddress" --output text 2^>nul') do set PUBLIC_IP=%%i
for /f %%i in ('aws ec2 describe-instances --instance-ids %INSTANCE_ID% --query "Reservations[0].Instances[0].InstanceType" --output text') do set INSTANCE_TYPE=%%i

echo ========================================
echo Estado: %STATE%
echo Tipo: %INSTANCE_TYPE%
if not "%PUBLIC_IP%"=="None" (
    echo IP pública: %PUBLIC_IP%
) else (
    echo IP pública: N/A (instancia detenida)
)
echo ========================================
echo.

if "%STATE%"=="running" (
    echo ✓ Instancia CORRIENDO
    echo   Costo: $0.504/hora
    echo   SSH: ssh -i C:\Proyectos\key\dbt-processing.pem ubuntu@%PUBLIC_IP%
    echo.
    echo   Para DETENER y ahorrar: ec2-stop.bat
) else if "%STATE%"=="stopped" (
    echo ● Instancia DETENIDA
    echo   Costo: ~$10/mes (solo almacenamiento)
    echo   Ahorro: $363/mes vs siempre prendida
    echo.
    echo   Para INICIAR: ec2-start.bat
) else if "%STATE%"=="stopping" (
    echo ○ Instancia DETENIÉNDOSE...
    echo   Espera unos segundos y vuelve a consultar
) else if "%STATE%"=="pending" (
    echo ○ Instancia INICIANDO...
    echo   Espera unos segundos y vuelve a consultar
) else (
    echo ? Estado desconocido: %STATE%
)

echo.
pause
