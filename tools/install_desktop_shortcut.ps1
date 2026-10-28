# Puts a "SOC Debating & MUN" shortcut, with the College crest as its icon, on this user's desktop.
# Clicking it runs launch_platform.ps1: starts the platform and opens the staff and student windows.
#   powershell -ExecutionPolicy Bypass -File tools\install_desktop_shortcut.ps1
param([string]$Name = "SOC Debating & MUN")

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$icon = Join-Path $root "assets\soc_launcher.ico"
if (-not (Test-Path $icon)) { & (Join-Path $PSScriptRoot "make_launcher_icon.ps1") }

$desktop = [Environment]::GetFolderPath("Desktop")
$path = Join-Path $desktop "$Name.lnk"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($path)
$lnk.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\launch_platform.ps1`""
$lnk.WorkingDirectory = $root
$lnk.IconLocation = "$icon,0"
$lnk.Description = "Start the South Oakleigh Debating & Model UN platform and open the staff and student windows"
$lnk.WindowStyle = 7          # minimised: the launcher itself has nothing to show
$lnk.Save()
Write-Host "Shortcut created: $path"
