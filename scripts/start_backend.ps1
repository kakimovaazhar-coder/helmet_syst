param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$BackendDir = Join-Path $PSScriptRoot "..\backend"

Push-Location $BackendDir
try {
    python -m uvicorn server:app --host 0.0.0.0 --port $Port
}
finally {
    Pop-Location
}
