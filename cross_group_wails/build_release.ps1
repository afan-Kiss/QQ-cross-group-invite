# Build Wails app with sidecar
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$MyqqHttp = Split-Path -Parent $Root

Write-Host "==> Building sidecar"
& "$MyqqHttp\build_sidecar.ps1" -ErrorAction Stop | Out-Null
if (-not (Test-Path "$MyqqHttp\dist\cross-group-service.exe")) {
    python -m PyInstaller --noconfirm --clean "$MyqqHttp\cross_group_service.spec"
}

$sidecar = "$MyqqHttp\dist\cross-group-service.exe"
New-Item -ItemType Directory -Force -Path "$Root\bin" | Out-Null
Copy-Item -Force $sidecar "$Root\bin\cross-group-service.exe"

Write-Host "==> wails build"
Set-Location $Root
wails build
if ($LASTEXITCODE -ne 0) { throw "wails build failed" }

$outDir = "$Root\build\bin"
Copy-Item -Force $sidecar "$outDir\cross-group-service.exe"

Write-Host "==> Done"
Get-ChildItem $outDir | Format-Table Name, Length
