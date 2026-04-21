param(
    [Parameter(Mandatory = $true)]
    [string]$ComputerIp,

    [string]$DeviceId = "",

    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$AppDir = Join-Path $PSScriptRoot "..\helmet_app"
$ApiBaseUrl = "http://${ComputerIp}:${Port}"

Push-Location $AppDir
try {
    flutter pub get

    if ([string]::IsNullOrWhiteSpace($DeviceId)) {
        flutter run --dart-define="API_BASE_URL=$ApiBaseUrl"
    }
    else {
        flutter run -d $DeviceId --dart-define="API_BASE_URL=$ApiBaseUrl"
    }
}
finally {
    Pop-Location
}
