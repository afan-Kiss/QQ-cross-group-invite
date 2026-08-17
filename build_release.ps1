# Thin Wails release entrypoint (repository root).
# Delegates to the single official build script under cross_group_wails/.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$WailsRelease = Join-Path $Root "cross_group_wails\build_release.ps1"

if (-not (Test-Path -LiteralPath $WailsRelease)) {
    Write-Error "Official Wails release script not found: $WailsRelease"
    exit 1
}

Write-Host "==> Delegating to cross_group_wails\build_release.ps1" -ForegroundColor Cyan
& $WailsRelease @args
exit $LASTEXITCODE
