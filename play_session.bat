@echo off
rem The Session, on its own (Ben, 11 Nov 2026): starts the platform in the background if it isn't running yet, then
rem opens just The Session in its own window, like a game. The desktop icon "The Session" points here.
cd /d "%~dp0"
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/session -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 goto open
if not exist ".venv\Scripts\python.exe" (
  echo The platform isn't set up yet: run start_platform.bat once first.
  pause
  exit /b 1
)
start "The Session (server: close to stop)" /min ".venv\Scripts\python.exe" -m app
powershell -NoProfile -Command "for ($i = 0; $i -lt 40; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/session -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
:open
set EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
if not exist "%EDGE%" set EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe
if exist "%EDGE%" (
  start "" "%EDGE%" --app=http://localhost:8080/session --start-maximized
) else (
  start "" http://localhost:8080/session
)
