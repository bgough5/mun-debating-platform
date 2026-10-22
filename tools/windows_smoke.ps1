# Smoke test for Ben's laptop (Phase 6 item 6). Run from the repository folder:
#
#   powershell -ExecutionPolicy Bypass -File tools\windows_smoke.ps1            # tests without the browser
#   powershell -ExecutionPolicy Bypass -File tools\windows_smoke.ps1 -Browser   # also the browser + axe tests
#
# It makes its own virtual environment (.venv-smoke, so .venv is untouched), installs the requirements,
# runs the tests, starts the platform on demo data in a temporary folder, checks it answers, stops it, and
# prints a PASS/FAIL table. Nothing touches data\ or real student data. Needs Python 3.12 and internet once.
param(
    [switch]$Browser,
    [int]$Port = 8099
)
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$onWindows = ($env:OS -eq "Windows_NT")
$results = New-Object System.Collections.ArrayList

function Add-Result([string]$step, [string]$result, [string]$detail) {
    [void]$results.Add([pscustomobject]@{ Step = $step; Result = $result; Detail = $detail })
    $colour = @{ "PASS" = "Green"; "FAIL" = "Red"; "SKIP" = "Yellow" }[$result]
    Write-Host ("{0,-28} {1,-5} {2}" -f $step, $result, $detail) -ForegroundColor $colour
}

function Show-Table {
    Write-Host ""
    $results | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
    $failed = @($results | Where-Object { $_.Result -eq "FAIL" }).Count
    if ($failed -eq 0) { Write-Host "OVERALL: PASS" -ForegroundColor Green; exit 0 }
    Write-Host "OVERALL: FAIL ($failed step(s) failed). See the Detail column." -ForegroundColor Red
    exit 1
}

# 1. Python 3.12+
$pyExe = $null
$pyArgs = @()
foreach ($cand in @("py|-3.12", "python|", "python3|")) {
    $exe, $extra = $cand.Split("|")
    $candArgs = @()
    if ($extra) { $candArgs = @($extra) }
    try {
        $ver = & $exe @candArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) {
            $parts = ("" + $ver).Trim().Split(".")
            if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 12) { $pyExe = $exe; $pyArgs = $candArgs; break }
        }
    } catch { }
}
if ($null -eq $pyExe) { Add-Result "Python 3.12" "FAIL" "Install Python 3.12 from python.org and tick 'Add python.exe to PATH'."; Show-Table }
Add-Result "Python 3.12" "PASS" ("found: " + $pyExe + " " + ($pyArgs -join " ") + " (" + ("" + $ver).Trim() + ")")

# 2. Virtual environment and requirements
$venv = Join-Path $root ".venv-smoke"
if ($onWindows) { $vpy = Join-Path $venv "Scripts\python.exe" } else { $vpy = Join-Path $venv "bin/python" }
if (-not (Test-Path $vpy)) { & $pyExe @pyArgs -m venv $venv | Out-Null }
if (-not (Test-Path $vpy)) { Add-Result "Virtual environment" "FAIL" "python -m venv failed"; Show-Table }
& $vpy -m pip install --quiet --disable-pip-version-check -r requirements.txt -r requirements-dev.txt 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Add-Result "Install requirements" "FAIL" "pip install failed (internet needed once)"; Show-Table }
Add-Result "Install requirements" "PASS" "requirements.txt + requirements-dev.txt"

# 3. Tests without the browser
# (pytest.ini already passes -q; a second -q would hide the summary line)
$out = & $vpy -m pytest -m "not ui" -p no:warnings 2>&1 | Out-String
$code = $LASTEXITCODE
$summary = "" + ($out -split "`n" | Where-Object { $_ -match "\d+ (passed|failed)" } | Select-Object -Last 1)
if (-not $summary.Trim()) { $summary = "pytest exit code $code" }
if ($code -eq 0) { Add-Result "Tests (engine, API)" "PASS" $summary.Trim() } else { Add-Result "Tests (engine, API)" "FAIL" ($summary.Trim() + " - see: .venv-smoke python -m pytest -m 'not ui'") }

# 4. Browser and accessibility tests (optional: downloads Chromium once)
if ($Browser) {
    & $vpy -m playwright install chromium 2>&1 | Out-Null
    $out = & $vpy -m pytest -m ui -p no:warnings 2>&1 | Out-String
    $code = $LASTEXITCODE
    $summary = "" + ($out -split "`n" | Where-Object { $_ -match "\d+ (passed|failed)" } | Select-Object -Last 1)
    if (-not $summary.Trim()) { $summary = "pytest exit code $code" }
    if ($code -eq 0) { Add-Result "Browser + axe tests" "PASS" $summary.Trim() } else { Add-Result "Browser + axe tests" "FAIL" $summary.Trim() }
} else {
    Add-Result "Browser + axe tests" "SKIP" "add -Browser to run them"
}

# 5. Start the platform on demo data in a temporary folder and check it answers
$data = Join-Path ([System.IO.Path]::GetTempPath()) ("soc-smoke-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $data | Out-Null
$log = Join-Path $data "server.log"
$err = Join-Path $data "server.err.log"
$appArgs = @("-m", "app", "--demo", "--host", "127.0.0.1", "--port", "$Port", "--data-dir", "`"$data`"")
if ($onWindows) {
    $proc = Start-Process -FilePath $vpy -ArgumentList $appArgs -RedirectStandardOutput $log -RedirectStandardError $err -PassThru -WindowStyle Hidden
} else {
    $proc = Start-Process -FilePath $vpy -ArgumentList $appArgs -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
}
$ok = $false
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 90) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/healthz" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if ($ok) { Add-Result "Platform starts" "PASS" ("health check answered in {0:N1} s" -f $sw.Elapsed.TotalSeconds) }
else { Add-Result "Platform starts" "FAIL" "no answer on port $Port within 90 s; see $err" }

# 6. Key pages load
if ($ok) {
    foreach ($page in @("/join", "/login", "/help/students", "/static/icons/sprite.svg")) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port$page" -UseBasicParsing -TimeoutSec 10
            if ($r.StatusCode -eq 200) { Add-Result "Page $page" "PASS" "200" } else { Add-Result "Page $page" "FAIL" ("" + $r.StatusCode) }
        } catch { Add-Result "Page $page" "FAIL" $_.Exception.Message }
    }
}

# 7. Stop the platform and tidy up
if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500
Remove-Item -Recurse -Force $data -ErrorAction SilentlyContinue
Add-Result "Stopped and tidied" "PASS" "temporary demo data removed"

Show-Table
