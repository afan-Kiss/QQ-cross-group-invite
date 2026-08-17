# Build production release for QQ Cross Group Invite (Wails)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$MyqqHttp = Split-Path -Parent $Root
$Failed = $false

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Step failed: $Name (exit $LASTEXITCODE)"
    }
}

function Require-Cmd([string]$Cmd, [string]$Hint) {
    $found = Get-Command $Cmd -ErrorAction SilentlyContinue
    if (-not $found) { throw "Missing dependency: $Cmd. $Hint" }
    Write-Host "  OK $Cmd = $($found.Source)"
}

try {
    Set-Location $Root

    Step "Check Python" { Require-Cmd python "Install Python 3.10+" }
    Step "Check PyInstaller" {
        python -c "import PyInstaller; print(PyInstaller.__version__)"
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller not installed. pip install pyinstaller" }
    }
    Step "Check Go" { Require-Cmd go "Install Go 1.21+" }
    Step "Check Wails" { Require-Cmd wails "go install github.com/wailsapp/wails/v2/cmd/wails@latest" }
    Step "Check Node" { Require-Cmd npm "Install Node.js 20+" }

    Step "npm ci" {
        Set-Location "$Root\frontend"
        npm ci
        Set-Location $Root
    }

    Step "TypeScript check + frontend build" {
        Set-Location "$Root\frontend"
        npm run build
        Set-Location $Root
    }

    Step "Mojibake scan" {
        Set-Location $MyqqHttp
        python -c @"
from pathlib import Path
root = Path('cross_group_wails/frontend/src')
bad = []
for p in list(root.rglob('*.ts')) + list(root.rglob('*.tsx')) + list(root.rglob('*.css')):
    data = p.read_bytes()
    if b'\xef\xbf\xbd' in data:
        bad.append(str(p))
if bad:
    print('MOJIBAKE FILES:')
    for x in bad: print(x)
    raise SystemExit(1)
print('mojibake scan OK')
"@
        Set-Location $Root
    }

    Step "Python tests" {
        Set-Location $MyqqHttp
        python -m pytest tests -q
        Set-Location $Root
    }

    Step "Go tests" {
        go test ./...
    }

    Step "Build sidecar" {
        $sidecarResult = & "$MyqqHttp\build_sidecar.ps1"
        $sidecarPath = "$MyqqHttp\dist\cross-group-service.exe"
        if ($sidecarResult -is [hashtable] -and $sidecarResult.SidecarPath) {
            $sidecarPath = [string]$sidecarResult.SidecarPath
        }
        if (-not (Test-Path -LiteralPath $sidecarPath)) {
            throw "sidecar missing after build: $sidecarPath"
        }
        New-Item -ItemType Directory -Force -Path "$Root\bin" | Out-Null
        Copy-Item -Force $sidecarPath "$Root\bin\cross-group-service.exe"
    }

    Step "Sidecar health smoke" {
        Set-Location $Root
        $sidecar = "$Root\bin\cross-group-service.exe"
        $proc = Start-Process -FilePath $sidecar -ArgumentList "--no-browser","--session-id","smoke-test" -PassThru -WindowStyle Hidden
        $ok = $false
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 400
            try {
                $h = Invoke-RestMethod -Uri "http://127.0.0.1:17888/health" -TimeoutSec 2
                if ($h.service -eq "cross-group-invite" -and $h.ok -eq $true) { $ok = $true; break }
            } catch {}
        }
        try { Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:17888/shutdown" -Headers @{"X-App-Session"="smoke-test"} -ContentType "application/json" -Body "{}" -TimeoutSec 3 | Out-Null } catch {}
        Start-Sleep -Milliseconds 500
        if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
        if (-not $ok) { throw "sidecar health smoke failed" }
        Write-Host "  sidecar smoke OK"
        Set-Location $Root
    }

    Step "wails build" {
        Set-Location $Root
        wails build
    }

    Step "Copy sidecar into release dir" {
        $outDir = "$Root\build\bin"
        if (-not (Test-Path $outDir)) { throw "build/bin missing" }
        Copy-Item -Force "$MyqqHttp\dist\cross-group-service.exe" "$outDir\cross-group-service.exe"
        Copy-Item -Force "$MyqqHttp\VERSION" "$outDir\VERSION" -ErrorAction SilentlyContinue
        # keep only runtime essentials
        Get-ChildItem $outDir | ForEach-Object {
            Write-Host ("  " + $_.Name + " " + $_.Length)
        }
    }

    Step "Release hashes" {
        $outDir = "$Root\build\bin"
        $exe = Get-ChildItem $outDir -Filter "*.exe" | Where-Object { $_.Name -like "*跨群*" -or $_.Name -like "*QQ*" -or $_.Name -eq "QQ跨群邀请工具.exe" } | Select-Object -First 1
        if (-not $exe) { $exe = Get-ChildItem $outDir -Filter "*.exe" | Where-Object { $_.Name -ne "cross-group-service.exe" } | Select-Object -First 1 }
        $sidecar = Get-Item "$outDir\cross-group-service.exe"
        foreach ($f in @($exe, $sidecar)) {
            if (-not $f) { continue }
            $hash = (Get-FileHash -Algorithm SHA256 $f.FullName).Hash
            Write-Host ("  " + $f.Name)
            Write-Host ("    size=" + $f.Length)
            Write-Host ("    sha256=" + $hash)
        }
    }

    Write-Host ""
    Write-Host "RELEASE BUILD OK" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "RELEASE BUILD FAILED: $_" -ForegroundColor Red
    exit 1
}
