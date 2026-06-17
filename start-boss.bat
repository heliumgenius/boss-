@echo off
title Boss CLI - All Services
cd /d "%~dp0"

echo [*] Starting cookie server (port 9876)...
start "boss-cookie-server" /MIN .\.venv\Scripts\python.exe -m boss_cli.cookie_server
timeout /t 2 /nobreak >nul

echo [*] Starting web UI (http://127.0.0.1:8080)...
start "boss-web-ui" /MIN .\.venv\Scripts\python.exe -m boss_cli.cli web-ui --port 8080
timeout /t 2 /nobreak >nul

echo [*] Opening Edge with extension...
start msedge.exe --load-extension="%CD%\extension" "https://www.zhipin.com"

echo.
echo =============================================
echo  Cookie server:  http://127.0.0.1:9876
echo  Web UI:         http://127.0.0.1:8080
echo  Edge:           opened with cookie extension
echo.
echo  Close this window to stop all services.
echo =============================================
echo.
pause

echo [*] Stopping services...
.\.venv\Scripts\python.exe -m boss_cli.cli cookie-server stop >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq boss-web-ui" >nul 2>&1
echo [*] All stopped.
timeout /t 2 /nobreak >nul
