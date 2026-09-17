# Verificacion previa a cerrar una tarea (docs/testing.md, seccion 4).
#
# Uso desde backend/:
#   .\scripts\verificar.ps1            formato, lint y pruebas
#   .\scripts\verificar.ps1 -ConBase   agrega migraciones e integracion con PostgreSQL
#
# -ConBase NO usa la base de /.env: las pruebas postgres escriben filas unicas
# (configuracion, supervisores, Speech original) que se usan al trabajar en la app.
# Corre contra la base de pruebas auto_cusco_test (otra con $env:AUTO_CUSCO_DB_PRUEBAS,
# siempre con sufijo _test), la migra y despues comprueba e integra. La base se crea
# una vez con backend/scripts/init_db.sql (docs/setup.md, seccion 6).

param([switch]$ConBase)

$fallos = @()

function Invoke-Paso {
    param([string]$Nombre, [scriptblock]$Accion)
    Write-Host ""
    Write-Host "== $Nombre" -ForegroundColor Cyan
    & $Accion
    if ($LASTEXITCODE -ne 0) {
        $script:fallos += $Nombre
        Write-Host "   $Nombre FALLO" -ForegroundColor Red
    }
}

Invoke-Paso "formato" { uv run ruff format --check app tests migrations }
Invoke-Paso "lint" { uv run ruff check . }
Invoke-Paso "pruebas" { uv run pytest -q }

if ($ConBase) {
    $basePruebas = if ($env:AUTO_CUSCO_DB_PRUEBAS) { $env:AUTO_CUSCO_DB_PRUEBAS } else { "auto_cusco_test" }
    $dbNameAnterior = $env:DB_NAME
    $env:DB_NAME = $basePruebas
    $env:AUTO_CUSCO_DB_TESTS = "1"
    Write-Host ""
    Write-Host "Base de pruebas: $basePruebas" -ForegroundColor Cyan
    try {
        Invoke-Paso "migraciones (aplicar)" { uv run alembic upgrade head }
        if ($fallos -contains "migraciones (aplicar)") {
            Write-Host "   Existe la base ${basePruebas}? Se crea con init_db.sql (docs/setup.md, seccion 6)" -ForegroundColor Yellow
        }
        else {
            Invoke-Paso "migraciones" { uv run alembic check }
            Invoke-Paso "integracion" { uv run pytest -m postgres -q }
        }
    }
    finally {
        Remove-Item Env:AUTO_CUSCO_DB_TESTS -ErrorAction SilentlyContinue
        if ($null -eq $dbNameAnterior) { Remove-Item Env:DB_NAME -ErrorAction SilentlyContinue }
        else { $env:DB_NAME = $dbNameAnterior }
    }
}
else {
    Write-Host ""
    Write-Host "Saltados: migraciones e integracion (usa -ConBase si tocaste persistencia)" -ForegroundColor Yellow
}

Write-Host ""
if ($fallos.Count -gt 0) {
    Write-Host ("FALTA CORREGIR: " + ($fallos -join ", ")) -ForegroundColor Red
    exit 1
}
Write-Host "Todo en verde" -ForegroundColor Green
