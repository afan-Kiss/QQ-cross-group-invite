# Full release build: Python sidecar + Tauri EXE (with optional subst for Chinese paths)
param(
    [string]$TargetTriple = "",
    [switch]$SkipSubst
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param(
        [string]$Name,
        [string]$Hint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name. $Hint"
    }
}

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

    throw "Unable to determine Rust target triple."
}

function Get-FreeDriveLetter {
    foreach ($letter in @("Q", "T", "R", "S", "U", "V", "W", "X", "Y", "Z")) {
        $drive = "${letter}:"
        if (-not (Test-Path $drive)) {
            return $letter
        }
    }
    throw "No free drive letter available for subst."
}

function Remove-SubstDrive {
    param([string]$DriveLetter)

    if (-not $DriveLetter) {
        return
    }

    $drive = "${DriveLetter}:"
    if (Test-Path $drive) {
        subst $drive /d | Out-Null
        Write-Host "==> Removed subst drive $drive"
    }
}

function Read-TauriProductName {
    param([string]$TauriDir)

    $configPath = Join-Path $TauriDir "src-tauri\tauri.conf.json"
    $raw = Get-Content -Raw -Encoding UTF8 $configPath
    $match = [regex]::Match($raw, '"productName"\s*:\s*"([^"]+)"')
    if (-not $match.Success) {
        throw "Unable to read productName from $configPath"
    }
    return $match.Groups[1].Value
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TauriProject = Join-Path $Root "cross_group_tauri"
$TauriSrc = Join-Path $TauriProject "src-tauri"
$SubstDrive = $null
$WorkingTauriProject = $TauriProject

try {
    Write-Host "==> Checking toolchain"
    Assert-Command -Name "node" -Hint "Install Node.js"
    Assert-Command -Name "npm" -Hint "Install Node.js"
    Assert-Command -Name "rustc" -Hint "Install Rust stable"
    Assert-Command -Name "cargo" -Hint "Install Rust stable"
    Assert-Command -Name "python" -Hint "Install Python 3"
    python -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not available. Run: python -m pip install pyinstaller"
    }

    $env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
    rustup default stable | Out-Null
    rustup update stable | Out-Null

    $resolvedTarget = Get-RustTargetTriple -ExplicitTarget $TargetTriple
    Write-Host "==> Target triple: $resolvedTarget"

    Write-Host "==> Step 1: Build Python sidecar"
    $sidecarResult = & (Join-Path $Root "build_sidecar.ps1") -TargetTriple $resolvedTarget
    $sidecarPath = $sidecarResult.SidecarPath
    if (-not (Test-Path $sidecarPath)) {
        throw "Sidecar not found after build: $sidecarPath"
    }

    $productName = Read-TauriProductName -TauriDir $TauriProject
    $releaseExeName = "$productName.exe"

    if (-not $SkipSubst) {
        $SubstDrive = Get-FreeDriveLetter
        subst "${SubstDrive}:" $TauriProject | Out-Null
        $WorkingTauriProject = "${SubstDrive}:\"
        Write-Host "==> Using subst drive ${SubstDrive}: -> $TauriProject"
    }

    Write-Host "==> Step 2: npm install"
    Set-Location $WorkingTauriProject
    npm install
    if ($LASTEXITCODE -ne 0) {
        throw "npm install failed with exit code $LASTEXITCODE"
    }

    Write-Host "==> Step 3: npm run build"
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run build failed with exit code $LASTEXITCODE"
    }

    Write-Host "==> Step 4: cargo check"
    Set-Location (Join-Path $WorkingTauriProject "src-tauri")
    cargo check
    if ($LASTEXITCODE -ne 0) {
        throw "cargo check failed with exit code $LASTEXITCODE"
    }

    Set-Location $WorkingTauriProject

    Write-Host "==> Step 5: npm run tauri build -- --no-bundle"
    npm run tauri build -- --no-bundle
    if ($LASTEXITCODE -ne 0) {
        throw "tauri build --no-bundle failed with exit code $LASTEXITCODE"
    }

    Write-Host "==> Step 6: npm run tauri build"
    npm run tauri build
    if ($LASTEXITCODE -ne 0) {
        throw "tauri build failed with exit code $LASTEXITCODE"
    }

    $releaseExe = Join-Path $TauriSrc "target\release\$releaseExeName"
    $nsisDir = Join-Path $TauriSrc "target\release\bundle\nsis"
    $msiDir = Join-Path $TauriSrc "target\release\bundle\msi"

    if (-not (Test-Path $releaseExe)) {
        throw "Release EXE not found: $releaseExe"
    }

    Write-Host "==> Release EXE: $releaseExe"
    Write-Host "    Size: $((Get-Item $releaseExe).Length) bytes"

    if (Test-Path $nsisDir) {
        Get-ChildItem $nsisDir -Filter "*.exe" | ForEach-Object {
            Write-Host "==> NSIS: $($_.FullName) ($($_.Length) bytes)"
        }
    } else {
        Write-Host "==> NSIS bundle directory not found"
    }

    if (Test-Path $msiDir) {
        Get-ChildItem $msiDir -Filter "*.msi" | ForEach-Object {
            Write-Host "==> MSI: $($_.FullName) ($($_.Length) bytes)"
        }
    } else {
        Write-Host "==> MSI bundle directory not found"
    }
}
catch {
    Write-Error $_
    throw
}
finally {
    Remove-SubstDrive -DriveLetter $SubstDrive
}

Write-Host "==> Done"
