# South Oakleigh Debating & Model UN platform: the one-click launcher behind the desktop shortcut.
#
# Starts the platform if it isn't already running, waits until it answers, then opens two browser windows:
#   - the staff (facilitator) view, in a normal Edge window;
#   - the student view, in an InPrivate Edge window, so a student sign-in never replaces the staff one.
# The platform runs in a minimised black window titled "...close this window to stop it".
# Clicking the shortcut again while it runs just opens the two windows again.
#
# Install the shortcut:  powershell -ExecutionPolicy Bypass -File tools\install_desktop_shortcut.ps1
param([int]$Port = 8080)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Add-Type -AssemblyName PresentationFramework

$AppName = "SOC Debating & MUN"
# 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 first and the platform listens on IPv4, which
# measured 2.06 s per connection against 0.08 s (and made a 2-second health check always fail).
$Base = "http://127.0.0.1:$Port"
$VenvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

function Show-Problem([string]$Message) {
    [System.Windows.MessageBox]::Show($Message, $AppName, "OK", "Error") | Out-Null
    exit 1
}

function Test-Up {
    try { return (Invoke-WebRequest "$Base/healthz" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 } catch { return $false }
}

if (-not (Test-Up)) {
    # First run on this laptop: set up Python's packages in a visible window (needs internet once).
    if (-not (Test-Path $VenvPy)) {
        $setup = "Set-Location '$PSScriptRoot'; Write-Host 'Setting up the platform for the first time. This needs internet access once...';" +
                 " if (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv .venv } else { python -m venv .venv };" +
                 " .\.venv\Scripts\python.exe -m pip install --upgrade pip; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
        Start-Process powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $setup -Wait
        if (-not (Test-Path $VenvPy)) {
            Show-Problem "First-time setup didn't finish. Check that Python 3.12 is installed (python.org) and the laptop is online, then click the shortcut again."
        }
    }

    # Port taken by something else (not the platform)? Say so instead of failing silently.
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        Show-Problem "Something else on this laptop is already using port $Port, so the platform can't start. Close that program (or restart the laptop) and try again."
    }

    # The platform, in its own minimised window. Closing that window stops it. /k keeps the window open
    # if the platform crashes, so the error stays readable. No "&" in the title: cmd reads it as "run the
    # next command", which split the line and stopped the platform starting (found in the first test).
    $title = "SOC Debating and MUN platform - close this window to stop it"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k title $title && `"$VenvPy`" -m app --port $Port" `
        -WorkingDirectory $PSScriptRoot -WindowStyle Minimized

    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Up)) {
        if ((Get-Date) -gt $deadline) {
            Show-Problem "The platform didn't start within 60 seconds. Open the minimised black window on the taskbar to see why."
        }
        Start-Sleep -Milliseconds 500
    }
}

# Two windows: staff, and student (private window, separate sign-in).
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($edge) {
    Start-Process $edge -ArgumentList "--new-window", "$Base/"
    Start-Sleep -Milliseconds 800
    Start-Process $edge -ArgumentList "--inprivate", "$Base/join"
} elseif ($chrome) {
    Start-Process $chrome -ArgumentList "--new-window", "$Base/"
    Start-Sleep -Milliseconds 800
    Start-Process $chrome -ArgumentList "--incognito", "$Base/join"
} else {
    Start-Process "$Base/"
    Start-Process "$Base/join"
    [System.Windows.MessageBox]::Show("Neither Edge nor Chrome was found, so both pages opened in your normal browser. Signing in as a student there will sign the staff account out; use a private window for the student page.", $AppName, "OK", "Warning") | Out-Null
}
