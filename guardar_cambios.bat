@echo off
color 0B
title Tecnocel CRM - Guardar cambios en GitHub

echo.
echo  ============================================
echo    TECNOCEL CRM - Guardando en GitHub...
echo  ============================================
echo.

:: Ir al directorio del proyecto
cd /d C:\Users\TECNOCEL\tecnocel-crm

:: Mostrar archivos modificados
echo  Archivos modificados:
git status --short
echo.

:: Pedir mensaje del commit
set /p MENSAJE="  Describe el cambio (Enter para mensaje automatico): "

:: Si no escribio nada, usar mensaje automatico con fecha
if "%MENSAJE%"=="" (
    for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set FECHA=%%c-%%b-%%a
    for /f "tokens=1-2 delims=: " %%a in ("%time%") do set HORA=%%a:%%b
    set MENSAJE=actualizacion %FECHA% %HORA%
)

:: Hacer commit y push
git add -A
git commit -m "%MENSAJE%"
git push

echo.
color 0A
echo  [OK] Cambios guardados en GitHub correctamente!
echo.
pause
