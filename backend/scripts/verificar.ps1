# Verificacion previa a cerrar una tarea (docs/testing.md, seccion 4).
#
# Uso desde backend/:
#   .\scripts\verificar.ps1            formato, lint y pruebas
#   .\scripts\verificar.ps1 -ConBase   agrega migraciones e integracion con PostgreSQL
#
# -ConBase necesita la base de /.env creada y migrada (uv run alembic upgrade head).

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
    Invoke-Paso "migraciones" { uv run alembic check }
    $env:AUTO_CUSCO_DB_TESTS = "1"
    try {
        Invoke-Paso "integracion" { uv run pytest -m postgres -q }
    }
    finally {
        Remove-Item Env:AUTO_CUSCO_DB_TESTS -ErrorAction SilentlyContinue
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
