param(
    [Parameter(Mandatory = $true)]
    [string]$ComputerIp,

    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$YoloDir = Join-Path $PSScriptRoot "..\yolo"
$env:HELMET_SERVER_URL = "http://${ComputerIp}:${Port}"

Push-Location $YoloDir
try {
    python face_worker.py
}
finally {
    Pop-Location
}
