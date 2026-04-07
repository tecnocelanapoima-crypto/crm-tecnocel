# registrar_tarea_semanal.ps1
# Registra la tarea automatica en el Programador de Tareas de Windows
# Ejecutar una sola vez como Administrador

$NombreTarea  = "TecnocelCRM_InformeSemanal"
$Descripcion  = "Genera automaticamente el informe semanal de facturacion del CRM Tecnocel cada lunes a las 8:00 AM"
$Python       = "C:\Users\TECNOCEL\tecnocel-crm\venv\Scripts\python.exe"
$Script       = "C:\Users\TECNOCEL\tecnocel-crm\informe_semanal.py"
$Directorio   = "C:\Users\TECNOCEL\tecnocel-crm"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Tecnocel CRM - Registrar Tarea Semanal" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que el Python del venv existe
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: No se encontro el Python del venv en:" -ForegroundColor Red
    Write-Host "  $Python" -ForegroundColor Red
    Write-Host "Asegurate de que el entorno virtual este creado." -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

# Verificar que el script existe
if (-not (Test-Path $Script)) {
    Write-Host "ERROR: No se encontro el script en:" -ForegroundColor Red
    Write-Host "  $Script" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

# Eliminar tarea anterior si existe
$tareaExistente = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
if ($tareaExistente) {
    Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false
    Write-Host "  Tarea anterior eliminada." -ForegroundColor Yellow
}

# Crear la accion: ejecutar python informe_semanal.py
$Accion = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$Script`"" `
    -WorkingDirectory $Directorio

# Disparador: cada lunes a las 8:00 AM
$Disparador = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday `
    -At "08:00AM"

# Configuracion: ejecutar aunque el usuario no este logueado
$Configuracion = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable

# Registrar la tarea
Register-ScheduledTask `
    -TaskName $NombreTarea `
    -Description $Descripcion `
    -Action $Accion `
    -Trigger $Disparador `
    -Settings $Configuracion `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host ""
Write-Host "  Tarea registrada exitosamente:" -ForegroundColor Green
Write-Host "  Nombre  : $NombreTarea" -ForegroundColor White
Write-Host "  Horario : Cada lunes a las 8:00 AM" -ForegroundColor White
Write-Host "  Script  : $Script" -ForegroundColor White
Write-Host ""
Write-Host "  Para verificarla: abre el Programador de Tareas de Windows" -ForegroundColor Cyan
Write-Host "  y busca '$NombreTarea'" -ForegroundColor Cyan
Write-Host ""

# Preguntar si quiere ejecutarla ahora para probar
$respuesta = Read-Host "  Ejecutar el informe AHORA para probar? (s/n)"
if ($respuesta -eq "s" -or $respuesta -eq "S") {
    Write-Host ""
    Write-Host "  Generando informe de prueba..." -ForegroundColor Yellow
    Start-ScheduledTask -TaskName $NombreTarea
    Start-Sleep -Seconds 3
    Write-Host "  Listo. Revisa la carpeta informes\ del proyecto." -ForegroundColor Green
}

Write-Host ""
Read-Host "  Presiona Enter para cerrar"
