@echo off
color 0A
title Tecnocel CRM - Servidor con Tunel (Datos Moviles)

echo.
echo  ====================================================
echo    TECNOCEL CRM - Modo Datos Moviles
echo  ====================================================
echo.

:: Ir al directorio del proyecto
cd /d C:\Users\TECNOCEL\tecnocel-crm

:: Activar entorno virtual
call venv\Scripts\activate

:: Verificar Flask
python -c "import flask" 2>nul
if errorlevel 1 (
    echo  Instalando dependencias...
    pip install -r requirements.txt
)

:: Abrir puerto 5000 en el Firewall
netsh advfirewall firewall show rule name="Tecnocel CRM Puerto 5000" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="Tecnocel CRM Puerto 5000" ^
        dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
)

:: Iniciar Flask en segundo plano (modo sin debug para produccion)
echo  [1/3] Iniciando servidor Flask...
set FLASK_DEBUG=0
start "Tecnocel CRM Flask" /min python app.py

:: Esperar a que Flask inicie
timeout /t 3 /nobreak >nul

:: Abrir navegador en el PC
echo  [2/3] Abriendo navegador...
start http://localhost:5000

:: Iniciar tunel (cloudflared o ngrok)
echo  [3/3] Iniciando tunel para datos moviles...
echo.
echo  Una vez aparezca la URL publica, abrela en el celular
echo  o escanea el QR desde http://localhost:5000/qr
echo.
echo  ====================================================
echo   Presiona Ctrl+C para detener el tunel
echo  ====================================================
echo.

python tunnel_manager.py

:: Al salir del tunel
echo.
color 0C
echo  [!] Tunel detenido. El servidor CRM puede seguir activo.
pause
