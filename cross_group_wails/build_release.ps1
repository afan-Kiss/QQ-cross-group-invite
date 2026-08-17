# Build production release for QQ Cross Group Invite (Wails)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$MyqqHttp = Split-Path -Parent $Root
$WailsCfg = Get-Content -LiteralPath (Join-Path $Root "wails.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$MainExeName = "$($WailsCfg.outputfilename).exe"
$SidecarExeName = "cross-group-service.exe"
$ScriptExit = 1

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    # Native tools often write INFO to stderr; do not treat as terminating.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Action
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "Step failed: $Name (exit $LASTEXITCODE)"
        }
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

function Require-Cmd([string]$Cmd, [string]$Hint) {
    $found = Get-Command $Cmd -ErrorAction SilentlyContinue
    if (-not $found) { throw "Missing dependency: $Cmd. $Hint" }
    Write-Host "  OK $Cmd = $($found.Source)"
}

function Get-FreeLoopbackPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()
    return [int]$port
}

function Invoke-OwnedSidecarSmoke([string]$SidecarPath) {
    if (-not (Test-Path -LiteralPath $SidecarPath)) {
        throw "sidecar missing for smoke: $SidecarPath"
    }
    $port = Get-FreeLoopbackPort
    $session = [guid]::NewGuid().ToString()
    $base = "http://127.0.0.1:$port"
    Write-Host "  smoke port=$port (never 17888)"
    $proc = $null
    try {
        $proc = Start-Process -FilePath $SidecarPath `
            -ArgumentList @("--no-browser", "--session-id", $session, "--port", "$port") `
            -PassThru -WindowStyle Hidden
        $ok = $false
        $lastErr = ""
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 400
            try {
                $headers = @{ "X-App-Session" = $session }
                $h = Invoke-RestMethod -Uri "$base/health" -Headers $headers -TimeoutSec 2
                if (
                    $h.ok -eq $true -and
                    $h.service -eq "cross-group-invite" -and
                    $h.session_required -eq $true -and
                    $h.session_match -eq $true -and
                    [int]$h.pid -gt 0
                ) {
                    $ok = $true
                    Write-Host "  smoke health pid=$($h.pid) session_match=true"
                    break
                }
                $lastErr = "unexpected health payload"
            } catch {
                $lastErr = $_.Exception.Message
            }
        }
        if (-not $ok) { throw "sidecar health smoke failed: $lastErr" }

        try {
            Invoke-RestMethod -Method POST -Uri "$base/shutdown" `
                -Headers @{ "X-App-Session" = $session } `
                -ContentType "application/json" -Body "{}" -TimeoutSec 3 | Out-Null
        } catch {}
        Start-Sleep -Milliseconds 500
        Write-Host "  sidecar smoke OK (temp port)"
    }
    finally {
        if ($null -ne $proc) {
            $pidToKill = $proc.Id
            # Prefer process-tree kill for this PID only (PyInstaller parent/child). Never /IM.
            try {
                & taskkill.exe /PID $pidToKill /T /F 2>$null | Out-Null
            } catch {}
            try {
                if (-not $proc.HasExited) { Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue }
            } catch {}
            # Confirm temp port released (must not touch 17888).
            $deadline = [DateTime]::UtcNow.AddSeconds(5)
            while ([DateTime]::UtcNow -lt $deadline) {
                $busy = $false
                try {
                    $c = New-Object System.Net.Sockets.TcpClient
                    $c.Connect("127.0.0.1", $port)
                    $c.Close()
                    $busy = $true
                } catch { $busy = $false }
                if (-not $busy) { break }
                Start-Sleep -Milliseconds 200
            }
        }
    }
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

    Step "Clean previous build/bin" {
        $outDir = Join-Path $Root "build\bin"
        if (Test-Path -LiteralPath $outDir) {
            Remove-Item -LiteralPath $outDir -Recurse -Force
            Write-Host "  removed $outDir"
        }
    }

    Step "npm ci" {
        Set-Location "$Root\frontend"
        npm ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
        Set-Location $Root
    }

    Step "TypeScript check + frontend build" {
        Set-Location "$Root\frontend"
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
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
        if ($LASTEXITCODE -ne 0) { throw "mojibake scan failed" }
        Set-Location $Root
    }

    Step "Python tests" {
        Set-Location $MyqqHttp
        python -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
        Set-Location $Root
    }

    Step "Go tests" {
        go test ./...
        if ($LASTEXITCODE -ne 0) { throw "go test failed" }
    }

    Step "Build sidecar" {
        & "$MyqqHttp\build_sidecar.ps1"
        if ($LASTEXITCODE -ne 0) { throw "build_sidecar failed" }
        $sidecarPath = "$MyqqHttp\dist\$SidecarExeName"
        if (-not (Test-Path -LiteralPath $sidecarPath)) {
            throw "sidecar missing after build: $sidecarPath"
        }
        New-Item -ItemType Directory -Force -Path "$Root\bin" | Out-Null
        Copy-Item -Force $sidecarPath "$Root\bin\$SidecarExeName"
    }

    Step "Sidecar health smoke (temp port)" {
        Invoke-OwnedSidecarSmoke "$Root\bin\$SidecarExeName"
    }

    Step "wails build" {
        Set-Location $Root
        wails build
        if ($LASTEXITCODE -ne 0) { throw "wails build failed" }
    }

    Step "Copy sidecar + verify release contents" {
        $outDir = "$Root\build\bin"
        if (-not (Test-Path -LiteralPath $outDir)) { throw "build/bin missing" }
        Copy-Item -Force "$MyqqHttp\dist\$SidecarExeName" "$outDir\$SidecarExeName"
        $versionSrc = Join-Path $MyqqHttp "VERSION"
        if (-not (Test-Path -LiteralPath $versionSrc)) {
            throw "VERSION file missing at repo root"
        }
        Copy-Item -Force $versionSrc "$outDir\VERSION"
        if (-not (Test-Path -LiteralPath (Join-Path $outDir "VERSION"))) {
            throw "VERSION missing in release dir"
        }

        $mainExe = Join-Path $outDir $MainExeName
        $sidecarExe = Join-Path $outDir $SidecarExeName
        if (-not (Test-Path -LiteralPath $mainExe)) {
            throw "main exe missing or wrong name: expected $MainExeName"
        }
        if (-not (Test-Path -LiteralPath $sidecarExe)) {
            throw "sidecar missing in release dir"
        }
        $otherExes = Get-ChildItem -LiteralPath $outDir -Filter "*.exe" |
            Where-Object { $_.Name -ne $MainExeName -and $_.Name -ne $SidecarExeName }
        if ($otherExes.Count -gt 0) {
            throw ("unexpected exe artifacts: " + (($otherExes | ForEach-Object { $_.Name }) -join ", "))
        }
        Get-ChildItem -LiteralPath $outDir | ForEach-Object {
            Write-Host ("  " + $_.Name + " " + $_.Length)
        }
    }

    Step "Release hashes" {
        $outDir = "$Root\build\bin"
        $main = Get-Item -LiteralPath (Join-Path $outDir $MainExeName)
        $sidecar = Get-Item -LiteralPath (Join-Path $outDir $SidecarExeName)
        foreach ($f in @($main, $sidecar)) {
            $hash = (Get-FileHash -Algorithm SHA256 $f.FullName).Hash
            Write-Host ("  " + $f.Name)
            Write-Host ("    size=" + $f.Length)
            Write-Host ("    sha256=" + $hash)
        }
    }

    Write-Host ""
    Write-Host "RELEASE BUILD OK" -ForegroundColor Green
    $ScriptExit = 0
}
catch {
    Write-Host ""
    Write-Host "RELEASE BUILD FAILED: $_" -ForegroundColor Red
    $ScriptExit = 1
}
finally {
    exit $ScriptExit
}
