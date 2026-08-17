# Build Python sidecar for Tauri bundle
param(
    [string]$TargetTriple = ""
)

$ErrorActionPreference = "Stop"

function Get-RustTargetTriple {
    param([string]$ExplicitTarget)

    if ($ExplicitTarget) {
        return $ExplicitTarget
    }

    $hostTuple = & rustc --print host-tuple 2>$null
    if ($LASTEXITCODE -eq 0 -and $hostTuple) {
        return $hostTuple.Trim()
    }

    $verbose = & rustc -Vv 2>$null
    if ($LASTEXITCODE -eq 0 -and $verbose) {
        $match = [regex]::Match(($verbose -join "`n"), "(?m)^host:\s+(\S+)")
        if ($match.Success) {
            return $match.Groups[1].Value.Trim()
        }
    }

    throw "Unable to determine Rust target triple. Install Rust and ensure rustc is on PATH."
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$resolvedTarget = Get-RustTargetTriple -ExplicitTarget $TargetTriple
Write-Host "==> Target triple: $resolvedTarget"

Write-Host "==> Building cross-group-service.exe with PyInstaller"
python -m PyInstaller --noconfirm --clean cross_group_service.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$Built = Join-Path $Root "dist\cross-group-service.exe"
if (-not (Test-Path $Built)) {
    throw "Build output not found: $Built"
}

$TauriBin = Join-Path $Root "cross_group_tauri\src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $TauriBin | Out-Null
$Target = Join-Path $TauriBin "cross-group-service-$resolvedTarget.exe"
Copy-Item -Force $Built $Target
Write-Host "==> Copied sidecar to $Target"

return @{
    TargetTriple = $resolvedTarget
    SidecarPath  = $Target
}
