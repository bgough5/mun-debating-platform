@echo off
title Whip Count - Server
setlocal
cd /d "%~dp0"

echo Whip Count v2 - starting server setup...
echo.

where python >nul 2>&1
if errorlevel 1 goto :no_python

python --version 2>nul | findstr /R "^Python" >nul
if errorlevel 1 goto :no_python

echo Checking dependencies (websockets)...
pip install -r server\requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo Could not install the "websockets" package. Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting the server. Leave this window open while the lesson runs.
echo Look below for the Player client and Teacher dashboard addresses.
echo Press Ctrl+C to stop the server when you're done.
echo.
python server\server.py %*

echo.
echo Server stopped.
pause
exit /b 0

:no_python
echo.
echo Python was not found on this computer.
echo.
echo Install it from https://python.org/downloads
echo During installation, make sure to tick "Add python.exe to PATH" on the first screen.
echo Then close this window and double-click start_server.bat again.
echo.
pause
exit /b 1
