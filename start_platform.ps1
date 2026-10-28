# South Oakleigh Debating & MUN platform. Run:  .\start_platform.ps1   (add -Demo for fake data)
param([switch]$Demo, [int]$Port = 8080)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Setting up for the first time. This needs internet access once..."
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.12 -m venv .venv } else { & python -m venv .venv }
    & $venvPy -m pip install --upgrade pip | Out-Null
    & $venvPy -m pip install -r requirements.txt
}
$argsList = @("-m", "app", "--port", "$Port")
if ($Demo) { $argsList += "--demo" }
& $venvPy @argsList
