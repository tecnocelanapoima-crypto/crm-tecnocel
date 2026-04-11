@echo off
color 0A
title Tecnocel CRM - Servidor

echo.
echo  ====================================================
echo    TECNOCEL CRM - Iniciando servidor...
echo  ====================================================
echo.

:: Ir al directorio del proyecto
cd /d C:\Users\TECNOCEL\tecnocel-crm

:: Activar entorno virtual
call venv\Scripts\activate

:: Verificar que Flask este instalado
python -c "import flask" 2>nul
if errorlevel 1 (
    color 0C
    echo  [ERROR] Flask no encontrado. Instalando dependencias...
    pip install -r requirements.txt
)

:: Activar modo DEBUG
set FLASK_DEBUG=1
set FLASK_ENV=development

:: Abrir puerto 5000 en el Firewall de Windows (permite acceso desde celular)
netsh advfirewall firewall show rule name="Tecnocel CRM Puerto 5000" >nul 2>&1
if errorlevel 1 (
    echo  [FW] Abriendo puerto 5000 en el Firewall...
    netsh advfirewall firewall add rule name="Tecnocel CRM Puerto 5000" ^
        dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
    if errorlevel 1 (
        echo  [AVISO] No se pudo abrir el Firewall automaticamente.
        echo  [AVISO] Si el celular no conecta, ejecuta este .bat como Administrador.
    ) else (
        echo  [OK] Puerto 5000 habilitado en el Firewall
    )
) else (
    echo  [OK] Puerto 5000 ya habilitado en el Firewall
)

echo  [OK] Entorno virtual activado
echo  [OK] Modo DEBUG activado
echo.

:: Obtener IP local con Python
for /f "delims=" %%I in ('python -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));print(s.getsockname()[0]);s.close()" 2^>nul') do set LOCAL_IP=%%I
if "%LOCAL_IP%"=="" set LOCAL_IP=desconocida

echo  ====================================================
echo.
echo    PC  (local):   http://localhost:5000
echo    Celular (LAN): http://%LOCAL_IP%:5000
echo    Codigo QR:     http://%LOCAL_IP%:5000/qr
echo.
echo    Conecta el celular al mismo WiFi y abre la URL
echo    o escanea el QR en /qr desde el navegador.
echo.
echo  ====================================================
echo   Para DETENER el servidor: Ctrl + C
echo  ====================================================
echo.

:: Abrir navegador en PC automaticamente
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Arrancar Flask
python app.py

:: Si el servidor se detiene con error
echo.
color 0C
echo  [!] El servidor se detuvo. Revisa el error arriba.
echo.
pause
