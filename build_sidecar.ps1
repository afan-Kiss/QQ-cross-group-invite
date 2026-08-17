# Build Python sidecar (framework-neutral).
# Depends only on Python + PyInstaller. Does not create any UI framework directories.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> Building cross-group-service.exe with PyInstaller"
python -m PyInstaller --noconfirm --clean cross_group_service.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$Built = Join-Path $Root "dist\cross-group-service.exe"
if (-not (Test-Path -LiteralPath $Built)) {
    throw "Build output not found: $Built"
}

Write-Host "==> Sidecar ready: $Built"
return @{
    SidecarPath = $Built
}
