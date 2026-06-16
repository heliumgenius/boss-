@echo off
title Boss CLI - Cookie Server
cd /d "%~dp0"

echo [*] Starting cookie server...
start "boss-cookie-server" /MIN .\.venv\Scripts\python.exe -m boss_cli.cookie_server
timeout /t 3 /nobreak >nul

echo [*] Opening Edge with extension...
start msedge.exe --load-extension="%CD%\extension" "https://www.zhipin.com"

echo.
echo ========================================
echo  Cookie server running in background
echo  Edge opened with BOSS Cookie extension
echo.
echo  Close this window to stop the server.
echo ========================================
echo.
pause

taskkill /F /FI "WINDOWTITLE eq boss-cookie-server" >nul 2>&1
echo [*] Server stopped.
