@echo off
title Tecnocel CRM — Informe Semanal
color 1F
cls

echo =====================================================
echo   TECNOCEL CRM — GENERADOR DE INFORME SEMANAL
echo =====================================================
echo.
echo   Generando informe de la semana anterior...
echo.

cd /d "C:\Users\TECNOCEL\tecnocel-crm"
call venv\Scripts\activate.bat
python informe_semanal.py

if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo.
    echo   ERROR: No se pudo generar el informe.
    echo   Revisa que el CRM este instalado correctamente.
    echo.
    pause
    exit /b 1
)

echo.
echo   El informe fue guardado en:
echo   C:\Users\TECNOCEL\tecnocel-crm\informes\
echo.
echo   La carpeta se abrira automaticamente...
echo.
pause
