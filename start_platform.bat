@echo off
rem South Oakleigh Debating & MUN platform. Double-click to start.
rem First run creates a private Python environment in .venv and installs what it needs.
rem Add  --demo  to open the demo (fake data) dataset, e.g.  start_platform.bat --demo
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3.12) else (set PY=python)
if not exist ".venv\Scripts\python.exe" (
  echo Setting up for the first time. This needs internet access once...
  %PY% -m venv .venv || goto :fail
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)
".venv\Scripts\python.exe" -m app %*
goto :eof
:fail
echo.
echo Setup failed. Check that Python 3.12 is installed (python.org) and that you are online, then try again.
pause
