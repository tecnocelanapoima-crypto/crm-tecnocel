@echo off
color 0A
title Tecnocel CRM - Servidor

echo.
echo  ============================================
echo    TECNOCEL CRM - Iniciando servidor...
echo  ============================================
echo.

:: Ir al directorio del proyecto
cd /d C:\Users\TECNOCEL\tecnocel-crm

:: Activar entorno virtual
call venv\Scripts\activate

:: Verificar que Flask esté instalado
python -c "import flask" 2>nul
if errorlevel 1 (
    color 0C
    echo  [ERROR] Flask no encontrado. Instalando dependencias...
    pip install -r requirements.txt
)

:: Activar modo DEBUG para ver errores en tiempo real
set FLASK_DEBUG=1
set FLASK_ENV=development

echo  [OK] Entorno virtual activado
echo  [OK] Modo DEBUG activado
echo.
echo  Abriendo navegador en http://localhost:5000
echo.
echo  ============================================
echo   ERRORES apareceran aqui abajo en rojo
echo   Para DETENER el servidor: Ctrl + C
echo  ============================================
echo.

:: Abrir el navegador automaticamente despues de 2 segundos
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Arrancar el servidor Flask
python app.py

:: Si el servidor se detiene con error, mostrar mensaje
echo.
color 0C
echo  [!] El servidor se detuvo. Revisa el error arriba.
echo.
pause
