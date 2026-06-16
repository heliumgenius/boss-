@echo off
title Boss CLI - Stop
cd /d "%~dp0"

echo [*] Stopping cookie server...
.\.venv\Scripts\python.exe -m boss_cli.cli cookie-server stop

echo [*] Closing Edge...
taskkill /F /IM msedge.exe >nul 2>&1

echo.
echo [*] All stopped.
timeout /t 2 /nobreak >nul
